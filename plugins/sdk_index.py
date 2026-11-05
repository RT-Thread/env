"""Serverless plugin catalog stored in the local SDK Git repository."""

from copy import deepcopy
from functools import cmp_to_key
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request

from .compatibility import compare_versions, version_satisfies
from .errors import ManifestError, UsageError
from .manifest import PLUGIN_ID_RE, VERSION_RE
from .market import (
    DOWNLOAD_LIMIT, DOWNLOAD_TIMEOUT, MarketError, artifact_compatibility_checks,
    network, runtime_profile, save_download,
)
from .paths import path_is_within


JSON_LIMIT = 1024 * 1024
_DIRECTORY_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
_FILENAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._+-]*\.epack$')
_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
_ASSET_HOSTS = frozenset((
    'release-assets.githubusercontent.com', 'objects.githubusercontent.com',
    'github-releases.githubusercontent.com',
))


def _invalid(message):
    return MarketError('invalid SDK plugin index: %s' % message, code='sdk_index_invalid')


def _https_origin(url):
    if not isinstance(url, str) or any(ord(char) <= 32 or ord(char) == 127 for char in url):
        raise _invalid('artifact URL must be an HTTPS URL without whitespace')
    try:
        parsed = urlparse(url)
        port = parsed.port
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.fragment or '\\' in url
                or port is not None and not 1 <= port <= 65535):
            raise ValueError()
    except ValueError:
        raise _invalid('artifact URL must use HTTPS without credentials or fragment')
    return parsed.hostname.lower(), port or 443


class ReleaseRedirectHandler(HTTPRedirectHandler):
    """Allow HTTPS redirects only within the source or GitHub asset hosts."""

    def __init__(self, url):
        self.origin = _https_origin(url)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            target = _https_origin(newurl)
        except MarketError:
            target = None
        github_asset = (self.origin == ('github.com', 443) and target is not None
                        and target[0] in _ASSET_HOSTS and target[1] == 443)
        if target != self.origin and not github_asset:
            raise MarketError('plugin release redirected to an unexpected host or scheme',
                              code='market_redirect_denied')
        return super(ReleaseRedirectHandler, self).redirect_request(req, fp, code, msg, headers, newurl)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: %s' % key)
        result[key] = value
    return result


class SdkIndexClient(object):
    def __init__(self, index_path, env_root=None):
        self.index_path = os.path.abspath(index_path)
        self.root = os.path.realpath(os.path.dirname(self.index_path))
        self.network = network.NetworkSettings(env_root)

    def _read(self, path):
        if not path_is_within(self.root, os.path.realpath(path)):
            raise _invalid('index path escapes env-plugins')
        try:
            with open(path, 'rb') as source:
                payload = source.read(JSON_LIMIT + 1)
            if len(payload) > JSON_LIMIT:
                raise ValueError('JSON exceeds size limit')
            value = json.loads(payload.decode('utf-8'), object_pairs_hook=_unique_object)
            if not isinstance(value, dict):
                raise ValueError('JSON root must be an object')
            return value
        except (OSError, UnicodeError, ValueError) as exc:
            raise _invalid('cannot read %s (%s)' % (os.path.basename(path), type(exc).__name__))

    def _catalog(self):
        root = self._read(self.index_path)
        directories = root.get('index')
        if type(root.get('version')) is not int or root['version'] != 1 or not isinstance(directories, list):
            raise _invalid('root requires version 1 and an index list')
        plugins = {}
        seen = set()
        for directory in directories:
            if not isinstance(directory, str) or not _DIRECTORY_RE.fullmatch(directory) or directory in seen:
                raise _invalid('invalid or duplicate plugin directory')
            seen.add(directory)
            plugin = self._plugin(self._read(os.path.join(self.root, directory, 'index.json')))
            if plugin['id'] in plugins:
                raise _invalid('duplicate plugin id: %s' % plugin['id'])
            plugins[plugin['id']] = plugin
        return plugins

    def _plugin(self, raw):
        plugin_id = raw.get('id')
        if not isinstance(plugin_id, str) or not PLUGIN_ID_RE.fullmatch(plugin_id):
            raise _invalid('plugin id is invalid')
        name = raw.get('name')
        if not isinstance(name, str) or not name.strip():
            raise _invalid('plugin name is required')
        plugin = dict(raw)
        for field in ('description', 'updated_at'):
            if not isinstance(plugin.get(field, ''), str):
                raise _invalid('%s must be a string' % field)
            plugin.setdefault(field, '')
        if not isinstance(plugin.get('capabilities', []), list) or any(
                not isinstance(item, str) for item in plugin.get('capabilities', [])):
            raise _invalid('capabilities must be a string list')
        plugin.setdefault('capabilities', [])
        self._status(plugin)
        versions = plugin.get('versions')
        if not isinstance(versions, list) or not versions:
            raise _invalid('plugin requires a nonempty versions list')
        seen = set()
        for version in versions:
            if not isinstance(version, dict):
                raise _invalid('version must be an object')
            number = version.get('version')
            try:
                if not isinstance(number, str) or not VERSION_RE.fullmatch(number) or number in seen:
                    raise ValueError()
                compare_versions(number, number)
            except (ManifestError, ValueError):
                raise _invalid('invalid or duplicate version')
            seen.add(number)
            self._status(version)
            artifacts = version.get('artifacts')
            if not isinstance(artifacts, list) or not artifacts:
                raise _invalid('version requires a nonempty artifacts list')
            for artifact in artifacts:
                self._artifact(artifact, number)
        versions.sort(key=cmp_to_key(lambda a, b: compare_versions(b['version'], a['version'])))
        published = [item for item in versions if item['status'] == 'published']
        plugin['latest_version'] = (published or versions)[0]['version']
        plugin['download_count'] = 0
        plugin['source_type'] = 'sdk'
        return plugin

    @staticmethod
    def _status(record):
        record.setdefault('status', 'published')
        if record['status'] not in ('published', 'yanked'):
            raise _invalid('status must be published or yanked')

    @staticmethod
    def _artifact(artifact, version):
        if not isinstance(artifact, dict):
            raise _invalid('artifact must be an object')
        filename = artifact.get('filename')
        digest = artifact.get('sha256')
        if not isinstance(filename, str) or not _FILENAME_RE.fullmatch(filename):
            raise _invalid('artifact filename must be an .epack basename')
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise _invalid('artifact sha256 must be 64 lowercase hexadecimal characters')
        url = artifact.pop('url', None)
        _https_origin(url)
        artifact['download_url'] = url
        artifact['id'] = digest
        artifact['version'] = version
        size = artifact.get('size_bytes')
        if size is not None and (type(size) is not int or not 0 < size <= DOWNLOAD_LIMIT):
            raise _invalid('artifact size_bytes is outside the download limit')
        compatibility = artifact.get('compatibility')
        if not isinstance(compatibility, dict):
            raise _invalid('artifact compatibility is required')
        for field in ('env', 'python'):
            expression = compatibility.get(field)
            try:
                if not isinstance(expression, str) or not expression:
                    raise ValueError()
                for clause in expression.split(','):
                    version_satisfies('0.0.0', clause)
            except (ManifestError, ValueError):
                raise _invalid('invalid compatibility.%s constraint' % field)
        for field in ('implementations', 'abis', 'platforms', 'architectures'):
            values = compatibility.get(field)
            if (not isinstance(values, list) or not values
                    or any(not isinstance(item, str) or not item for item in values)):
                raise _invalid('compatibility.%s must be a nonempty string list' % field)

    def health(self):
        self._catalog()
        return True

    def list_plugins(self, query=None, sort='updated', page=1, page_size=20):
        if sort not in ('updated', 'downloads', 'name'):
            raise UsageError('unknown plugin catalog sort')
        if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 100:
            raise UsageError('invalid plugin catalog page')
        items = list(self._catalog().values())
        if query:
            needle = query.casefold()
            items = [item for item in items if needle in ' '.join(
                (item['id'], item['name'], item['description'])).casefold()]
        items.sort(key=lambda item: (item['name'].casefold(), item['id']))
        if sort == 'updated':
            items.sort(key=lambda item: item['updated_at'], reverse=True)
        total = len(items)
        items = items[(page - 1) * page_size:page * page_size]
        return {'items': [self._summary(item) for item in items], 'total': total,
                'page': page, 'page_size': page_size}

    def plugin_detail(self, plugin_id):
        plugin = self._catalog().get(plugin_id)
        if plugin is None:
            raise MarketError('plugin is not in the SDK index', code='plugin_not_found', status=404)
        return plugin

    @staticmethod
    def _summary(plugin):
        return {key: deepcopy(value) for key, value in plugin.items() if key != 'versions'}

    def resolve(self, plugin_id):
        plugin = self.plugin_detail(plugin_id)
        if plugin['status'] == 'yanked' or all(item['status'] == 'yanked' for item in plugin['versions']):
            raise MarketError('plugin or version has been yanked', code='yanked', status=410)
        runtime = runtime_profile()
        for version in plugin['versions']:
            if version['status'] == 'yanked':
                continue
            for artifact in version['artifacts']:
                if all(check['ok'] for check in artifact_compatibility_checks(artifact['compatibility'], runtime)):
                    return {'plugin': self._summary(plugin), 'artifact': deepcopy(artifact)}
        raise MarketError('no compatible artifact for the current environment', code='incompatible', status=404)

    def download(self, sha256, destination, filename=None):
        if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
            raise UsageError('artifact checksum is invalid')
        # Reread the index to reject artifacts withdrawn since resolution.
        for plugin in self._catalog().values():
            if plugin['status'] != 'published':
                continue
            for version in plugin['versions']:
                if version['status'] != 'published':
                    continue
                for artifact in version['artifacts']:
                    if artifact['sha256'] == sha256 and (filename is None or artifact['filename'] == filename):
                        return self._download(artifact, destination)
        raise MarketError('artifact is not in the published SDK index', code='artifact_not_found', status=404)

    def _download(self, artifact, destination):
        url = artifact['download_url']
        opener = network.urllib_opener(ReleaseRedirectHandler(url), env_root=self.network.env_root)
        request = Request(url, headers={'Accept': 'application/octet-stream', 'User-Agent': 'rt-env-webui'})
        try:
            response = opener.open(request, timeout=self.network.timeout(DOWNLOAD_TIMEOUT))
        except HTTPError as exc:
            exc.close()
            raise MarketError('plugin release download failed (HTTP %d)' % exc.code,
                              code='market_unreachable')
        except (URLError, OSError):
            raise MarketError('plugin release is unreachable', code='market_unreachable')
        return save_download(response, artifact['sha256'], destination, artifact['filename'],
                             expected_size=artifact.get('size_bytes'))

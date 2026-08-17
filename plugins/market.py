"""Optional online plugin market client used by CLI and the WebUI BFF."""

import hashlib
import json
import os
import platform
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .compatibility import (
    compare_versions,
    current_env_version,
    normalize_architecture,
    normalize_platform,
    version_satisfies,
)
from .errors import PluginError, UsageError


MARKET_ENV = 'ENV_PLUGIN_MARKET_URL'
MARKET_FILE = 'market.json'
JSON_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 120
DOWNLOAD_LIMIT = 256 * 1024 * 1024
_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')


class MarketError(PluginError):
    exit_code = 4

    def __init__(self, message, code='market_error', status=502, details=None):
        super(MarketError, self).__init__(message)
        self.code = code
        self.status = int(status)
        self.details = details


def normalize_market_url(value):
    text = (value or '').strip()
    if not text:
        raise UsageError('market URL is required')
    parsed = urlparse(text)
    if parsed.scheme not in ('http', 'https'):
        raise UsageError('market URL must use http or https')
    if parsed.username or parsed.password:
        raise UsageError('market URL must not contain user information')
    if parsed.query or parsed.fragment:
        raise UsageError('market URL must not contain a query or fragment')
    if not parsed.hostname:
        raise UsageError('market URL must include a host')
    path = '' if parsed.path in ('', '/') else parsed.path.rstrip('/')
    return '%s://%s%s' % (parsed.scheme, parsed.netloc, path)


def market_config_path(paths):
    return os.path.join(paths.root, MARKET_FILE)


def load_market_config(paths, environ=None):
    environ = os.environ if environ is None else environ
    env_value = (environ.get(MARKET_ENV) or '').strip()
    if env_value:
        try:
            return {'enabled': True, 'url': normalize_market_url(env_value), 'source': 'env'}
        except UsageError:
            return {'enabled': False, 'url': '', 'source': None}
    raw = _read_file_url(paths)
    if not raw:
        return {'enabled': False, 'url': '', 'source': None}
    try:
        return {'enabled': True, 'url': normalize_market_url(raw), 'source': 'file'}
    except UsageError:
        return {'enabled': False, 'url': '', 'source': None}


def save_market_url(paths, url):
    normalized = normalize_market_url(url)
    paths.ensure()
    target = market_config_path(paths)
    handle, temporary = tempfile.mkstemp(prefix='.market-', dir=paths.root, text=True)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as output:
            json.dump({'url': normalized}, output, ensure_ascii=True, indent=2, sort_keys=True)
            output.write('\n')
        os.replace(temporary, target)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return load_market_config(paths)


def clear_market_url(paths):
    try:
        os.unlink(market_config_path(paths))
    except OSError:
        pass
    return load_market_config(paths)


def runtime_profile():
    env_version = current_env_version() or ''
    if env_version[:1] in ('v', 'V'):
        env_version = env_version[1:]
    return {
        'env': env_version,
        'python': '%d.%d.%d' % sys.version_info[:3],
        'implementation': platform.python_implementation().lower(),
        'abi': 'py3',
        'platform': normalize_platform(),
        'architecture': normalize_architecture(),
    }


def annotate_catalog_item(item, installed):
    result = dict(item)
    local = installed.get(item.get('id'))
    result['installed'] = local is not None
    result['installed_version'] = local['version'] if local else None
    result['enabled'] = bool(local['enabled']) if local else False
    latest = item.get('latest_version') or ''
    if local is None:
        result['action'] = 'install'
    elif latest and compare_versions(latest, local['version']) > 0:
        result['action'] = 'upgrade'
    else:
        result['action'] = 'installed'
    return result


def artifact_compatibility_checks(compatibility, runtime=None):
    runtime = runtime or runtime_profile()
    compatibility = compatibility or {}
    checks = []

    env_expr = compatibility.get('env') or ''
    checks.append(_version_check('env', env_expr, runtime.get('env'), 'Env'))

    python_expr = compatibility.get('python') or ''
    checks.append(_version_check('python', python_expr, runtime.get('python'), 'Python'))

    implementations = list(compatibility.get('implementations') or [])
    implementation = runtime.get('implementation')
    impl_ok = implementation in implementations
    checks.append(
        {
            'field': 'implementation',
            'expected': implementations,
            'actual': implementation,
            'ok': impl_ok,
            'message': (
                'Python implementation %s is supported' % implementation
                if impl_ok
                else 'Python implementation %s is not in %s' % (implementation, _join_values(implementations))
            ),
        }
    )

    platforms = list(compatibility.get('platforms') or [])
    current_platform = runtime.get('platform')
    platform_ok = 'any' in platforms or current_platform in platforms
    checks.append(
        {
            'field': 'platform',
            'expected': platforms,
            'actual': current_platform,
            'ok': platform_ok,
            'message': (
                'platform %s is supported' % current_platform
                if platform_ok
                else 'platform %s is not in %s' % (current_platform, _join_values(platforms))
            ),
        }
    )

    architectures = list(compatibility.get('architectures') or [])
    current_arch = runtime.get('architecture')
    arch_ok = 'any' in architectures or current_arch in architectures
    checks.append(
        {
            'field': 'architecture',
            'expected': architectures,
            'actual': current_arch,
            'ok': arch_ok,
            'message': (
                'architecture %s is supported' % current_arch
                if arch_ok
                else 'architecture %s is not in %s' % (current_arch, _join_values(architectures))
            ),
        }
    )

    abis = list(compatibility.get('abis') or [])
    current_abi = runtime.get('abi')
    abi_ok = current_abi in abis or 'py3' in abis
    checks.append(
        {
            'field': 'abi',
            'expected': abis,
            'actual': current_abi,
            'ok': abi_ok,
            'message': (
                'Python ABI %s is supported' % current_abi
                if abi_ok
                else 'Python ABI %s is not in %s' % (current_abi, _join_values(abis))
            ),
        }
    )
    return checks


def diagnose_market_plugin(detail, local=None, runtime=None):
    runtime = runtime or runtime_profile()
    reasons = []
    artifacts = []
    plugin_status = detail.get('status') or 'published'
    if plugin_status == 'yanked':
        reasons.append(
            {
                'code': 'yanked',
                'message': 'plugin has been yanked and cannot be downloaded',
            }
        )

    versions = detail.get('versions') or []
    if not versions:
        reasons.append({'code': 'no_versions', 'message': 'plugin has no published versions'})

    for version in versions:
        version_name = version.get('version') or ''
        version_status = version.get('status') or 'published'
        version_artifacts = version.get('artifacts') or []
        if not version_artifacts:
            artifacts.append(
                {
                    'version': version_name,
                    'filename': '',
                    'status': version_status,
                    'compatible': False,
                    'checks': [],
                    'failed_checks': ['version has no artifacts'],
                    'summary': 'version has no artifacts',
                }
            )
            continue
        for artifact in version_artifacts:
            yanked = plugin_status == 'yanked' or version_status == 'yanked'
            checks = artifact_compatibility_checks(artifact.get('compatibility') or {}, runtime)
            failed = [item['message'] for item in checks if not item['ok']]
            compatible = (not yanked) and not failed
            if yanked:
                summary = 'version has been yanked'
                failed = ['version has been yanked'] + failed
            elif compatible:
                summary = 'matches the current environment'
            else:
                summary = '; '.join(failed)
            artifacts.append(
                {
                    'version': artifact.get('version') or version_name,
                    'filename': artifact.get('filename') or '',
                    'status': 'yanked' if yanked else version_status,
                    'compatible': compatible,
                    'checks': checks,
                    'failed_checks': failed,
                    'summary': summary,
                }
            )

    compatible_artifacts = [item for item in artifacts if item['compatible']]
    if plugin_status != 'yanked' and versions and not compatible_artifacts:
        reasons.append(
            {
                'code': 'incompatible',
                'message': (
                    'no published artifact matches Env %s, Python %s, %s/%s'
                    % (
                        runtime.get('env'),
                        runtime.get('python'),
                        runtime.get('platform'),
                        runtime.get('architecture'),
                    )
                ),
            }
        )

    if local and compatible_artifacts:
        best = compatible_artifacts[0]['version']
        for item in compatible_artifacts[1:]:
            if compare_versions(item['version'], best) > 0:
                best = item['version']
        if compare_versions(best, local.get('version') or '0.0.0') <= 0:
            reasons.append(
                {
                    'code': 'already_latest',
                    'message': 'installed version %s is already the newest compatible market version' % local.get('version'),
                }
            )

    if reasons:
        reason_code = reasons[0]['code']
        summary = reasons[0]['message']
    elif compatible_artifacts:
        reason_code = 'ok'
        summary = 'compatible artifact %s is available' % compatible_artifacts[0]['version']
    else:
        reason_code = 'ok'
        summary = 'plugin can be installed'

    return {
        'runtime': runtime,
        'reason_code': reason_code,
        'reasons': reasons,
        'artifacts': artifacts,
        'compatible_count': len(compatible_artifacts),
        'summary': summary,
    }


def strip_download_urls(detail):
    result = dict(detail)
    versions = []
    for version in result.get('versions') or []:
        current = dict(version)
        artifacts = []
        for artifact in current.get('artifacts') or []:
            public = dict(artifact)
            public.pop('download_url', None)
            artifacts.append(public)
        current['artifacts'] = artifacts
        versions.append(current)
    if 'versions' in result:
        result['versions'] = versions
    return result


def _read_file_url(paths):
    try:
        with open(market_config_path(paths), 'r', encoding='utf-8') as source:
            data = json.load(source)
    except (OSError, ValueError, TypeError):
        return ''
    if not isinstance(data, dict):
        return ''
    value = data.get('url')
    return value.strip() if isinstance(value, str) else ''


class _OriginRedirectHandler(HTTPRedirectHandler):
    def __init__(self, origin):
        HTTPRedirectHandler.__init__(self)
        self.origin = origin

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        origin = '%s://%s' % (parsed.scheme.lower(), parsed.netloc)
        if origin != self.origin:
            raise MarketError(
                'plugin market redirected to an unexpected host',
                code='market_redirect_denied',
                status=502,
            )
        return HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)


class MarketClient(object):
    def __init__(self, base_url):
        self.base_url = normalize_market_url(base_url)
        parsed = urlparse(self.base_url)
        self.origin = '%s://%s' % (parsed.scheme.lower(), parsed.netloc)
        self.opener = build_opener(_OriginRedirectHandler(self.origin))

    def health(self):
        payload = self._get_json('/api/v1/health')
        return payload.get('status') == 'ok'

    def list_plugins(self, query=None, sort='updated', page=1, page_size=20):
        params = {
            'sort': sort or 'updated',
            'page': str(page or 1),
            'page_size': str(page_size or 20),
        }
        if query:
            params['q'] = query
        return self._get_json('/api/v1/plugins', params)

    def plugin_detail(self, plugin_id):
        return self._get_json('/api/v1/plugins/%s' % _path_segment(plugin_id))

    def resolve(self, plugin_id):
        params = dict(runtime_profile())
        params['plugin_id'] = plugin_id
        try:
            return self._get_json('/api/v1/resolve', params)
        except MarketError as exc:
            if exc.status == 410 or exc.code == 'yanked':
                raise MarketError('plugin or version has been yanked', code='yanked', status=410)
            if exc.status == 404:
                raise MarketError(
                    'no compatible artifact for the current environment',
                    code='incompatible',
                    status=404,
                )
            raise

    def download(self, sha256, destination, filename=None):
        digest = (sha256 or '').strip().lower()
        if not _SHA256_RE.match(digest):
            raise UsageError('artifact checksum is invalid')
        path = '/api/v1/artifacts/%s/download' % digest
        response = self._open(path, timeout=DOWNLOAD_TIMEOUT)
        try:
            header = (response.headers.get('X-Checksum-SHA256') or '').strip().lower()
            length = response.headers.get('Content-Length')
            if length is not None:
                try:
                    declared = int(length)
                except ValueError:
                    raise MarketError('plugin market returned an invalid download size', code='market_invalid_response')
                if declared < 0 or declared > DOWNLOAD_LIMIT:
                    raise MarketError('plugin package exceeds size limit', code='payload_too_large', status=413)
            hasher = hashlib.sha256()
            total = 0
            with open(destination, 'wb') as output:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > DOWNLOAD_LIMIT:
                        raise MarketError('plugin package exceeds size limit', code='payload_too_large', status=413)
                    hasher.update(chunk)
                    output.write(chunk)
            actual = hasher.hexdigest()
            if header and header != actual:
                raise MarketError('downloaded package checksum does not match', code='checksum_mismatch')
            if actual != digest:
                raise MarketError('downloaded package checksum does not match', code='checksum_mismatch')
            return {
                'path': destination,
                'sha256': actual,
                'size_bytes': total,
                'filename': filename or os.path.basename(destination),
            }
        finally:
            response.close()

    def _get_json(self, path, query=None):
        response = self._open(path, query=query, timeout=JSON_TIMEOUT)
        try:
            payload = response.read(1024 * 1024)
            status = getattr(response, 'status', 200)
            try:
                value = json.loads(payload.decode('utf-8'))
            except (UnicodeError, ValueError):
                raise MarketError('plugin market returned invalid JSON', code='market_invalid_response')
            if status >= 400:
                raise _error_from_payload(value, status)
            return value
        finally:
            response.close()

    def _open(self, path, query=None, timeout=JSON_TIMEOUT):
        url = self.base_url + path
        if query:
            url = url + '?' + urlencode(query)
        request = Request(url, headers={'Accept': '*/*', 'User-Agent': 'rt-env-webui'})
        try:
            return self.opener.open(request, timeout=timeout)
        except HTTPError as exc:
            payload = b''
            try:
                payload = exc.read(1024 * 1024)
            except Exception:
                pass
            try:
                value = json.loads(payload.decode('utf-8')) if payload else {}
            except (UnicodeError, ValueError):
                value = {}
            raise _error_from_payload(value, exc.code)
        except URLError:
            raise MarketError('plugin market is unreachable', code='market_unreachable', status=502)
        except MarketError:
            raise
        except OSError:
            raise MarketError('plugin market is unreachable', code='market_unreachable', status=502)


def public_artifact(artifact):
    if artifact is None:
        return None
    result = dict(artifact)
    result.pop('download_url', None)
    return result


def _path_segment(value):
    text = (value or '').strip()
    if not text or '/' in text or '\\' in text or text in ('.', '..'):
        raise UsageError('plugin id is invalid')
    return text


def _error_from_payload(value, status):
    error = value.get('error') if isinstance(value, dict) else None
    if not isinstance(error, dict):
        error = {}
    code = error.get('code') or 'market_error'
    message = error.get('message') or 'plugin market request failed'
    if status == 410:
        code = 'yanked'
        message = message or 'plugin or version has been yanked'
    return MarketError(message, code=code, status=status)


def _join_values(values):
    if not values:
        return '(none)'
    return ', '.join(str(item) for item in values)


def _version_check(field, expression, actual, label):
    if not expression:
        return {
            'field': field,
            'expected': expression,
            'actual': actual,
            'ok': False,
            'message': '%s constraint is missing' % label,
        }
    try:
        ok = version_satisfies(actual, expression)
    except Exception:
        return {
            'field': field,
            'expected': expression,
            'actual': actual,
            'ok': False,
            'message': '%s constraint %s is invalid' % (label, expression),
        }
    return {
        'field': field,
        'expected': expression,
        'actual': actual,
        'ok': ok,
        'message': (
            '%s %s satisfies %s' % (label, actual, expression)
            if ok
            else '%s %s does not satisfy %s' % (label, actual, expression)
        ),
    }

from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError
from urllib.request import Request

import network
from plugins.errors import UsageError
from plugins.market import MarketClient, MarketError, clear_market_url, load_market_config, save_market_url
from plugins.paths import PluginPaths
from plugins.sdk_index import ReleaseRedirectHandler, SdkIndexClient


RUNTIME = {'env': '2.0.2', 'python': '3.12.0', 'implementation': 'cpython', 'abi': 'py3',
           'platform': 'linux', 'architecture': 'x86_64'}
RELEASE_URL = 'https://github.com/example/plugins/releases/download/v1.0.0/plugin.epack'


def index_plugin(plugin_id='org.example.demo', content=b'package', version='1.0.0'):
    return {
        'id': plugin_id, 'name': 'Demo', 'description': 'Example plugin', 'capabilities': ['webui'],
        'versions': [{'version': version, 'artifacts': [{
            'filename': 'plugin.epack', 'url': RELEASE_URL, 'sha256': hashlib.sha256(content).hexdigest(),
            'size_bytes': len(content), 'compatibility': {
                'env': '>=2.0.2,<3.0.0', 'python': '>=3.7.0,<4.0.0', 'implementations': ['cpython'],
                'abis': ['py3'], 'platforms': ['any'], 'architectures': ['any'],
            },
        }]}],
    }


def write_sdk_index(env_root, plugins):
    root = Path(env_root) / 'packages' / 'sdk' / 'env-plugins'
    root.mkdir(parents=True, exist_ok=True)
    for plugin in plugins:
        directory = root / plugin['id']
        directory.mkdir(exist_ok=True)
        (directory / 'index.json').write_text(json.dumps(plugin), encoding='utf-8')
    (root / 'index.json').write_text(json.dumps({'version': 1, 'index': [item['id'] for item in plugins]}),
                                     encoding='utf-8')
    return root / 'index.json'


def download_response(content=b'package', headers=None):
    response = io.BytesIO(content)
    response.headers = headers or {}
    return response


class SdkConfigTest(unittest.TestCase):
    def test_default_source_and_explicit_market_precedence(self):
        with tempfile.TemporaryDirectory() as root, mock.patch.dict(os.environ, {'ENV_PLUGIN_MARKET_URL': ''}):
            paths = PluginPaths(env_root=root)
            index = write_sdk_index(root, [])
            self.assertEqual(load_market_config(paths, environ={}),
                             {'enabled': True, 'url': str(index), 'source': 'sdk'})
            save_market_url(paths, 'https://market.example')
            self.assertEqual(load_market_config(paths, environ={})['source'], 'file')
            self.assertEqual(load_market_config(paths, environ={'ENV_PLUGIN_MARKET_URL': 'https://override.example'})[
                'source'], 'env')
            self.assertFalse(load_market_config(paths, environ={'ENV_PLUGIN_MARKET_URL': 'ftp://bad'})['enabled'])
            self.assertEqual(clear_market_url(paths)['source'], 'sdk')
            index.unlink()
            self.assertFalse(load_market_config(paths, environ={})['enabled'])

    def test_invalid_explicit_file_does_not_fall_back_to_sdk(self):
        with tempfile.TemporaryDirectory() as root:
            paths = PluginPaths(env_root=root)
            write_sdk_index(root, [])
            Path(paths.root).mkdir(parents=True)
            Path(paths.root, 'market.json').write_text('{"url": "ftp://bad"}', encoding='utf-8')
            self.assertFalse(load_market_config(paths, environ={})['enabled'])


class SdkIndexTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = self.temporary.name
        self.plugin = index_plugin()
        self.path = write_sdk_index(self.root, [self.plugin])
        self.client = SdkIndexClient(str(self.path), env_root=self.root)

    def assert_market_error(self, call, code='sdk_index_invalid'):
        with self.assertRaises(MarketError) as error:
            call()
        self.assertEqual(error.exception.code, code)

    def test_empty_catalog_and_health(self):
        write_sdk_index(self.root, [])
        self.assertTrue(self.client.health())
        self.assertEqual(self.client.list_plugins()['total'], 0)
        self.assert_market_error(lambda: self.client.plugin_detail('org.unknown.plugin'), 'plugin_not_found')

    def test_catalog_search_sort_pagination_and_reload(self):
        second = index_plugin('org.example.second')
        second.update(name='Another', updated_at='2026-11-05T00:00:00Z')
        write_sdk_index(self.root, [self.plugin, second])
        catalog = self.client.list_plugins(sort='updated', page_size=1)
        self.assertEqual(catalog['total'], 2)
        self.assertEqual(catalog['items'][0]['id'], second['id'])
        self.assertNotIn('versions', catalog['items'][0])
        self.assertEqual(self.client.list_plugins(query='DEMO')['total'], 1)
        self.assertEqual(self.client.list_plugins(query='org.example.second')['total'], 1)
        self.assertEqual(self.client.list_plugins(sort='name')['items'][0]['name'], 'Another')
        self.assertEqual(self.client.list_plugins(sort='downloads')['items'][0]['download_count'], 0)
        self.assertEqual(self.client.list_plugins(page=2, page_size=1)['items'][0]['id'], self.plugin['id'])
        self.assertEqual(self.client.list_plugins(page=3, page_size=1)['items'], [])
        write_sdk_index(self.root, [])
        self.assertEqual(self.client.list_plugins()['total'], 0)
        for kwargs in ({'page': 0}, {'page_size': 101}, {'page': True}, {'sort': 'unknown'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(UsageError):
                self.client.list_plugins(**kwargs)

    def test_resolve_highest_compatible_semantic_version(self):
        first = self.plugin['versions'][0]
        for version in ('1.9.0', '1.10.0-beta.1', '1.10.0', '2.0.0'):
            current = deepcopy(first)
            current['version'] = version
            self.plugin['versions'].append(current)
        self.plugin['versions'][-1]['artifacts'][0]['compatibility']['platforms'] = ['windows']
        write_sdk_index(self.root, [self.plugin])
        with mock.patch('plugins.sdk_index.runtime_profile', return_value=RUNTIME):
            resolved = self.client.resolve(self.plugin['id'])
        self.assertEqual(resolved['artifact']['version'], '1.10.0')
        self.assertEqual(resolved['plugin']['latest_version'], '2.0.0')
        self.assertEqual(resolved['artifact']['download_url'], RELEASE_URL)
        self.assertNotIn('url', resolved['artifact'])
        self.assertNotIn('versions', resolved['plugin'])

    def test_yanked_versions_are_skipped_and_incompatible_is_reported(self):
        newest = deepcopy(self.plugin['versions'][0])
        newest.update(version='2.0.0', status='yanked')
        self.plugin['versions'].append(newest)
        write_sdk_index(self.root, [self.plugin])
        with mock.patch('plugins.sdk_index.runtime_profile', return_value=RUNTIME):
            self.assertEqual(self.client.resolve(self.plugin['id'])['artifact']['version'], '1.0.0')
            self.plugin['versions'][0]['artifacts'][0]['compatibility']['abis'] = ['cp37']
            write_sdk_index(self.root, [self.plugin])
            self.assert_market_error(lambda: self.client.resolve(self.plugin['id']), 'incompatible')
            self.plugin['status'] = 'yanked'
            write_sdk_index(self.root, [self.plugin])
            self.assert_market_error(lambda: self.client.resolve(self.plugin['id']), 'yanked')
            self.plugin['status'] = 'published'
            self.plugin['versions'][0]['status'] = 'yanked'
            write_sdk_index(self.root, [self.plugin])
            self.assert_market_error(lambda: self.client.resolve(self.plugin['id']), 'yanked')

    def test_compiled_abi_artifact_can_be_resolved(self):
        self.plugin['versions'][0]['artifacts'][0]['compatibility']['abis'] = ['cp312']
        write_sdk_index(self.root, [self.plugin])
        with mock.patch('plugins.sdk_index.runtime_profile', return_value=dict(RUNTIME, abi='cp312')):
            self.assertEqual(self.client.resolve(self.plugin['id'])['artifact']['version'], '1.0.0')

    def test_bad_json_missing_file_and_duplicate_keys_fail_closed(self):
        for content in ('{', '[]', '{"version":1,"version":1,"index":[]}', '{"version":true,"index":[]}',
                        '{"version":2,"index":[]}', '{"version":1,"index":"demo"}',
                        ' ' * (1024 * 1024 + 1)):
            with self.subTest(content=content[:80]):
                self.path.write_text(content, encoding='utf-8')
                self.assert_market_error(self.client.health)
        self.path.unlink()
        self.assert_market_error(self.client.health)

    def test_directory_escape_and_duplicates_are_rejected(self):
        for directories in (['..'], ['../outside'], ['/tmp'], ['a/b'], ['a\\b'], [1],
                            [self.plugin['id'], self.plugin['id']]):
            with self.subTest(directories=directories):
                self.path.write_text(json.dumps({'version': 1, 'index': directories}), encoding='utf-8')
                self.assert_market_error(self.client.health)
        write_sdk_index(self.root, [self.plugin])
        other = self.path.parent / 'duplicate'
        other.mkdir()
        (other / 'index.json').write_text(json.dumps(self.plugin), encoding='utf-8')
        self.path.write_text(json.dumps({'version': 1, 'index': [self.plugin['id'], 'duplicate']}), encoding='utf-8')
        self.assert_market_error(self.client.health)

    @unittest.skipIf(os.name == 'nt', 'symlink permissions are host-dependent on Windows')
    def test_symlink_escape_is_rejected(self):
        outside = Path(self.root) / 'outside'
        outside.mkdir()
        (outside / 'index.json').write_text(json.dumps(self.plugin), encoding='utf-8')
        (self.path.parent / 'escape').symlink_to(outside, target_is_directory=True)
        self.path.write_text('{"version": 1, "index": ["escape"]}', encoding='utf-8')
        self.assert_market_error(self.client.health)

    def test_invalid_plugin_and_artifact_metadata(self):
        invalid = []
        for field, value in (('id', '../escape'), ('name', ''), ('versions', []), ('status', 'draft'),
                             ('description', []), ('capabilities', [1]), ('updated_at', {})):
            plugin = deepcopy(self.plugin)
            plugin[field] = value
            invalid.append(plugin)
        for field, value in (('filename', '../plugin.epack'), ('filename', 'plugin.zip'), ('sha256', 'bad'),
                             ('url', 'http://github.com/asset'), ('url', 'file:///tmp/asset'),
                             ('url', 'https://user:secret@github.com/asset'), ('url', 'https://github.com:bad/a'),
                             ('url', 'https://github.com:0/a'), ('url', 'https://github.com/a\n'),
                             ('url', 'https://github.com/a#fragment'), ('size_bytes', True),
                             ('size_bytes', -1), ('size_bytes', 256 * 1024 * 1024 + 1), ('compatibility', {})):
            plugin = deepcopy(self.plugin)
            plugin['versions'][0]['artifacts'][0][field] = value
            invalid.append(plugin)
        for field, value in (('env', '>=99.0.0,bad'), ('python', 42), ('abis', []), ('platforms', 'any')):
            plugin = deepcopy(self.plugin)
            plugin['versions'][0]['artifacts'][0]['compatibility'][field] = value
            invalid.append(plugin)
        for version in ('bad', '1', 'v1.0.0'):
            plugin = deepcopy(self.plugin)
            plugin['versions'][0]['version'] = version
            invalid.append(plugin)
        duplicate = deepcopy(self.plugin)
        duplicate['versions'].append(deepcopy(duplicate['versions'][0]))
        invalid.append(duplicate)
        for plugin in invalid:
            with self.subTest(plugin=plugin):
                write_sdk_index(self.root, [plugin] if plugin['id'] != '../escape' else [])
                (self.path.parent / self.plugin['id'] / 'index.json').write_text(json.dumps(plugin), encoding='utf-8')
                self.path.write_text(json.dumps({'version': 1, 'index': [self.plugin['id']]}), encoding='utf-8')
                self.assert_market_error(self.client.health)

    def test_download_uses_index_network_settings_and_checksum(self):
        destination = os.path.join(self.root, 'download.epack')
        network.NetworkSettings(self.root).save({'proxy_mode': 'direct', 'timeout': 23})
        response = download_response(headers={'Content-Length': '7'})
        with mock.patch('plugins.sdk_index.network.urllib_opener') as make_opener:
            make_opener.return_value.open.return_value = response
            result = self.client.download(hashlib.sha256(b'package').hexdigest(), destination)
        self.assertTrue(response.closed)
        self.assertEqual(Path(destination).read_bytes(), b'package')
        self.assertEqual(result['size_bytes'], 7)
        self.assertEqual(make_opener.call_args.kwargs['env_root'], self.root)
        self.assertEqual(make_opener.return_value.open.call_args.kwargs['timeout'], 23)
        self.assertEqual(make_opener.return_value.open.call_args.args[0].full_url, RELEASE_URL)

    def test_download_errors_remove_temporary_file(self):
        digest = self.plugin['versions'][0]['artifacts'][0]['sha256']
        destination = os.path.join(self.root, 'download.epack')
        for content, headers, code in ((b'tampered', {}, 'checksum_mismatch'),
                                       (b'package', {'X-Checksum-SHA256': '0' * 64}, 'checksum_mismatch'),
                                       (b'package', {'Content-Length': '8'}, 'size_mismatch'),
                                       (b'package', {'Content-Length': 'bad'}, 'market_invalid_response'),
                                       (b'package', {'Content-Length': str(256 * 1024 * 1024 + 1)}, 'payload_too_large')):
            with self.subTest(code=code), mock.patch('plugins.sdk_index.network.urllib_opener') as opener:
                response = download_response(content, headers)
                opener.return_value.open.return_value = response
                self.assert_market_error(lambda: self.client.download(digest, destination), code)
                self.assertFalse(os.path.exists(destination))
                self.assertTrue(response.closed)
        self.plugin['versions'][0]['artifacts'][0]['size_bytes'] = 8
        write_sdk_index(self.root, [self.plugin])
        with mock.patch('plugins.sdk_index.network.urllib_opener') as opener:
            opener.return_value.open.return_value = download_response()
            self.assert_market_error(lambda: self.client.download(digest, destination), 'size_mismatch')
        self.assertFalse(os.path.exists(destination))

    def test_stream_size_limit_is_enforced(self):
        with mock.patch('plugins.sdk_index.network.urllib_opener') as opener, mock.patch('plugins.market.DOWNLOAD_LIMIT', 3):
            opener.return_value.open.return_value = download_response()
            destination = os.path.join(self.root, 'download.epack')
            self.assert_market_error(lambda: self.client.download(
                self.plugin['versions'][0]['artifacts'][0]['sha256'], destination), 'payload_too_large')
        self.assertFalse(os.path.exists(destination))

    def test_download_cannot_request_arbitrary_or_yanked_artifact(self):
        destination = os.path.join(self.root, 'download.epack')
        with mock.patch('plugins.sdk_index.network.urllib_opener') as opener:
            self.assert_market_error(lambda: self.client.download('0' * 64, destination), 'artifact_not_found')
            self.plugin['status'] = 'yanked'
            write_sdk_index(self.root, [self.plugin])
            self.assert_market_error(lambda: self.client.download(
                self.plugin['versions'][0]['artifacts'][0]['sha256'], destination), 'artifact_not_found')
            opener.assert_not_called()

    def test_network_failure_redacts_url_credentials_and_signed_query(self):
        destination = os.path.join(self.root, 'download.epack')
        for failure in (URLError('secret signed URL'), HTTPError(RELEASE_URL, 403, 'secret', {}, None)):
            with mock.patch('plugins.sdk_index.network.urllib_opener') as opener:
                opener.return_value.open.side_effect = failure
                with self.assertRaises(MarketError) as error:
                    self.client.download(self.plugin['versions'][0]['artifacts'][0]['sha256'], destination)
                self.assertNotIn('secret', str(error.exception))
                self.assertEqual(error.exception.code, 'market_unreachable')

    def test_http_market_retains_same_origin_redirect_rule_and_stream_checks(self):
        client = MarketClient('https://market.example', env_root=self.root)
        destination = os.path.join(self.root, 'http.epack')
        digest = hashlib.sha256(b'package').hexdigest()
        with mock.patch.object(client, '_open', return_value=download_response()):
            self.assertEqual(client.download(digest, destination)['size_bytes'], 7)
        self.assertEqual(Path(destination).read_bytes(), b'package')
        from plugins.market import _OriginRedirectHandler
        with self.assertRaises(MarketError):
            _OriginRedirectHandler('https://market.example').redirect_request(
                Request('https://market.example/a'), None, 302, '', {}, RELEASE_URL)


class ReleaseRedirectTest(unittest.TestCase):
    def test_github_release_redirects_to_explicit_asset_hosts(self):
        handler = ReleaseRedirectHandler(RELEASE_URL)
        request = Request(RELEASE_URL)
        for url in (RELEASE_URL, 'https://release-assets.githubusercontent.com/asset?signature=value',
                    'https://objects.githubusercontent.com/asset', 'https://github-releases.githubusercontent.com/asset'):
            with self.subTest(url=url):
                redirected = handler.redirect_request(request, None, 302, '', {}, url)
                self.assertEqual(redirected.full_url, url)

    def test_cross_origin_and_downgrade_redirects_are_rejected(self):
        handler = ReleaseRedirectHandler(RELEASE_URL)
        for url in ('http://github.com/file', 'file:///tmp/file', 'https://evil.example/file',
                    'https://release-assets.githubusercontent.com.evil.example/file',
                    'https://user:secret@release-assets.githubusercontent.com/file',
                    'https://release-assets.githubusercontent.com:444/file'):
            with self.subTest(url=url), self.assertRaises(MarketError):
                handler.redirect_request(Request(RELEASE_URL), None, 302, '', {}, url)
        with self.assertRaises(MarketError):
            ReleaseRedirectHandler('https://example.com/file').redirect_request(
                Request('https://example.com/file'), None, 302, '', {},
                'https://release-assets.githubusercontent.com/file')


if __name__ == '__main__':
    unittest.main()

from copy import deepcopy
from http.cookiejar import CookieJar
from pathlib import Path
import json
import os
import tempfile
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, build_opener

from plugins.tests.helpers import build_example
from plugins.tests.test_sdk_index import download_response, index_plugin, write_sdk_index
from plugins.tests import test_webui_server as webui_helpers
from plugins.webui.server import WebUIServer


class SdkMarketWebUITest(unittest.TestCase):
    request_json = webui_helpers.WebUIServerTest.request_json
    authenticate = webui_helpers.WebUIServerTest.authenticate
    tearDown = webui_helpers.WebUIServerTest.tearDown

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self._market_env = mock.patch.dict(os.environ, {'ENV_PLUGIN_MARKET_URL': ''})
        self._market_env.start()
        self.env_root = os.path.join(self.temporary.name, 'env')
        package = build_example('1.0.0', self.temporary.name)
        self.content = Path(package).read_bytes()
        self.plugin_id = 'org.rt-thread.examples.hello'
        self.plugin = index_plugin(self.plugin_id, self.content)
        self.index = write_sdk_index(self.env_root, [self.plugin])
        self.server = WebUIServer(
            env_root=self.env_root, workspace=self.temporary.name,
            launcher_dir=os.path.join(self.temporary.name, 'launchers'),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = self.server.url.rstrip('/')
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def prepare(self, content=None):
        with mock.patch('plugins.sdk_index.network.urllib_opener') as opener:
            opener.return_value.open.return_value = download_response(self.content if content is None else content)
            return self.request_json('/api/v1/market/plugins/%s/prepare' % self.plugin_id, method='POST', body={})[1]

    def assert_empty_staging(self):
        self.assertEqual(os.listdir(self.server.application.service.paths.staging), [])
        self.assertEqual(self.server.application.uploads, {})

    def test_session_catalog_detail_and_offline_index_health(self):
        session = self.authenticate()
        self.assertEqual(session['market'], {'enabled': True, 'source': 'sdk', 'url': str(self.index)})
        _, catalog = self.request_json('/api/v1/market/plugins?q=demo&sort=name')
        self.assertEqual(catalog['total'], 1)
        self.assertEqual(catalog['items'][0]['action'], 'install')
        _, detail = self.request_json('/api/v1/market/plugins/' + self.plugin_id)
        self.assertTrue(detail['compatible'])
        self.assertEqual(detail['diagnosis']['reason_code'], 'ok')
        self.assertNotIn('download_url', detail['resolved']['artifact'])
        self.assertNotIn('download_url', detail['versions'][0]['artifacts'][0])
        self.assertNotIn('url', detail['versions'][0]['artifacts'][0])
        with mock.patch('plugins.sdk_index.network.urllib_opener') as opener:
            _, status = self.request_json('/api/v1/market/status')
            self.assertTrue(status['reachable'])
            _, result = self.request_json('/api/v1/settings/network/test', method='POST', body={'target': 'market'})
            self.assertTrue(result['reachable'])
            self.assertIsNone(result['status'])
            opener.assert_not_called()

    def test_prepare_install_upgrade_and_compatible_version_action(self):
        self.authenticate()
        prepared = self.prepare()
        self.assertEqual(prepared['version'], '1.0.0')
        self.assertEqual(prepared['signing_status'], 'unsigned')
        _, installed = self.request_json('/api/v1/plugins/install', method='POST', body={
            'upload_id': prepared['upload_id'], 'allow_unsigned': True,
        })
        self.assertEqual(installed['id'], self.plugin_id)
        upgraded_package = build_example('1.1.0', self.temporary.name)
        upgraded_content = Path(upgraded_package).read_bytes()
        self.plugin['versions'].append(index_plugin(self.plugin_id, upgraded_content, '1.1.0')['versions'][0])
        write_sdk_index(self.env_root, [self.plugin])
        _, detail = self.request_json('/api/v1/market/plugins/' + self.plugin_id)
        self.assertEqual(detail['action'], 'upgrade')
        self.assertEqual(detail['resolved']['version'], '1.1.0')
        prepared = self.prepare(upgraded_content)
        _, installed = self.request_json('/api/v1/plugins/%s/upgrade' % self.plugin_id, method='POST', body={
            'upload_id': prepared['upload_id'], 'allow_unsigned': True,
        })
        self.assertEqual(installed['version'], '1.1.0')
        incompatible = deepcopy(self.plugin['versions'][-1])
        incompatible['version'] = '9.0.0'
        incompatible['artifacts'][0]['compatibility']['env'] = '>=99.0.0'
        self.plugin['versions'].append(incompatible)
        write_sdk_index(self.env_root, [self.plugin])
        _, detail = self.request_json('/api/v1/market/plugins/' + self.plugin_id)
        self.assertEqual(detail['latest_version'], '9.0.0')
        self.assertEqual(detail['resolved']['version'], '1.1.0')
        self.assertEqual(detail['action'], 'installed')
        self.assert_empty_staging()

    def test_unsigned_install_still_requires_explicit_consent(self):
        self.authenticate()
        prepared = self.prepare()
        with self.assertRaises(HTTPError) as error:
            self.request_json('/api/v1/plugins/install', method='POST', body={
                'upload_id': prepared['upload_id'], 'allow_unsigned': False,
            })
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.server.application.service.list(), [])

    def test_checksum_mismatch_removes_download_and_never_registers_upload(self):
        self.authenticate()
        with self.assertRaises(HTTPError) as error:
            self.prepare(b'tampered')
        payload = json.loads(error.exception.read())
        self.assertEqual(payload['error']['code'], 'checksum_mismatch')
        self.assertEqual(payload['error']['details']['stage'], 'download')
        self.assert_empty_staging()

    def test_package_id_and_version_must_match_index(self):
        self.authenticate()
        for mismatch in ('id', 'version'):
            with self.subTest(mismatch=mismatch):
                plugin = deepcopy(self.plugin)
                if mismatch == 'id':
                    plugin['id'] = 'org.example.impostor'
                else:
                    plugin['versions'][0]['version'] = '2.0.0'
                write_sdk_index(self.env_root, [plugin])
                original_id = self.plugin_id
                self.plugin_id = plugin['id']
                try:
                    with self.assertRaises(HTTPError) as error:
                        self.prepare()
                finally:
                    self.plugin_id = original_id
                self.assertEqual(json.loads(error.exception.read())['error']['code'], 'invalid_package')
                self.assert_empty_staging()

    def test_invalid_index_is_reported_and_can_be_repaired_without_restart(self):
        self.authenticate()
        self.index.write_text('{', encoding='utf-8')
        _, status = self.request_json('/api/v1/market/status')
        self.assertFalse(status['reachable'])
        with self.assertRaises(HTTPError) as error:
            self.request_json('/api/v1/market/plugins')
        self.assertEqual(error.exception.code, 502)
        self.assertEqual(json.loads(error.exception.read())['error']['code'], 'sdk_index_invalid')
        write_sdk_index(self.env_root, [self.plugin])
        _, catalog = self.request_json('/api/v1/market/plugins')
        self.assertEqual(catalog['total'], 1)


if __name__ == '__main__':
    unittest.main()

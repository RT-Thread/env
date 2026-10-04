import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import env_venv
import network
from plugins.market import MarketClient
from plugins.webui.server import WebUIServer


class ProxyHandler(BaseHTTPRequestHandler):
    paths = []

    def do_GET(self):
        self.paths.append(self.path)
        if self.path == 'http://target.invalid/redirect':
            self.send_response(302)
            self.send_header('Location', 'http://127.0.0.1:%d/redirected' % self.server.server_address[1])
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        content = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *args):
        pass


class NetworkSettingsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = self.temporary.name
        self.environment = mock.patch.dict(os.environ, {'ENV_ROOT': self.root, 'ENV_PYPI_INDEX_URL': ''})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.policy = network.NetworkSettings(self.root)

    def test_defaults_and_atomic_persistence(self):
        self.assertFalse(self.policy.snapshot()['configured'])
        saved = self.policy.save({'proxy_mode': 'direct', 'timeout': 37})
        self.assertTrue(saved['configured'])
        self.assertEqual(network.NetworkSettings(self.root).load()['timeout'], 37)
        self.assertEqual(self.policy.timeout(15), 37)
        self.assertEqual(sorted(Path(self.policy.config_path).parent.iterdir()), [Path(self.policy.config_path)])

    def test_invalid_settings_do_not_replace_saved_configuration(self):
        self.policy.save({'proxy_mode': 'direct'})
        original = Path(self.policy.config_path).read_bytes()
        for invalid in (
            {'proxy_mode': 'invalid'}, {'proxy_mode': 'custom'},
            {'proxy_url': 'http://user:secret@proxy.invalid'}, {'proxy_url': 'http://host:0'},
            {'proxy_url': 'http://host:65536'}, {'proxy_url': 'http://host/path'},
            {'pypi_mode': 'custom'}, {'pypi_url': 'https://host/simple/?secret=x'},
            {'timeout': True}, {'timeout': 0}, {'timeout': 301}, {'timeout': 1.5},
            {'no_proxy': 'host\nother'}, {'unexpected': True},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(network.NetworkConfigError):
                self.policy.save(invalid)
            self.assertEqual(Path(self.policy.config_path).read_bytes(), original)

    def test_invalid_json_fails_without_silently_using_other_settings(self):
        self.policy.save({})
        Path(self.policy.config_path).write_text('{', encoding='ascii')
        with self.assertRaises(network.NetworkConfigError):
            self.policy.load()

    def test_child_environment_does_not_modify_global_configuration(self):
        original = {'PATH': 'bin', 'HTTP_PROXY': 'http://old.invalid', 'GIT_CONFIG_COUNT': '1',
                    'GIT_CONFIG_KEY_0': 'http.sslVerify', 'GIT_CONFIG_VALUE_0': 'true'}
        self.policy.save({'proxy_mode': 'custom', 'proxy_url': 'http://127.0.0.1:7890', 'timeout': 42})
        environment = network.subprocess_environment(original, self.root)
        self.assertEqual(original['HTTP_PROXY'], 'http://old.invalid')
        self.assertEqual(environment['HTTPS_PROXY'], 'http://127.0.0.1:7890')
        self.assertEqual(environment['GIT_CONFIG_COUNT'], '2')
        self.assertEqual(environment['GIT_CONFIG_VALUE_1'], 'http://127.0.0.1:7890')
        self.assertEqual(environment['GIT_CONFIG_VALUE_0'], 'true')
        self.assertEqual(environment['PIP_DEFAULT_TIMEOUT'], '42')
        self.assertIn('127.0.0.1', environment['NO_PROXY'])
        self.policy.save({'proxy_mode': 'direct'})
        environment = network.subprocess_environment(original, self.root)
        self.assertNotIn('HTTP_PROXY', environment)
        self.assertEqual(environment['GIT_CONFIG_VALUE_1'], '')
        self.assertEqual(environment['PIP_PROXY'], '')

    def test_pypi_setting_and_environment_precedence(self):
        self.policy.save({'pypi_mode': 'custom', 'pypi_url': 'https://index.invalid/simple/'})
        detector = mock.Mock(side_effect=AssertionError('must not detect the country'))
        self.assertEqual(env_venv.select_index_url(detector, env_root=self.root), 'https://index.invalid/simple/')
        self.assertEqual(network.pypi_index_url(self.root, {'ENV_PYPI_INDEX_URL': 'https://override.invalid'}),
                         'https://override.invalid')
        self.policy.save({'pypi_mode': 'default'})
        self.assertIsNone(env_venv.select_index_url(detector, env_root=self.root))

    def test_bootstrap_honors_explicit_system_proxy(self):
        self.policy.save({'proxy_mode': 'system'})
        with mock.patch.dict(os.environ, {'HTTP_PROXY': 'http://proxy.invalid'}):
            with mock.patch('env_venv.subprocess.check_call') as check_call:
                env_venv.run_command(['python', '--version'])
        self.assertEqual(check_call.call_args.kwargs['env']['HTTP_PROXY'], 'http://proxy.invalid')
        self.assertNotIn('--proxy', env_venv._pip_network_arguments(None, self.root))

    def test_requests_and_urllib_use_proxy_and_bypass_loopback(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), ProxyHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(lambda: thread.join(timeout=2))
        self.addCleanup(server.shutdown)
        url = 'http://127.0.0.1:%d' % server.server_address[1]
        ProxyHandler.paths = []
        self.policy.save({'proxy_mode': 'custom', 'proxy_url': url})
        with network.request('GET', 'http://target.invalid/request', env_root=self.root) as response:
            self.assertEqual(response.json()['status'], 'ok')
        with network.urllib_opener(env_root=self.root).open('http://target.invalid/urllib') as response:
            self.assertIn(b'ok', response.read())
        with network.request('GET', 'http://target.invalid/redirect', env_root=self.root) as response:
            self.assertEqual(response.status_code, 200)
        self.policy.save({'proxy_mode': 'custom', 'proxy_url': 'http://127.0.0.1:1'})
        with network.request('GET', url + '/direct', env_root=self.root) as response:
            self.assertEqual(response.status_code, 200)
        with network.urllib_opener(env_root=self.root).open(url + '/direct-urllib') as response:
            self.assertEqual(response.status, 200)
        self.assertEqual(ProxyHandler.paths, ['http://target.invalid/request', 'http://target.invalid/urllib',
                                            'http://target.invalid/redirect', '/redirected',
                                            '/direct', '/direct-urllib'])

    def test_running_market_client_refreshes_network_policy(self):
        client = MarketClient('https://market.invalid', env_root=self.root)
        previous = client.opener
        self.policy.save({'proxy_mode': 'direct', 'timeout': 23})
        with mock.patch('network.urllib_opener') as make_opener:
            response = mock.Mock()
            make_opener.return_value.open.return_value = response
            self.assertIs(client._open('/api/v1/health'), response)
            self.assertIsNot(client.opener, previous)
            self.assertEqual(client.opener.open.call_args.kwargs['timeout'], 23)


class NetworkWebUITest(unittest.TestCase):
    def setUp(self):
        from plugins.tests import test_webui_server

        self.helpers = test_webui_server.WebUIServerTest
        self.helpers.setUp(self)
        self.helpers.authenticate(self)

    def tearDown(self):
        self.helpers.tearDown(self)

    def request_json(self, *args, **kwargs):
        return self.helpers.request_json(self, *args, **kwargs)

    def test_save_reload_and_csrf(self):
        from urllib.error import HTTPError

        path = '/api/v1/settings/network'
        _, original = self.request_json(path)
        self.assertFalse(original['configured'])
        with self.assertRaises(HTTPError) as denied:
            self.request_json(path, method='PUT', body={'proxy_mode': 'direct'}, csrf=False)
        self.assertEqual(denied.exception.code, 403)
        _, saved = self.request_json(path, method='PUT', body={'proxy_mode': 'direct', 'timeout': 37})
        _, loaded = self.request_json(path)
        self.assertEqual(saved, loaded)
        self.assertEqual(loaded['settings']['timeout'], 37)
        with self.assertRaises(HTTPError) as invalid:
            self.request_json(path, method='PUT', body={'timeout': 0})
        self.assertEqual(invalid.exception.code, 400)

    def test_connection_test_uses_saved_configuration_and_redacts_failures(self):
        from urllib.error import HTTPError

        path = '/api/v1/settings/network/test'
        response = mock.Mock(status_code=200)
        with mock.patch('network.request', return_value=response) as request:
            _, result = self.request_json(path, method='POST', body={'target': 'github'})
        self.assertTrue(result['reachable'])
        self.assertEqual(request.call_args.kwargs['env_root'], self.server.application.network.env_root)
        response.close.assert_called_once()
        with mock.patch('network.request', side_effect=OSError('secret http://user:password@proxy')):
            _, result = self.request_json(path, method='POST', body={'target': 'github'})
        self.assertFalse(result['reachable'])
        self.assertNotIn('password', json.dumps(result))
        with self.assertRaises(HTTPError) as invalid:
            self.request_json(path, method='POST', body={'target': 'http://arbitrary.invalid'})
        self.assertEqual(invalid.exception.code, 400)


if __name__ == '__main__':
    unittest.main()

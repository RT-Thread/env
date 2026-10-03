import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from plugins.epack import cli as epack_cli
from plugins.epack import tester
from plugins.epack.builder import build_project
from plugins.epack.publisher import push_package
from plugins.errors import UsageError
from plugins.market import MarketError
from plugins.service import PluginService
from plugins.tests.helpers import EXAMPLES, build_epack_plugin


class MarketHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not self.path.startswith('/api/v1/plugins/org.rt-thread.examples.hello'):
            self.send_error(404)
            return
        if self.server.mode == 'plugin':
            self.send_error(404)
            return
        versions = [] if self.server.mode == 'version' else [{'version': '1.0.0'}]
        payload = json.dumps({'versions': versions}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        size = int(self.headers['Content-Length'])
        self.server.upload = {
            'path': self.path,
            'authorization': self.headers.get('Authorization'),
            'content_type': self.headers['Content-Type'],
            'body': self.rfile.read(size),
        }
        if self.server.reject:
            status, payload = 401, {'detail': 'invalid token'}
        else:
            status, payload = 201, {'status': 'published'}
        content = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        pass


class EpackWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        project = os.path.join(EXAMPLES, 'hello-1.0.0')
        self.package = build_project(project, output_directory=self.temporary.name)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), MarketHandler)
        self.server.mode = 'plugin'
        self.server.reject = False
        self.server.upload = None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:%d' % self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def test_push_selects_market_admin_endpoints_and_sends_package(self):
        expected = {
            'plugin': ('/api/v1/admin/plugins', 'plugin'),
            'version': ('/api/v1/admin/plugins/org.rt-thread.examples.hello/versions', 'version'),
            'artifact': (
                '/api/v1/admin/plugins/org.rt-thread.examples.hello/versions/1.0.0/artifacts',
                'artifact',
            ),
        }
        for mode, (path, action) in expected.items():
            self.server.mode = mode
            result = push_package(self.package, self.url, token='test-token')
            self.assertEqual(result['action'], action)
            upload = self.server.upload
            self.assertEqual(upload['path'], path)
            self.assertEqual(upload['authorization'], 'Bearer test-token')
            self.assertIn('multipart/form-data', upload['content_type'])
            with open(self.package, 'rb') as source:
                self.assertIn(source.read(), upload['body'])

    def test_push_cli_sends_changelog_and_handles_market_error(self):
        token_file = os.path.join(self.temporary.name, 'token.txt')
        with open(token_file, 'w', encoding='utf-8') as output:
            output.write('from-file\n')
        self.assertEqual(
            epack_cli.run([
                'push', self.package, '--market', self.url, '--token-file', token_file,
                '--changelog', 'First release',
            ]), 0
        )
        self.assertIn(b'First release', self.server.upload['body'])
        self.assertEqual(self.server.upload['authorization'], 'Bearer from-file')
        self.assertEqual(epack_cli.run(['publish', self.package, '--market', self.url]), 0)
        self.server.reject = True
        with self.assertRaisesRegex(MarketError, 'invalid token'):
            push_package(self.package, self.url)

    def test_test_command_executes_from_temporary_install(self):
        project = os.path.join(EXAMPLES, 'hello-1.0.0')
        with mock.patch('plugins.launchers.shutil.which', return_value='/some/installed/launcher'):
            self.assertEqual(epack_cli.run(['test', project]), 0)

    def test_test_webui_opens_plugin_and_cleans_temporary_install(self):
        project = os.path.join(EXAMPLES, 'build-insight-1.0.0')
        package = build_project(project, output_directory=self.temporary.name)
        observed = {}

        class FakeWebUI(object):
            def __init__(self, **kwargs):
                observed.update(kwargs)
                self.url = 'http://127.0.0.1:8000/'
                self.launch_url = self.url + '_launch/test'

            def serve_forever(self):
                observed['installed'] = os.path.isdir(observed['env_root'])

            def shutdown(self):
                observed['shutdown'] = True

        with mock.patch('plugins.webui.server.WebUIServer', FakeWebUI), mock.patch.object(
            tester.webbrowser, 'open', return_value=True
        ) as browser:
            self.assertEqual(tester.test_package(package, project), 0)
        self.assertEqual(observed['plugin_id'], 'org.rt-thread.build-insight')
        self.assertEqual(observed['host'], '127.0.0.1')
        self.assertTrue(observed['installed'])
        self.assertTrue(observed['shutdown'])
        self.assertFalse(os.path.exists(observed['env_root']))
        browser.assert_called_once_with('http://127.0.0.1:8000/_launch/test')

    def test_test_global_aliases_bind_webui_on_all_interfaces(self):
        project = os.path.join(EXAMPLES, 'build-insight-1.0.0')
        observed = []

        class FakeWebUI(object):
            def __init__(self, **kwargs):
                observed.append(kwargs)
                self.url = 'http://127.0.0.1:8000/'
                self.launch_url = self.url + '_launch/test'

            def serve_forever(self):
                pass

            def shutdown(self):
                pass

        with mock.patch('plugins.webui.server.WebUIServer', FakeWebUI), mock.patch.object(
            tester.webbrowser, 'open'
        ) as browser:
            for option in ('-g', '--global'):
                with self.subTest(option=option):
                    self.assertEqual(epack_cli.run(['test', project, option, '--no-browser']), 0)

        self.assertEqual([entry['host'] for entry in observed], ['0.0.0.0', '0.0.0.0'])
        browser.assert_not_called()

    def test_test_rejects_missing_command(self):
        with self.assertRaisesRegex(UsageError, 'does not provide command'):
            tester.test_package(self.package, self.temporary.name, command='missing')

    def test_installed_epack_launcher_can_push_package(self):
        import subprocess

        env_root = os.path.join(self.temporary.name, 'env')
        launcher_dir = os.path.join(self.temporary.name, 'bin')
        official = build_epack_plugin(self.temporary.name)
        service = PluginService(env_root=env_root, launcher_dir=launcher_dir)
        service.install(official, allow_unsigned=True)
        launcher = service.installer.launchers.path('epack')
        token_file = os.path.join(self.temporary.name, 'market-token.txt')
        with open(token_file, 'w', encoding='utf-8') as output:
            output.write('launcher-token\n')
        environment = dict(os.environ)
        environment['ENV_ROOT'] = env_root
        process = subprocess.run(
            [launcher, 'push', os.path.basename(self.package), '--market', self.url,
             '--token-file', os.path.basename(token_file)],
            cwd=self.temporary.name, env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(self.server.upload['authorization'], 'Bearer launcher-token')


if __name__ == '__main__':
    unittest.main()

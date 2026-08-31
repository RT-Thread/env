import argparse
from http.cookiejar import CookieJar
from http.client import HTTPConnection
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from cmds import cmd_webui
import env as env_module
from plugins.epack.builder import build_project
from plugins.tests.helpers import EXAMPLES, copy_project, update_manifest
from plugins.webui.server import PACKAGE_LIMIT, WebUIServer


REPOSITORY = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_SCRIPT = os.path.join(REPOSITORY, 'env.py')


class WebUIServerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self._market_env = mock.patch.dict(os.environ, {'ENV_PLUGIN_MARKET_URL': ''}, clear=False)
        self._market_env.start()
        os.environ.pop('ENV_PLUGIN_MARKET_URL', None)
        self.server = WebUIServer(
            env_root=os.path.join(self.temporary.name, 'env'),
            workspace=self.temporary.name,
            launcher_dir=os.path.join(self.temporary.name, 'launchers'),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = self.server.url.rstrip('/')
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self._market_env.stop()
        self.temporary.cleanup()

    def request_json(self, path, method='GET', body=None, csrf=True):
        headers = {}
        data = None
        if body is not None:
            data = json.dumps(body).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        if method != 'GET':
            headers['Origin'] = self.origin
            headers['Sec-Fetch-Site'] = 'same-origin'
            if csrf:
                headers['X-Env-CSRF'] = self.csrf
        request = Request(self.server.url + path.lstrip('/'), data=data, headers=headers, method=method)
        with self.opener.open(request) as response:
            return response.status, json.loads(response.read().decode('utf-8'))['data']

    def authenticate(self):
        with self.opener.open(self.server.launch_url) as response:
            self.assertIn('RT-Thread Env', response.read().decode('utf-8'))
        _, session = self.request_json('/api/v1/session')
        self.csrf = session['csrf_token']
        return session

    def upload_package(self, package, filename=None):
        with open(package, 'rb') as source:
            content = source.read()
        request = Request(
            self.server.url + 'api/v1/packages',
            data=content,
            headers={
                'Content-Type': 'application/vnd.rt-thread.epack',
                'X-Filename': filename or os.path.basename(package),
                'Origin': self.origin,
                'Sec-Fetch-Site': 'same-origin',
                'X-Env-CSRF': self.csrf,
            },
            method='POST',
        )
        with self.opener.open(request) as response:
            return json.loads(response.read().decode('utf-8'))['data']

    def test_session_csrf_and_local_package_lifecycle(self):
        with self.assertRaises(HTTPError) as unauthenticated:
            urlopen(self.server.url + 'api/v1/session')
        self.assertEqual(unauthenticated.exception.code, 401)
        session = self.authenticate()
        self.assertEqual(session['frontend_sdk'], '1.0.0')
        self.assertTrue(session['plugin_asset_base'].startswith('/plugin-assets/'))
        self.assertEqual(session['market'], {'enabled': False, 'url': '', 'source': None})

        package = os.path.join(
            REPOSITORY,
            'plugins',
            'examples',
            'prebuilt',
            'org.rt-thread.build-insight-1.0.0-py3-none-any.epack',
        )
        build = self.upload_package(package)
        self.assertEqual(build['author']['name'], 'RT-Thread')
        self.assertIn('build output', build['description'])
        self.assertEqual(build['compatibility_issues'], [])
        with self.assertRaises(HTTPError) as denied:
            self.request_json(
                '/api/v1/plugins/install',
                method='POST',
                body={'upload_id': build['upload_id'], 'allow_unsigned': True},
                csrf=False,
            )
        self.assertEqual(denied.exception.code, 403)

        status, installed = self.request_json(
            '/api/v1/plugins/install',
            method='POST',
            body={'upload_id': build['upload_id'], 'allow_unsigned': True},
        )
        self.assertEqual(status, 201)
        self.assertEqual(installed['id'], build['id'])
        _, plugins = self.request_json('/api/v1/plugins')
        self.assertEqual(len(plugins), 1)
        self.assertEqual(plugins[0]['compatibility_issues'], [])
        with self.opener.open(self.server.url + 'plugins/org.rt-thread.build-insight/') as response:
            self.assertIn('固件构建分析', response.read().decode('utf-8'))
        asset_url = (
            self.server.url
            + session['plugin_asset_base'].lstrip('/')
            + 'org.rt-thread.build-insight/styles.css'
        )
        with urlopen(asset_url) as response:
            self.assertIn(':root', response.read().decode('utf-8'))

        self.request_json(
            '/api/v1/plugins/org.rt-thread.build-insight/permissions',
            method='PUT',
            body={'permissions': ['process.execute']},
        )
        with self.assertRaises(HTTPError) as missing_permission:
            self.opener.open(self.server.url + 'plugins/org.rt-thread.build-insight/')
        self.assertEqual(missing_permission.exception.code, 409)
        self.request_json(
            '/api/v1/plugins/org.rt-thread.build-insight/permissions',
            method='PUT',
            body={'permissions': ['workspace.read', 'process.execute']},
        )
        upgrade_project = copy_project(
            os.path.join(EXAMPLES, 'build-insight-1.0.0'),
            os.path.join(self.temporary.name, 'build-insight-1.1.0'),
        )
        update_manifest(upgrade_project, lambda data: data.update({'version': '1.1.0'}))
        upgrade_package = build_project(upgrade_project, os.path.join(self.temporary.name, 'packages'))
        upgrade = self.upload_package(upgrade_package)
        _, upgraded = self.request_json(
            '/api/v1/plugins/org.rt-thread.build-insight/upgrade',
            method='POST',
            body={'upload_id': upgrade['upload_id'], 'allow_unsigned': True},
        )
        self.assertEqual(upgraded['version'], '1.1.0')
        _, diagnosis = self.request_json('/api/v1/plugins/org.rt-thread.build-insight/doctor')
        self.assertEqual(diagnosis['status'], 'ok')
        self.request_json(
            '/api/v1/plugins/org.rt-thread.build-insight/enabled',
            method='PUT',
            body={'enabled': False},
        )
        _, disabled = self.request_json('/api/v1/plugins/org.rt-thread.build-insight')
        self.assertFalse(disabled['enabled'])
        self.request_json('/api/v1/plugins/org.rt-thread.build-insight?purge_data=false', method='DELETE')
        _, plugins = self.request_json('/api/v1/plugins')
        self.assertEqual(plugins, [])

    def test_local_upload_installs_cli_only_plugin(self):
        self.authenticate()
        package = build_project(
            os.path.join(EXAMPLES, 'probe-flash-0.9.6'),
            os.path.join(self.temporary.name, 'probe-packages'),
        )
        summary = self.upload_package(package, 'probe-flash.epack')
        _, installed = self.request_json(
            '/api/v1/plugins/install',
            method='POST',
            body={'upload_id': summary['upload_id'], 'allow_unsigned': True},
        )
        self.assertEqual(installed['id'], 'org.rt-thread.probe-flash')
        self.assertIsNone(installed['webui'])

    def test_catalog_and_remote_package_sources_are_rejected(self):
        self.authenticate()
        with self.assertRaises(HTTPError) as catalog:
            self.request_json('/api/v1/catalog')
        self.assertEqual(catalog.exception.code, 404)

        for body in (
            {'plugin_id': 'org.rt-thread.build-insight', 'allow_unsigned': True},
            {'url': 'https://plugins.example.invalid/example.epack', 'allow_unsigned': True},
        ):
            with self.subTest(body=body):
                with self.assertRaises(HTTPError) as rejected:
                    self.request_json('/api/v1/plugins/install', method='POST', body=body)
                self.assertEqual(rejected.exception.code, 400)

        for path in (
            '/api/v1/market/status',
            '/api/v1/market/plugins',
            '/api/v1/market/plugins/org.example.hello',
        ):
            with self.subTest(path=path):
                with self.assertRaises(HTTPError) as missing:
                    self.request_json(path)
                self.assertEqual(missing.exception.code, 404)

    def test_configured_market_is_proxied_and_prepared(self):
        package = os.path.join(
            REPOSITORY,
            'plugins',
            'examples',
            'prebuilt',
            'org.rt-thread.build-insight-1.0.0-py3-none-any.epack',
        )
        with open(package, 'rb') as source:
            content = source.read()
        digest = hashlib.sha256(content).hexdigest()
        catalog = {
            'items': [
                {
                    'id': 'org.rt-thread.build-insight',
                    'name': 'Build Insight',
                    'description': 'build output',
                    'latest_version': '1.0.0',
                    'download_count': 3,
                    'capabilities': ['webui'],
                    'status': 'published',
                }
            ],
            'page': 1,
            'page_size': 20,
            'total': 1,
        }
        detail = dict(catalog['items'][0])
        detail['versions'] = [
            {
                'version': '1.0.0',
                'artifacts': [
                    {
                        'id': digest,
                        'sha256': digest,
                        'version': '1.0.0',
                        'filename': os.path.basename(package),
                        'download_url': '/api/v1/artifacts/%s/download' % digest,
                        'compatibility': {
                            'env': '>=2.0.2,<3.0.0',
                            'python': '>=3.6.0,<4.0.0',
                            'implementations': ['cpython'],
                            'abis': ['py3'],
                            'platforms': ['any'],
                            'architectures': ['any'],
                        },
                    }
                ],
            }
        ]
        resolved = {
            'plugin': catalog['items'][0],
            'artifact': detail['versions'][0]['artifacts'][0],
        }

        class FakeMarket(object):
            def __init__(self, *args, **kwargs):
                pass

            def health(self):
                return True

            def list_plugins(self, query=None, sort='updated', page=1, page_size=20):
                self.query = query
                self.sort = sort
                return catalog

            def plugin_detail(self, plugin_id):
                self.plugin_id = plugin_id
                return detail

            def resolve(self, plugin_id):
                self.resolved_id = plugin_id
                return resolved

            def download(self, sha256, destination, filename=None):
                with open(destination, 'wb') as output:
                    output.write(content)
                return {'path': destination, 'sha256': sha256, 'filename': filename}

        env_root = os.path.join(self.temporary.name, 'market-env')
        os.makedirs(os.path.join(env_root, 'var', 'plugins'), exist_ok=True)
        with open(os.path.join(env_root, 'var', 'plugins', 'market.json'), 'w', encoding='utf-8') as output:
            output.write('{"url": "http://127.0.0.1:8800"}\n')
        self.server.shutdown()
        self.thread.join(timeout=2)
        with mock.patch('plugins.webui.server.MarketClient', FakeMarket):
            self.server = WebUIServer(
                env_root=env_root,
                workspace=self.temporary.name,
                launcher_dir=os.path.join(self.temporary.name, 'market-launchers'),
            )
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            self.origin = self.server.url.rstrip('/')
            self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
            session = self.authenticate()
            self.assertTrue(session['market']['enabled'])
            self.assertEqual(session['market']['url'], 'http://127.0.0.1:8800')
            _, status = self.request_json('/api/v1/market/status')
            self.assertTrue(status['reachable'])
            _, plugins = self.request_json('/api/v1/market/plugins?q=build&sort=downloads')
            self.assertEqual(plugins['items'][0]['action'], 'install')
            _, item = self.request_json('/api/v1/market/plugins/org.rt-thread.build-insight')
            self.assertTrue(item['compatible'])
            self.assertIn('diagnosis', item)
            self.assertEqual(item['diagnosis']['reason_code'], 'ok')
            self.assertNotIn('download_url', item['versions'][0]['artifacts'][0])
            _, prepared = self.request_json(
                '/api/v1/market/plugins/org.rt-thread.build-insight/prepare',
                method='POST',
                body={},
            )
            self.assertEqual(prepared['id'], 'org.rt-thread.build-insight')
            self.assertTrue(prepared['upload_id'])
            _, installed = self.request_json(
                '/api/v1/plugins/install',
                method='POST',
                body={'upload_id': prepared['upload_id'], 'allow_unsigned': True},
            )
            self.assertEqual(installed['id'], 'org.rt-thread.build-insight')

    def test_launch_token_is_one_time(self):
        self.authenticate()
        with self.assertRaises(HTTPError) as repeated:
            build_opener(HTTPCookieProcessor(CookieJar())).open(self.server.launch_url)
        self.assertEqual(repeated.exception.code, 401)

    def test_launch_target_redirects_to_plugin_view(self):
        self.server.application.initial_plugin = 'org.example.build-insight'
        with self.opener.open(self.server.launch_url) as response:
            self.assertEqual(
                response.geturl(),
                self.server.url + '?plugin=org.example.build-insight',
            )

    def test_shutdown_endpoint_requires_csrf_and_stops_server(self):
        self.authenticate()
        with self.assertRaises(HTTPError) as denied:
            self.request_json('/api/v1/shutdown', method='POST', body={}, csrf=False)
        self.assertEqual(denied.exception.code, 403)

        status, result = self.request_json('/api/v1/shutdown', method='POST', body={})
        self.assertEqual(status, 200)
        self.assertEqual(result, {'status': 'shutting_down'})
        self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive())

    def test_host_and_upload_size_limits_are_enforced(self):
        host, port = self.server.httpd.server_address[:2]
        connection = HTTPConnection(host, port)
        connection.putrequest('GET', '/api/v1/session', skip_host=True)
        connection.putheader('Host', 'attacker.invalid')
        connection.endheaders()
        self.assertEqual(connection.getresponse().status, 400)
        connection.close()

        self.authenticate()
        connection = HTTPConnection(host, port)
        connection.putrequest('POST', '/api/v1/packages')
        connection.putheader('Cookie', 'env_webui_session=' + self.server.application.session_token)
        connection.putheader('Origin', self.origin)
        connection.putheader('Sec-Fetch-Site', 'same-origin')
        connection.putheader('X-Env-CSRF', self.csrf)
        connection.putheader('X-Filename', 'oversized.epack')
        connection.putheader('Content-Length', str(PACKAGE_LIMIT + 1))
        connection.endheaders()
        self.assertEqual(connection.getresponse().status, 400)
        connection.close()

    def test_wildcard_listener_accepts_numeric_hosts_and_rejects_dns_names(self):
        remote = WebUIServer(
            env_root=os.path.join(self.temporary.name, 'remote-env'),
            workspace=self.temporary.name,
            host='0.0.0.0',
            launcher_dir=os.path.join(self.temporary.name, 'remote-launchers'),
        )
        thread = threading.Thread(target=remote.serve_forever, daemon=True)
        thread.start()
        try:
            self.assertTrue(remote.remote_access)
            self.assertNotIn('0.0.0.0', remote.launch_url)
            port = remote.httpd.server_address[1]

            connection = HTTPConnection('127.0.0.1', port)
            connection.putrequest('GET', '/api/v1/session', skip_host=True)
            connection.putheader('Host', '192.0.2.10:%d' % port)
            connection.endheaders()
            self.assertEqual(connection.getresponse().status, 401)
            connection.close()

            connection = HTTPConnection('127.0.0.1', port)
            connection.putrequest('GET', '/api/v1/session', skip_host=True)
            connection.putheader('Host', 'attacker.invalid')
            connection.endheaders()
            self.assertEqual(connection.getresponse().status, 400)
            connection.close()
        finally:
            remote.shutdown()
            thread.join(timeout=2)


class WebUICommandTest(unittest.TestCase):
    SSH_ENVIRONMENT = {
        'SSH_CONNECTION': '',
        'SSH_CLIENT': '',
        'SSH_TTY': '',
    }

    @staticmethod
    def parse_webui(*arguments):
        parser = argparse.ArgumentParser()
        commands = parser.add_subparsers()
        cmd_webui.add_parser(commands)
        return parser.parse_args(['webui'] + list(arguments))

    def test_global_aliases_select_wildcard_listener(self):
        self.assertEqual(self.parse_webui().host, '127.0.0.1')
        for option in ('-g', '--global'):
            with self.subTest(option=option):
                self.assertEqual(self.parse_webui(option).host, '0.0.0.0')

    def test_global_alias_conflicts_with_explicit_host(self):
        with mock.patch('sys.stderr', new=io.StringIO()):
            with self.assertRaises(SystemExit) as conflict:
                self.parse_webui('--global', '--host', '127.0.0.1')
        self.assertEqual(conflict.exception.code, 2)

    def test_browser_options_are_mutually_exclusive(self):
        with mock.patch('sys.stderr', new=io.StringIO()):
            with self.assertRaises(SystemExit) as conflict:
                self.parse_webui('--browser', '--no-browser')
        self.assertEqual(conflict.exception.code, 2)

    def test_ssh_session_detection_uses_standard_environment_variables(self):
        self.assertFalse(cmd_webui.is_ssh_session({}))
        for name in cmd_webui.SSH_ENVIRONMENT_VARIABLES:
            with self.subTest(name=name):
                self.assertTrue(cmd_webui.is_ssh_session({name: 'active'}))
                self.assertFalse(cmd_webui.is_ssh_session({name: '   '}))

    def test_command_opens_browser_by_default(self):
        server = mock.Mock(
            url='http://127.0.0.1:49152/',
            launch_url='http://127.0.0.1:49152/_launch/token',
            remote_access=False,
        )
        args = self.parse_webui()
        with mock.patch.dict(os.environ, self.SSH_ENVIRONMENT), mock.patch.object(
            cmd_webui,
            'WebUIServer',
            return_value=server,
        ), mock.patch.object(
            cmd_webui.webbrowser,
            'open',
        ) as open_browser:
            args.func(args)
        open_browser.assert_called_once_with(server.launch_url)
        server.serve_forever.assert_called_once_with()
        server.shutdown.assert_called_once_with()

    def test_ssh_session_skips_browser_by_default(self):
        server = mock.Mock(
            url='http://192.0.2.10:49152/',
            launch_url='http://192.0.2.10:49152/_launch/token',
            remote_access=True,
        )
        args = self.parse_webui('-g')
        output = io.StringIO()
        with mock.patch.dict(os.environ, {'SSH_CONNECTION': 'client 123 server 22'}, clear=False), mock.patch.object(
            cmd_webui,
            'WebUIServer',
            return_value=server,
        ), mock.patch.object(cmd_webui.webbrowser, 'open') as open_browser, mock.patch(
            'sys.stdout',
            new=output,
        ):
            args.func(args)
        open_browser.assert_not_called()
        self.assertIn('SSH session detected; browser launch skipped.', output.getvalue())
        server.serve_forever.assert_called_once_with()

    def test_browser_option_forces_opening_in_ssh_session(self):
        server = mock.Mock(
            url='http://192.0.2.10:49152/',
            launch_url='http://192.0.2.10:49152/_launch/token',
            remote_access=True,
        )
        args = self.parse_webui('-g', '--browser')
        with mock.patch.dict(os.environ, {'SSH_TTY': '/dev/pts/1'}, clear=False), mock.patch.object(
            cmd_webui,
            'WebUIServer',
            return_value=server,
        ), mock.patch.object(cmd_webui.webbrowser, 'open') as open_browser, mock.patch('builtins.print'):
            args.func(args)
        open_browser.assert_called_once_with(server.launch_url)

    def test_global_command_can_disable_browser(self):
        server = mock.Mock(
            url='http://192.0.2.10:49152/',
            launch_url='http://192.0.2.10:49152/_launch/token',
            remote_access=True,
        )
        args = self.parse_webui('-g', '--no-browser')
        with mock.patch.object(cmd_webui, 'WebUIServer', return_value=server) as server_type, mock.patch.object(
            cmd_webui.webbrowser,
            'open',
        ) as open_browser, mock.patch('builtins.print'):
            args.func(args)
        server_type.assert_called_once_with(
            env_root=args.env_root,
            workspace=args.workspace,
            host='0.0.0.0',
            port=args.port,
        )
        open_browser.assert_not_called()

    def test_plugin_target_is_forwarded_to_server(self):
        server = mock.Mock(
            url='http://127.0.0.1:49152/',
            launch_url='http://127.0.0.1:49152/_launch/token',
            remote_access=False,
        )
        args = self.parse_webui('--plugin', 'org.example.build-insight', '--no-browser')
        with mock.patch.object(cmd_webui, 'WebUIServer', return_value=server) as server_type:
            args.func(args)
        server_type.assert_called_once_with(
            env_root=None,
            workspace=os.getcwd(),
            host='127.0.0.1',
            port=0,
            plugin_id='org.example.build-insight',
        )

    def test_installed_plugin_id_can_be_used_as_positional_target(self):
        args = self.parse_webui('org.example.build-insight')
        with mock.patch.object(cmd_webui, '_is_webui_plugin', return_value=True):
            normalized = cmd_webui._normalize_args(args)
        self.assertEqual(normalized.action, 'run')
        self.assertEqual(normalized.plugin, 'org.example.build-insight')
        self.assertEqual(normalized.workspace, os.getcwd())

    def test_start_status_stop_lifecycle(self):
        temporary = tempfile.TemporaryDirectory()
        env_root = os.path.join(temporary.name, 'env')
        try:
            start = self.parse_webui('start', '--env-root', env_root, '--no-browser', '--port', '0')
            start_output = io.StringIO()
            with mock.patch('sys.stdout', new=start_output):
                self.assertEqual(start.func(start), 0)
            self.assertIn('Env WebUI:', start_output.getvalue())

            status = self.parse_webui('status', '--env-root', env_root)
            status_output = io.StringIO()
            with mock.patch('sys.stdout', new=status_output):
                self.assertEqual(status.func(status), 0)
            self.assertIn('running and online', status_output.getvalue())

            repeated = self.parse_webui('start', '--env-root', env_root, '--no-browser', '--port', '0')
            repeated_output = io.StringIO()
            with mock.patch('sys.stdout', new=repeated_output):
                self.assertEqual(repeated.func(repeated), 0)
            self.assertIn('already running', repeated_output.getvalue())

            stop = self.parse_webui('stop', '--env-root', env_root)
            stop_output = io.StringIO()
            with mock.patch('sys.stdout', new=stop_output):
                self.assertEqual(stop.func(stop), 0)
            self.assertIn('stopped', stop_output.getvalue())

            stopped = self.parse_webui('status', '--env-root', env_root)
            stopped_output = io.StringIO()
            with mock.patch('sys.stdout', new=stopped_output):
                self.assertEqual(stopped.func(stopped), 0)
            self.assertIn('is stopped', stopped_output.getvalue())
        finally:
            cleanup = self.parse_webui('stop', '--env-root', env_root)
            with mock.patch('sys.stdout', new=io.StringIO()):
                cleanup.func(cleanup)
            temporary.cleanup()

    def test_start_opens_browser_for_local_service(self):
        temporary = tempfile.TemporaryDirectory()
        env_root = os.path.join(temporary.name, 'env')
        try:
            start = self.parse_webui('start', '--env-root', env_root, '--port', '0')
            with mock.patch.object(cmd_webui, 'is_ssh_session', return_value=False), mock.patch.object(
                cmd_webui.webbrowser, 'open'
            ) as open_browser:
                start.func(start)
            open_browser.assert_called_once()
        finally:
            stop = self.parse_webui('stop', '--env-root', env_root)
            with mock.patch('sys.stdout', new=io.StringIO()):
                stop.func(stop)
            temporary.cleanup()

    def test_standalone_entry_reuses_webui_subcommand(self):
        with mock.patch.object(env_module, 'show_version_warning') as version_warning, mock.patch.object(
            env_module,
            'export_environment_variable',
        ) as export_environment, mock.patch.object(env_module, 'init_logger') as init_logger, mock.patch.object(
            env_module.cmd_webui,
            'main',
        ) as webui_main:
            env_module.webui()
        version_warning.assert_called_once_with()
        export_environment.assert_called_once_with()
        init_logger.assert_called_once_with(env_module.get_env_root())
        webui_main.assert_called_once_with()

    def test_installed_package_context_uses_env_manager_imports(self):
        import importlib.util
        import types

        import file_context_menu
        import plugins.backend
        import plugins.errors
        import plugins.market
        import plugins.service
        import plugins.webui
        import sdk_manager
        import toolchain_manager

        package = types.ModuleType('env')
        package.__path__ = [REPOSITORY]
        aliases = {
            'env': package,
            'env.plugins': sys.modules['plugins'],
            'env.plugins.backend': sys.modules['plugins.backend'],
            'env.plugins.errors': sys.modules['plugins.errors'],
            'env.plugins.market': sys.modules['plugins.market'],
            'env.plugins.service': sys.modules['plugins.service'],
            'env.plugins.webui': sys.modules['plugins.webui'],
            'env.sdk_manager': sdk_manager,
            'env.toolchain_manager': toolchain_manager,
            'env.file_context_menu': file_context_menu,
        }
        with mock.patch.dict(sys.modules, aliases):
            spec = importlib.util.spec_from_file_location(
                'env.plugins.webui.server_test',
                sys.modules['plugins.webui.server'].__file__,
            )
            imported = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(imported)

        self.assertIs(imported.SdkManager, sdk_manager.SdkManager)
        self.assertIs(imported.ToolchainManager, toolchain_manager.ToolchainManager)
        self.assertIs(imported.FileContextMenuManager, file_context_menu.FileContextMenuManager)

    def test_standalone_help_uses_short_program_name(self):
        output = io.StringIO()
        with mock.patch('sys.stdout', new=output):
            with self.assertRaises(SystemExit) as help_exit:
                cmd_webui.main(['--help'])
        self.assertEqual(help_exit.exception.code, 0)
        self.assertIn('usage: webui ', output.getvalue())
        self.assertNotIn('usage: webui webui ', output.getvalue())

    def test_help_lists_global_shortcut(self):
        result = subprocess.run(
            [sys.executable, ENV_SCRIPT, 'webui', '--help'],
            cwd=REPOSITORY,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('-g, --global', result.stdout)
        self.assertIn('--browser', result.stdout)
        self.assertIn('--no-browser', result.stdout)

    def test_non_ip_hostname_is_rejected(self):
        result = subprocess.run(
            [sys.executable, ENV_SCRIPT, 'webui', '--host', 'attacker.invalid', '--no-browser'],
            cwd=REPOSITORY,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn('loopback address or 0.0.0.0', result.stderr)

    def test_catalog_option_is_not_available(self):
        result = subprocess.run(
            [sys.executable, ENV_SCRIPT, 'webui', '--catalog', 'catalog.json', '--no-browser'],
            cwd=REPOSITORY,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn('unrecognized arguments: --catalog', result.stderr)


if __name__ == '__main__':
    unittest.main()

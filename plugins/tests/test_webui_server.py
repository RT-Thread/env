import argparse
from http.cookiejar import CookieJar
from http.client import HTTPConnection
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
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

    def test_launch_token_is_one_time(self):
        self.authenticate()
        with self.assertRaises(HTTPError) as repeated:
            build_opener(HTTPCookieProcessor(CookieJar())).open(self.server.launch_url)
        self.assertEqual(repeated.exception.code, 401)

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

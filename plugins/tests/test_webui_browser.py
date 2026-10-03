import argparse
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import socketserver
import subprocess
import tempfile
import threading
import unittest
from unittest import mock

from cmds import cmd_webui


class WebUIBrowserTest(unittest.TestCase):
    def setUp(self):
        self.args = argparse.Namespace(browser=False, no_browser=False)
        self.url = 'http://127.0.0.1:8000/_launch/token'
        self.environment = {'TERM_PROGRAM': 'vscode', 'VSCODE_IPC_HOOK_CLI': '/tmp/editor.sock',
                            'SSH_CONNECTION': 'remote', 'PATH': '/bin'}

    def test_vscode_remote_session_is_not_treated_as_plain_ssh(self):
        self.assertTrue(cmd_webui.should_open_browser(self.args, self.environment))
        self.assertFalse(cmd_webui.should_open_browser(self.args, {'SSH_CONNECTION': 'remote'}))
        self.assertTrue(cmd_webui.should_open_browser(self.args, {}))

    def test_remote_ssh_bridge_is_detected_without_term_program(self):
        environment = dict(self.environment)
        environment.pop('TERM_PROGRAM')
        self.assertTrue(cmd_webui.is_vscode_terminal(environment))
        self.assertTrue(cmd_webui.should_open_browser(self.args, environment))

    def create_server_layout(self, directory):
        root = Path(directory) / 'VS Code Server'
        (root / 'out').mkdir(parents=True)
        (root / 'out' / 'server-cli.js').touch()
        (root / 'node').touch()
        return root

    def test_remote_cli_hidden_open_flag_does_not_require_help(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.create_server_layout(directory)
            cli = root / 'bin' / 'remote-cli' / 'code'
            cli.parent.mkdir(parents=True)
            cli.touch()
            environment = dict(self.environment, VSCODE_GIT_ASKPASS_NODE=str(root / 'node'))
            environment.pop('TERM_PROGRAM')
            with mock.patch.object(cmd_webui.shutil, 'which', return_value=None), mock.patch.object(
                cmd_webui.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', ''),
            ) as run, mock.patch.object(cmd_webui.webbrowser, 'open') as system:
                self.assertTrue(cmd_webui.open_browser(self.url, self.args, environment))
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0], [str(cli), '--openExternal', self.url])
            self.assertEqual(run.call_args.kwargs['env']['VSCODE_IPC_HOOK_CLI'], '/tmp/editor.sock')
            system.assert_not_called()

    def test_remote_browser_helper_works_without_code_on_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.create_server_layout(directory)
            helper = root / 'bin' / 'helpers' / 'browser.sh'
            helper.parent.mkdir(parents=True)
            helper.touch()
            environment = dict(self.environment, BROWSER=str(helper))
            with mock.patch.object(cmd_webui.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
                self.assertTrue(cmd_webui._open_in_vscode(self.url, environment))
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0], [str(helper), self.url])

    def test_helper_failure_falls_back_to_remote_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.create_server_layout(directory)
            helper = root / 'bin' / 'helpers' / 'browser.sh'
            helper.parent.mkdir(parents=True)
            helper.touch()
            cli = root / 'bin' / 'remote-cli' / 'code'
            cli.parent.mkdir(parents=True)
            cli.touch()
            with mock.patch.object(cmd_webui.subprocess, 'run', side_effect=[
                subprocess.CompletedProcess([], 1, '', ''), subprocess.CompletedProcess([], 0, '', ''),
            ]) as run:
                self.assertTrue(cmd_webui._open_in_vscode(self.url, dict(self.environment, BROWSER=str(helper))))
            self.assertEqual([call.args[0] for call in run.call_args_list], [
                [str(helper), self.url], [str(cli), '--openExternal', self.url],
            ])

    def test_insiders_remote_cli_on_path_uses_hidden_open_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.create_server_layout(directory)
            cli = root / 'bin' / 'remote-cli' / 'code-insiders'
            cli.parent.mkdir(parents=True)
            cli.touch()
            with mock.patch.object(cmd_webui.shutil, 'which', side_effect=[None, str(cli)]), mock.patch.object(
                cmd_webui.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', ''),
            ) as run:
                self.assertTrue(cmd_webui._open_in_vscode(self.url, self.environment))
            self.assertEqual(run.call_args.args[0], [str(cli), '--openExternal', self.url])
            run.assert_called_once()

    @unittest.skipUnless(os.name == 'posix', 'VS Code Server Unix socket integration')
    def test_installed_remote_cli_and_helper_pass_url_to_client_bridge(self):
        installed = Path.home() / '.vscode-server'
        candidates = list(installed.glob('cli/servers/*/server/bin/remote-cli/code'))
        candidates += list(installed.glob('bin/*/bin/remote-cli/code'))
        cli = next((path for path in candidates if cmd_webui._vscode_server_root(
            str(path), 'remote-cli', ('code',),
        )), None)
        if cli is None:
            self.skipTest('VS Code Server is not installed')
        root = cli.parents[2]
        received = []

        class ClientBridge(BaseHTTPRequestHandler):
            def do_POST(self):
                # The real CLI, not Env, produces this client-bound request.
                if self.headers.get('Transfer-Encoding') == 'chunked':
                    chunks = []
                    while True:
                        size = int(self.rfile.readline().split(b';', 1)[0], 16)
                        if not size:
                            self.rfile.readline()
                            break
                        chunks.append(self.rfile.read(size))
                        self.rfile.read(2)
                    body = b''.join(chunks)
                else:
                    body = self.rfile.read(int(self.headers['Content-Length']))
                received.append(json.loads(body.decode('utf-8')))
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', '4')
                self.end_headers()
                self.wfile.write(b'null')

            def log_message(self, *args):
                pass

        with tempfile.TemporaryDirectory() as directory:
            server = socketserver.UnixStreamServer(os.path.join(directory, 'cli.sock'), ClientBridge)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            environment = dict(os.environ, VSCODE_IPC_HOOK_CLI=server.server_address,
                               VSCODE_GIT_ASKPASS_NODE=str(root / 'node'),
                               BROWSER='', SSH_CONNECTION='remote', TERM_PROGRAM='vscode')
            try:
                help_result = subprocess.run([str(cli), '--help'], env=environment,
                                             capture_output=True, text=True, timeout=5)
                self.assertEqual(help_result.returncode, 0)
                self.assertNotIn('--openExternal', help_result.stdout)
                with mock.patch.object(cmd_webui.webbrowser, 'open') as system:
                    self.assertTrue(cmd_webui.open_browser(self.url, self.args, environment))
                    helper = root / 'bin' / 'helpers' / 'browser.sh'
                    if helper.is_file():
                        environment['BROWSER'] = str(helper)
                        self.assertTrue(cmd_webui.open_browser(self.url, self.args, environment))
                        self.assertEqual(len(received), 2)
                system.assert_not_called()
                self.assertTrue(received)
                self.assertTrue(all(message == {'type': 'openExternal', 'uris': [self.url]} for message in received))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

    def test_arbitrary_browser_command_is_not_executed_on_remote_host(self):
        with mock.patch.object(cmd_webui.shutil, 'which', return_value=None), mock.patch.object(
            cmd_webui.subprocess, 'run',
        ) as run, mock.patch.object(cmd_webui.webbrowser, 'open') as system, mock.patch('sys.stderr'):
            environment = dict(self.environment, BROWSER='xdg-open; touch /tmp/unwanted')
            self.assertFalse(cmd_webui.open_browser(self.url, self.args, environment))
        run.assert_not_called()
        system.assert_not_called()

    def test_missing_bridge_does_not_launch_a_remote_browser(self):
        environment = dict(self.environment)
        environment.pop('VSCODE_IPC_HOOK_CLI')
        with mock.patch.object(cmd_webui.subprocess, 'run') as run, mock.patch.object(
            cmd_webui.webbrowser, 'open',
        ) as system, mock.patch('sys.stderr'):
            self.assertFalse(cmd_webui.open_browser(self.url, self.args, environment))
        run.assert_not_called()
        system.assert_not_called()

    def test_remote_helper_failure_does_not_depend_on_ssh_environment_variables(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.create_server_layout(directory)
            helper = root / 'bin' / 'helpers' / 'browser.sh'
            helper.parent.mkdir(parents=True)
            helper.touch()
            environment = dict(self.environment, BROWSER=str(helper))
            environment.pop('SSH_CONNECTION')
            with mock.patch.object(cmd_webui, '_open_in_vscode', return_value=False), mock.patch.object(
                cmd_webui.shutil, 'which', return_value=None,
            ), mock.patch.object(cmd_webui.webbrowser, 'open') as system, mock.patch('sys.stderr'):
                self.assertFalse(cmd_webui.open_browser(self.url, self.args, environment))
            system.assert_not_called()

    def test_cli_failure_and_timeout_are_nonfatal(self):
        for result in (
            subprocess.CompletedProcess([], 0, '', 'Error when invoking the open external command:'),
            subprocess.CompletedProcess([], 1, '', ''),
            subprocess.TimeoutExpired('code', 5),
            OSError('missing'),
        ):
            with self.subTest(result=result):
                options = {'side_effect': result} if isinstance(result, Exception) else {'return_value': result}
                with mock.patch.object(cmd_webui.subprocess, 'run', **options):
                    self.assertFalse(cmd_webui._run_vscode_opener(['code', '--openExternal', self.url], self.environment))

    def test_plain_ssh_does_not_try_editor_or_system_browser(self):
        with mock.patch.object(cmd_webui, '_open_in_vscode') as editor, mock.patch.object(
            cmd_webui.webbrowser, 'open',
        ) as system:
            self.assertFalse(cmd_webui.open_browser(self.url, self.args, {'SSH_CONNECTION': 'remote'}))
        editor.assert_not_called()
        system.assert_not_called()

    def test_foreground_remote_ssh_attempts_editor_open(self):
        server = mock.Mock(url='http://127.0.0.1:8000/', launch_url=self.url, remote_access=False)
        with mock.patch.dict(os.environ, self.environment, clear=True), mock.patch.object(
            cmd_webui, 'WebUIServer', return_value=server,
        ), mock.patch.object(cmd_webui, '_open_in_vscode', return_value=True) as editor, mock.patch.object(
            cmd_webui.webbrowser, 'open',
        ) as system, mock.patch('builtins.print'):
            cmd_webui.main([])
        editor.assert_called_once_with(self.url, os.environ)
        system.assert_not_called()
        server.serve_forever.assert_called_once()
        server.shutdown.assert_called_once()

    def test_no_browser_disables_remote_ssh_editor_attempt(self):
        with mock.patch.dict(os.environ, self.environment, clear=True), mock.patch.object(
            cmd_webui, 'WebUIServer', return_value=mock.Mock(remote_access=False),
        ), mock.patch.object(cmd_webui, '_open_in_vscode') as editor, mock.patch.object(
            cmd_webui.webbrowser, 'open',
        ) as system, mock.patch('builtins.print'):
            cmd_webui.main(['--no-browser'])
        editor.assert_not_called()
        system.assert_not_called()

    def test_supported_editor_cli_is_preferred_over_system_browser(self):
        with mock.patch.object(cmd_webui.shutil, 'which', return_value='/bin/code'), mock.patch.object(
            cmd_webui.os.path, 'isfile', return_value=True,
        ), mock.patch.object(cmd_webui.subprocess, 'run', side_effect=[
            subprocess.CompletedProcess([], 0, '--openExternal', ''),
            subprocess.CompletedProcess([], 0, '', ''),
        ]) as run, mock.patch.object(cmd_webui.webbrowser, 'open') as system:
            self.assertTrue(cmd_webui.open_browser(self.url, self.args, self.environment))
        self.assertEqual(run.call_args.args[0], ['/bin/code', '--openExternal', self.url])
        system.assert_not_called()

    def test_unsupported_desktop_cli_does_not_receive_url_as_a_file(self):
        with mock.patch.object(cmd_webui.shutil, 'which', return_value='/bin/code'), mock.patch.object(
            cmd_webui.os.path, 'isfile', return_value=True,
        ), mock.patch.object(cmd_webui.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'desktop CLI', '')) as run:
            self.assertFalse(cmd_webui._open_in_vscode(self.url, self.environment))
        self.assertEqual(run.call_count, 1)

    def test_explicit_options_take_precedence(self):
        with mock.patch.object(cmd_webui, '_open_in_vscode') as editor, mock.patch.object(
            cmd_webui.webbrowser, 'open', return_value=True,
        ) as system:
            self.args.no_browser = True
            self.assertFalse(cmd_webui.open_browser(self.url, self.args, self.environment))
            self.args.no_browser = False
            self.args.browser = True
            self.assertTrue(cmd_webui.open_browser(self.url, self.args, self.environment))
        editor.assert_not_called()
        system.assert_called_once_with(self.url)

    def test_failed_editor_open_does_not_open_browser_on_ssh_host(self):
        with mock.patch.object(cmd_webui, '_open_in_vscode', return_value=False), mock.patch.object(
            cmd_webui.webbrowser, 'open',
        ) as system, mock.patch('sys.stderr'):
            self.assertFalse(cmd_webui.open_browser(self.url, self.args, self.environment))
        system.assert_not_called()

    def test_browser_failure_does_not_fail_the_webui_server(self):
        with mock.patch.object(cmd_webui.webbrowser, 'open', side_effect=OSError('no display')), mock.patch('sys.stderr'):
            self.assertFalse(cmd_webui.open_browser(self.url, self.args, {}))


if __name__ == '__main__':
    unittest.main()

# -*- coding:utf-8 -*-
"""Manage and run the local Env WebUI."""

import argparse
import http.client
import json
import os
import signal
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from urllib.parse import urlparse

from plugins.errors import PluginError, UsageError
from plugins.paths import PluginPaths
from plugins.service import PluginService
from plugins.store import FileLock
from plugins.webui.server import WebUIServer


SSH_ENVIRONMENT_VARIABLES = ('SSH_CONNECTION', 'SSH_CLIENT', 'SSH_TTY')
WEBUI_ACTIONS = frozenset(('start', 'stop', 'status'))
WEBUI_STATE_FILE = 'webui-state-v1.json'
WEBUI_LOCK_FILE = 'webui-state-v1.lock'
START_TIMEOUT = 10.0
STOP_TIMEOUT = 5.0


def is_ssh_session(environ=None):
    environ = environ if environ is not None else os.environ
    return any(environ.get(name, '').strip() for name in SSH_ENVIRONMENT_VARIABLES)


def is_vscode_terminal(environ=None):
    environ = environ if environ is not None else os.environ
    return environ.get('TERM_PROGRAM', '').lower() == 'vscode' or bool(environ.get('VSCODE_IPC_HOOK_CLI'))


def should_open_browser(args, environ=None):
    if getattr(args, 'browser', False):
        return True
    if getattr(args, 'no_browser', False):
        return False
    return is_vscode_terminal(environ) or not is_ssh_session(environ=environ)


def _vscode_server_root(candidate, directory, filenames):
    path = os.path.realpath(candidate)
    parent = os.path.dirname(path)
    bin_path = os.path.dirname(parent)
    root = os.path.dirname(bin_path)
    if (os.path.basename(path) not in filenames or os.path.basename(parent) != directory
            or os.path.basename(bin_path) != 'bin' or not os.path.isfile(path)):
        return None
    if not any(os.path.isfile(os.path.join(root, name)) for name in ('node', 'node.exe')):
        return None
    if not any(os.path.isfile(os.path.join(root, name)) for name in (
        'out/server-cli.js', 'out/vs/server/node/server.cli.js',
    )):
        return None
    return root


def _run_vscode_opener(command, environ):
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=5, env=dict(environ),
        )
        output = result.stdout + result.stderr
        return result.returncode == 0 and not any(message in output for message in (
            'Error when invoking', 'Unable to connect to VS Code server',
            'Invalid url:', 'Ignoring option',
        ))
    except (OSError, subprocess.SubprocessError):
        return False


def _vscode_opener_paths(environ):
    candidates = []
    browser = environ.get('BROWSER', '').strip()
    browser_root = _vscode_server_root(browser, 'helpers', ('browser.sh',)) if browser else None
    if browser_root:
        candidates.extend(os.path.join(browser_root, 'bin', 'remote-cli', name)
                          for name in ('code', 'code-insiders'))
    node = environ.get('VSCODE_GIT_ASKPASS_NODE')
    if node:
        candidates.extend(os.path.join(os.path.dirname(node), 'bin', 'remote-cli', name)
                          for name in ('code', 'code-insiders'))
    askpass = environ.get('VSCODE_GIT_ASKPASS_MAIN')
    if askpass:
        root = os.path.abspath(os.path.join(os.path.dirname(askpass), '..', '..', '..'))
        candidates.extend(os.path.join(root, 'bin', 'remote-cli', name)
                          for name in ('code', 'code-insiders'))
    for name in ('code', 'code-insiders'):
        candidate = shutil.which(name, path=environ.get('PATH'))
        if candidate:
            candidates.append(candidate)
    return browser if browser_root else None, list(dict.fromkeys(candidates))


def _open_in_vscode(url, environ):
    if not environ.get('VSCODE_IPC_HOOK_CLI'):
        return False
    browser, candidates = _vscode_opener_paths(environ)
    # Remote SSH injects this helper; it opens on the connected VS Code client.
    if browser and _run_vscode_opener([browser, url], environ):
        return True
    for candidate in candidates:
        if not os.path.isfile(candidate):
            continue
        if _vscode_server_root(candidate, 'remote-cli', ('code', 'code-insiders')):
            # Remote CLI supports this hidden flag, absent from its --help output.
            if _run_vscode_opener([candidate, '--openExternal', url], environ):
                return True
            continue
        try:
            # For unrecognized CLIs, do not risk interpreting a URL as a file.
            help_result = subprocess.run(
                [candidate, '--help'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, timeout=5, env=dict(environ),
            )
            if help_result.returncode or '--openExternal' not in help_result.stdout:
                continue
            if _run_vscode_opener([candidate, '--openExternal', url], environ):
                return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False


def open_browser(url, args, environ=None):
    environ = environ if environ is not None else os.environ
    if not should_open_browser(args, environ):
        return False
    if is_vscode_terminal(environ) and not getattr(args, 'browser', False):
        if _open_in_vscode(url, environ):
            return True
        browser, candidates = _vscode_opener_paths(environ)
        remote = browser or any(_vscode_server_root(path, 'remote-cli', ('code', 'code-insiders'))
                                for path in candidates)
        if is_ssh_session(environ) or remote:
            print('VS Code URL opener unavailable; open the Launch URL from the terminal.', file=sys.stderr)
            return False
    try:
        return webbrowser.open(url)
    except (OSError, webbrowser.Error):
        print('Env WebUI: cannot open browser; open the Launch URL manually.', file=sys.stderr)
        return False


def _state_path(env_root=None):
    paths = PluginPaths(env_root=env_root)
    return os.path.join(paths.runtime, WEBUI_STATE_FILE)


def _lock_path(state_path):
    return os.path.join(os.path.dirname(state_path), WEBUI_LOCK_FILE)


def _load_state(path):
    try:
        with open(path, 'r', encoding='utf-8') as source:
            state = json.load(source)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(state, dict) or not isinstance(state.get('pid'), int):
        return None
    if not isinstance(state.get('url'), str) or not isinstance(state.get('launch_url'), str):
        return None
    if 'stop_token' in state and not isinstance(state.get('stop_token'), str):
        return None
    return state


def _remove_state(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _write_state(path, state):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.webui-state-', dir=directory, text=True)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(state, output, ensure_ascii=True, indent=2, sort_keys=True)
            output.write('\n')
        if os.name != 'nt':
            os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    return True


def _process_matches(state, lock_path):
    pid = state['pid']
    if not _pid_alive(pid):
        return False
    try:
        with FileLock(lock_path, shared=True, blocking=False):
            return False
    except OSError:
        return True


def _server_online(state):
    try:
        parsed = urlparse(state['url'])
        host = parsed.hostname
        port = parsed.port
        if not host or port is None:
            return False
        connection = socket.create_connection((host, port), timeout=0.5)
        connection.close()
        return True
    except (OSError, TypeError, ValueError):
        return False


def _is_webui_plugin(plugin_id, env_root=None):
    if not isinstance(plugin_id, str) or not plugin_id.strip():
        return False
    try:
        plugin = PluginService(env_root=env_root).info(plugin_id.strip())
    except (PluginError, OSError):
        return False
    return bool(plugin.get('enabled') and plugin.get('webui'))


def _stop_url(state):
    token = state.get('stop_token')
    if not isinstance(token, str) or not token:
        return None
    return state['url'].rstrip('/') + '/_shutdown/' + token


def _request_shutdown(stop_url):
    if not stop_url:
        return False
    try:
        parsed = urlparse(stop_url)
        host = parsed.hostname
        port = parsed.port
        if not host or port is None:
            return False
        connection = http.client.HTTPConnection(host, port, timeout=1.0)
        try:
            path = parsed.path or '/'
            if parsed.query:
                path += '?' + parsed.query
            connection.request('GET', path)
            response = connection.getresponse()
            response.read()
            return 200 <= response.status < 300
        finally:
            connection.close()
    except (OSError, TypeError, ValueError, http.client.HTTPException):
        return False


def _current_status(path):
    state = _load_state(path)
    if state is None:
        if os.path.exists(path):
            _remove_state(path)
        return 'stopped', None
    if not _process_matches(state, _lock_path(path)):
        _remove_state(path)
        return 'stopped', None
    if _server_online(state):
        return 'online', state
    return 'starting', state


def _normalize_args(args):
    target = getattr(args, 'target', None)
    extra_workspace = getattr(args, 'workspace_arg', None)
    plugin = getattr(args, 'plugin', None)
    env_root = getattr(args, 'env_root', None)
    if target in WEBUI_ACTIONS:
        if plugin and target in ('stop', 'status'):
            raise UsageError('%s does not accept a plugin target' % target)
        if extra_workspace is not None and target != 'start':
            raise UsageError('%s does not accept a workspace argument' % target)
        args.action = target
        if (
            target == 'start'
            and not plugin
            and extra_workspace
            and not os.path.isdir(extra_workspace)
            and _is_webui_plugin(extra_workspace, env_root)
        ):
            plugin = extra_workspace.strip()
            args.workspace = os.getcwd()
        else:
            args.workspace = extra_workspace or os.getcwd()
    else:
        if extra_workspace is not None:
            raise UsageError('WebUI accepts at most one workspace argument')
        args.action = 'run'
        if target and not plugin and not os.path.isdir(target) and _is_webui_plugin(target, env_root):
            plugin = target.strip()
            args.workspace = os.getcwd()
        else:
            args.workspace = target or os.getcwd()
    args.workspace = os.path.abspath(args.workspace)
    args.plugin = plugin
    return args


def _print_server_urls(state):
    print('Env WebUI: %s' % state['url'], flush=True)
    print('Launch URL: %s' % state['launch_url'], flush=True)
    if state.get('remote_access'):
        print('Warning: Env WebUI is accessible from local networks over unencrypted HTTP.', flush=True)


def _child_command(args):
    command = [sys.executable, os.path.abspath(__file__), '--serve', args.workspace]
    command.extend(['--host', args.host, '--port', str(args.port)])
    if args.env_root:
        command.extend(['--env-root', args.env_root])
    plugin = getattr(args, 'plugin', None)
    if plugin:
        command.extend(['--plugin', plugin])
    return command


def _child_environment():
    environment = dict(os.environ)
    module_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    current_path = environment.get('PYTHONPATH')
    environment['PYTHONPATH'] = module_root + (os.pathsep + current_path if current_path else '')
    return environment


def _start_background(args, path):
    status, state = _current_status(path)
    if status == 'online':
        print('Env WebUI is already running at %s' % state['url'])
        return 0
    if status == 'starting':
        print('Env WebUI is already starting at %s' % state['url'])
        return 0

    options = {
        'stdin': subprocess.DEVNULL,
        'stdout': subprocess.DEVNULL,
        'stderr': subprocess.DEVNULL,
        'env': _child_environment(),
        'close_fds': True,
    }
    if os.name == 'nt':
        options['creationflags'] = (
            getattr(subprocess, 'DETACHED_PROCESS', 0x00000008)
            | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x00000200)
        )
    else:
        options['start_new_session'] = True
    try:
        child = subprocess.Popen(_child_command(args), **options)
    except OSError as exc:
        raise PluginError('cannot start WebUI service: %s' % exc)

    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        status, state = _current_status(path)
        if status == 'online':
            _print_server_urls(state)
            if should_open_browser(args):
                open_browser(state['launch_url'], args)
            elif not getattr(args, 'no_browser', False) and is_ssh_session():
                print('SSH session detected; browser launch skipped. Use --browser to force it.', flush=True)
            # The daemon owns its lifetime after the readiness handshake.
            child.returncode = 0
            return 0
        if child.poll() is not None:
            break
        time.sleep(0.05)

    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=1)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
    _remove_state(path)
    raise PluginError('WebUI service did not become available')


def _stop_background(path):
    status, state = _current_status(path)
    if state is None:
        print('Env WebUI is stopped.')
        return 0

    pid = state['pid']
    stop_url = _stop_url(state)
    if _request_shutdown(stop_url):
        deadline = time.monotonic() + STOP_TIMEOUT
        while time.monotonic() < deadline:
            if not _pid_alive(pid) or _load_state(path) is None:
                break
            time.sleep(0.05)
    if _pid_alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        deadline = time.monotonic() + STOP_TIMEOUT
        while time.monotonic() < deadline:
            if not _pid_alive(pid) or _load_state(path) is None:
                break
            time.sleep(0.05)
        if _pid_alive(pid):
            force_signal = getattr(signal, 'SIGKILL', signal.SIGTERM)
            try:
                os.kill(pid, force_signal)
            except OSError:
                pass
            if os.name == 'nt' and _pid_alive(pid):
                subprocess.call(
                    ['taskkill', '/PID', str(pid), '/T', '/F'],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
    _remove_state(path)
    if status == 'online':
        print('Env WebUI stopped.')
    else:
        print('Env WebUI startup was stopped.')
    return 0


def _show_status(path):
    status, state = _current_status(path)
    if status == 'online':
        print('Env WebUI is running and online at %s' % state['url'])
    elif status == 'starting':
        print('Env WebUI is starting at %s' % state['url'])
    else:
        print('Env WebUI is stopped.')
    return 0


def _serve(args, path):
    server = None
    try:
        with FileLock(_lock_path(path), shared=False, blocking=False):
            options = {
                'env_root': args.env_root,
                'workspace': args.workspace,
                'host': args.host,
                'port': args.port,
            }
            if getattr(args, 'plugin', None):
                options['plugin_id'] = args.plugin
            server = WebUIServer(**options)
            _write_state(
                path,
                {
                    'version': 1,
                    'pid': os.getpid(),
                    'url': server.url,
                    'launch_url': server.launch_url,
                    'stop_token': server.application.stop_token,
                    'host': args.host,
                    'port': server.httpd.server_address[1],
                    'workspace': args.workspace,
                    'remote_access': server.remote_access,
                    'started_at': time.time(),
                },
            )

            def request_shutdown(signum, frame):
                threading.Thread(target=server.httpd.shutdown, daemon=True).start()

            signal.signal(signal.SIGTERM, request_shutdown)
            server.serve_forever()
    finally:
        if server is not None:
            server.shutdown()
        state = _load_state(path)
        if state is not None and state.get('pid') == os.getpid():
            _remove_state(path)


def _run_foreground(args):
    server = None
    try:
        options = {
            'env_root': args.env_root,
            'workspace': args.workspace,
            'host': args.host,
            'port': args.port,
        }
        if getattr(args, 'plugin', None):
            options['plugin_id'] = args.plugin
        server = WebUIServer(**options)
        print('Env WebUI: %s' % server.url, flush=True)
        print('Launch URL: %s' % server.launch_url, flush=True)
        if server.remote_access:
            print('Warning: Env WebUI is accessible from local networks over unencrypted HTTP.', flush=True)
        if should_open_browser(args):
            open_browser(server.launch_url, args)
        elif not getattr(args, 'no_browser', False) and is_ssh_session():
            print('SSH session detected; browser launch skipped. Use --browser to force it.', flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    except PluginError as exc:
        print('env webui: %s' % exc, file=sys.stderr)
        raise SystemExit(exc.exit_code)
    except OSError as exc:
        print('env webui: cannot start local server: %s' % exc, file=sys.stderr)
        raise SystemExit(4)
    finally:
        if server is not None:
            server.shutdown()
    return 0


def cmd(args):
    try:
        args = _normalize_args(args)
        path = _state_path(args.env_root)
        if getattr(args, 'serve', False):
            _serve(args, path)
            return 0
        if args.action == 'start':
            return _start_background(args, path)
        if args.action == 'stop':
            return _stop_background(path)
        if args.action == 'status':
            return _show_status(path)
        return _run_foreground(args)
    except PluginError as exc:
        print('env webui: %s' % exc, file=sys.stderr)
        raise SystemExit(exc.exit_code)
    except OSError as exc:
        print('env webui: cannot start local server: %s' % exc, file=sys.stderr)
        raise SystemExit(4)


def add_arguments(parser):
    parser.add_argument(
        'target',
        nargs='?',
        default=None,
        help='workspace path, installed WebUI plugin id, or one of start, stop and status',
    )
    parser.add_argument('workspace_arg', nargs='?', default=None, help=argparse.SUPPRESS)
    parser.set_defaults(workspace=os.getcwd())
    listener = parser.add_mutually_exclusive_group()
    listener.add_argument(
        '--host',
        default='127.0.0.1',
        help='listen address; use 0.0.0.0 to expose Env WebUI on all IPv4 interfaces',
    )
    listener.add_argument(
        '-g',
        '--global',
        dest='host',
        action='store_const',
        const='0.0.0.0',
        help='listen on all IPv4 interfaces (equivalent to --host 0.0.0.0)',
    )
    parser.add_argument('--port', type=int, default=0, help='listen port; 0 selects an available port')
    parser.add_argument('--env-root', help='override the Env data root')
    parser.add_argument('--plugin', '--plugin-id', dest='plugin', help='open an installed WebUI plugin after startup')
    parser.add_argument('--serve', action='store_true', help=argparse.SUPPRESS)
    browser = parser.add_mutually_exclusive_group()
    browser.add_argument('--browser', action='store_true', help='open the default browser, even in an SSH session')
    browser.add_argument('--no-browser', action='store_true', help='do not open the default browser')


def add_parser(sub):
    parser = sub.add_parser('webui', help=__doc__, description=__doc__)
    add_arguments(parser)
    parser.set_defaults(func=cmd)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='webui', description=__doc__)
    add_arguments(parser)
    if argv is None:
        argv = sys.argv[1:]
        if argv and argv[0] == 'webui':
            argv = argv[1:]
    return cmd(parser.parse_args(argv))


if __name__ == '__main__':
    sys.exit(main())

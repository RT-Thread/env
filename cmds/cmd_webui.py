# -*- coding:utf-8 -*-
"""Manage and run the local Env WebUI."""

import argparse
import json
import os
import signal
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
from plugins.webui.server import WebUIServer


SSH_ENVIRONMENT_VARIABLES = ('SSH_CONNECTION', 'SSH_CLIENT', 'SSH_TTY')
WEBUI_ACTIONS = frozenset(('start', 'stop', 'status'))
WEBUI_STATE_FILE = 'webui-state-v1.json'
START_TIMEOUT = 10.0
STOP_TIMEOUT = 5.0


def is_ssh_session(environ=None):
    environ = environ if environ is not None else os.environ
    return any(environ.get(name, '').strip() for name in SSH_ENVIRONMENT_VARIABLES)


def should_open_browser(args, environ=None):
    if getattr(args, 'browser', False):
        return True
    if getattr(args, 'no_browser', False):
        return False
    return not is_ssh_session(environ=environ)


def _state_path(env_root=None):
    paths = PluginPaths(env_root=env_root)
    return os.path.join(paths.runtime, WEBUI_STATE_FILE)


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


def _process_matches(pid):
    if not _pid_alive(pid):
        return False
    if os.name == 'nt':
        return True
    command_path = '/proc/%d/cmdline' % pid
    try:
        with open(command_path, 'rb') as source:
            command = source.read().decode('utf-8', 'replace').split('\0')
    except OSError:
        return True
    return '--serve' in command and any(item.endswith('cmd_webui.py') for item in command)


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


def _current_status(path):
    state = _load_state(path)
    if state is None:
        if os.path.exists(path):
            _remove_state(path)
        return 'stopped', None
    if not _process_matches(state['pid']):
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
                try:
                    webbrowser.open(state['launch_url'])
                except OSError as exc:
                    print('Env WebUI: cannot open browser: %s' % exc, file=sys.stderr)
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
            webbrowser.open(server.launch_url)
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
    cmd(parser.parse_args(argv))


if __name__ == '__main__':
    main()

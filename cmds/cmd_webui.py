# -*- coding:utf-8 -*-
"""Start the local Env WebUI."""

import argparse
import os
import sys
import webbrowser

from plugins.errors import PluginError
from plugins.webui.server import WebUIServer


SSH_ENVIRONMENT_VARIABLES = ('SSH_CONNECTION', 'SSH_CLIENT', 'SSH_TTY')


def is_ssh_session(environ=None):
    environ = environ if environ is not None else os.environ
    return any(environ.get(name, '').strip() for name in SSH_ENVIRONMENT_VARIABLES)


def should_open_browser(args, environ=None):
    if getattr(args, 'browser', False):
        return True
    if getattr(args, 'no_browser', False):
        return False
    return not is_ssh_session(environ=environ)


def cmd(args):
    server = None
    try:
        server = WebUIServer(
            env_root=args.env_root,
            workspace=args.workspace,
            host=args.host,
            port=args.port,
        )
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


def add_arguments(parser):
    parser.add_argument('workspace', nargs='?', default=os.getcwd(), help='workspace used by plugin pages')
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
    cmd(parser.parse_args(argv))

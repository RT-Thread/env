# -*- coding:utf-8 -*-
"""Start the local Env WebUI."""

import os
import sys
import webbrowser

from plugins.errors import PluginError
from plugins.webui.server import WebUIServer


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
        if not args.no_browser:
            webbrowser.open(server.launch_url)
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


def add_parser(sub):
    parser = sub.add_parser('webui', help=__doc__, description=__doc__)
    parser.add_argument('workspace', nargs='?', default=os.getcwd(), help='workspace used by plugin pages')
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='listen address; use 0.0.0.0 to expose Env WebUI on all IPv4 interfaces',
    )
    parser.add_argument('--port', type=int, default=0, help='listen port; 0 selects an available port')
    parser.add_argument('--env-root', help='override the Env data root')
    parser.add_argument('--no-browser', action='store_true', help='do not open the default browser')
    parser.set_defaults(func=cmd)

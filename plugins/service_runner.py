"""Run one installed plugin backend service in a supervised child process."""

import argparse
import importlib
import sys

from .paths import PluginPaths
from .sdk.context import create_runtime_context


def _load_entry(entry):
    module_name, attribute = entry.split(':', 1)
    module = importlib.import_module(module_name)
    value = getattr(module, attribute, None)
    if not callable(value):
        raise TypeError('service entry is not callable: %s' % entry)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run an Env plugin backend service')
    parser.add_argument('--entry', required=True)
    parser.add_argument('--env-root', required=True)
    parser.add_argument('--plugin-id', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--permissions', default='')
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args(argv)
    paths = PluginPaths(env_root=args.env_root)
    permissions = [item for item in args.permissions.split(',') if item]
    context = create_runtime_context(
        paths,
        args.plugin_id,
        args.version,
        permissions,
        workspace_root=args.workspace,
    )
    service = _load_entry(args.entry)(context, args.host, args.port)
    app = getattr(service, 'app', service)
    if app is None:
        raise TypeError('service entry returned no ASGI application')
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError('plugin service requires uvicorn') from exc
    uvicorn.run(app, host=args.host, port=args.port, log_level='warning')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)

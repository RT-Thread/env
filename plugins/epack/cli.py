"""Develop, test and publish RT-Thread Env plugin packages."""

import argparse
import json
import os
import sys
import tempfile

from ..errors import PluginError, UsageError
from ..manifest import validate_manifest
from ..market import load_market_config
from ..package import EpackArchive
from ..paths import PluginPaths
from .builder import build_project
from .publisher import push_package
from .project import default_manifest, default_project_values, ensure_target_available, init_project, validate_project
from .tester import test_package


def _path(value, context):
    if context is None:
        return os.path.abspath(value)
    return context.workspace.resolve(value)


def _interactive_terminal():
    return sys.stdin.isatty() and sys.stdout.isatty()


def _prompt(label, default, metadata, field):
    while True:
        try:
            value = input('%s [%s]: ' % (label, default)).strip() or default
        except (EOFError, KeyboardInterrupt):
            print()
            raise UsageError('interactive initialization cancelled')
        candidate = dict(metadata)
        candidate[field] = value
        try:
            validate_manifest(default_manifest(**candidate))
        except PluginError as exc:
            print('Invalid %s: %s' % (label.lower(), exc), file=sys.stderr)
            continue
        return value


def _prompt_yes_no(label, default):
    default_label = 'Y/n' if default else 'y/N'
    while True:
        try:
            raw = input('%s [%s]: ' % (label, default_label)).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            raise UsageError('interactive initialization cancelled')
        if not raw:
            return default
        if raw in ('y', 'yes', 'true', '1'):
            return True
        if raw in ('n', 'no', 'false', '0'):
            return False
        print('Please answer yes or no.', file=sys.stderr)


def _init_metadata(target, args):
    defaults = default_project_values(target)
    explicit = any(
        value is not None
        for value in (
            args.plugin_id,
            args.name,
            args.version,
            args.description,
            args.author,
            args.register_command,
            args.webui,
        )
    )
    metadata = {
        'plugin_id': defaults['plugin_id'] if args.plugin_id is None else args.plugin_id,
        'name': defaults['name'] if args.name is None else args.name,
        'version': defaults['version'] if args.version is None else args.version,
        'description': (
            '%s Env plugin' % (args.name if args.name is not None else defaults['name'])
            if args.description is None
            else args.description
        ),
        'author': defaults['author'] if args.author is None else args.author,
        'register_command': True if args.register_command is None else args.register_command,
        'webui': False if args.webui is None else args.webui,
    }
    if not explicit and _interactive_terminal():
        print('Create an Env plugin project. Press Enter to accept a default.')
        for label, field in (
            ('Plugin ID', 'plugin_id'),
            ('Plugin name', 'name'),
            ('Version', 'version'),
            ('Description', 'description'),
            ('Author', 'author'),
        ):
            metadata[field] = _prompt(label, metadata[field], metadata, field)
            if field == 'name' and args.description is None:
                metadata['description'] = '%s Env plugin' % metadata['name']
        metadata['register_command'] = _prompt_yes_no('Register a command?', True)
        metadata['webui'] = _prompt_yes_no('Create a WebUI page?', False)
    if not metadata['register_command'] and not metadata['webui']:
        raise UsageError('a plugin must provide a command or a WebUI page')
    return metadata


def _parser():
    parser = argparse.ArgumentParser(prog='epack', description=__doc__)
    commands = parser.add_subparsers(dest='command')

    init = commands.add_parser('init', help='create a plugin project')
    init.add_argument('directory', nargs='?', default='env-plugin')
    init.add_argument('--id', dest='plugin_id')
    init.add_argument('--name')
    init.add_argument('--version')
    init.add_argument('--description')
    init.add_argument('--author')
    command_options = init.add_mutually_exclusive_group()
    command_options.add_argument(
        '--with-command', '--command',
        dest='register_command', action='store_true',
        help='generate and register a plugin command (default)',
    )
    command_options.add_argument(
        '--without-command', '--no-command',
        dest='register_command', action='store_false',
        help='do not generate a plugin command',
    )
    webui_options = init.add_mutually_exclusive_group()
    webui_options.add_argument(
        '--with-webui', '--webui',
        dest='webui', action='store_true',
        help='generate a minimal WebUI page',
    )
    webui_options.add_argument(
        '--without-webui', '--no-webui',
        dest='webui', action='store_false',
        help='do not generate a WebUI page (default)',
    )
    init.set_defaults(register_command=None, webui=None)

    validate = commands.add_parser('validate', help='validate a plugin project')
    validate.add_argument('directory', nargs='?', default='.')
    validate.add_argument('--json', action='store_true')

    build = commands.add_parser('build', help='build a local .epack')
    build.add_argument('directory', nargs='?', default='.')
    build.add_argument('-o', '--output')
    build.add_argument('--backend-format', choices=('source-wheel', 'pyc-wheel'))
    build.add_argument('--json', action='store_true')

    inspect = commands.add_parser('inspect', help='inspect a package without executing it')
    inspect.add_argument('package')
    inspect.add_argument('--json', action='store_true')

    push = commands.add_parser(
        'push', aliases=['publish'], help='publish a plugin project or .epack to the online market'
    )
    push.add_argument('source', nargs='?', default='.')
    push.add_argument('--market', help='override the configured plugin market URL')
    push.add_argument('--token-file', help='read the market bearer token from a file')
    push.add_argument('--changelog', help='release notes for a new plugin or version')
    push.add_argument('--backend-format', choices=('source-wheel', 'pyc-wheel'))
    push.add_argument('--json', action='store_true')

    test = commands.add_parser('test', help='install and run a plugin in a temporary Env')
    test.add_argument('source', nargs='?', default='.')
    test.add_argument('--command', dest='plugin_command', help='run a plugin command instead of its WebUI')
    test.add_argument('--no-browser', action='store_true', help='do not open the WebUI in a browser')
    test.add_argument(
        '-g', '--global', dest='host', action='store_const', const='0.0.0.0', default='127.0.0.1',
        help='listen on all IPv4 interfaces when testing a WebUI',
    )
    test.add_argument('--port', type=int, default=0, help='WebUI port; 0 selects an available port')
    test.add_argument('--backend-format', choices=('source-wheel', 'pyc-wheel'))
    return parser


def _package_for_source(source, context, output, backend_format):
    path = _path(source, context)
    if os.path.isdir(path):
        return build_project(path, output_directory=output, backend_format=backend_format), path
    if backend_format:
        raise UsageError('--backend-format requires a plugin project directory')
    return path, None


def _read_token(path, context):
    try:
        with open(_path(path, context), 'r', encoding='utf-8') as source:
            token = source.read().strip()
    except OSError as exc:
        raise UsageError('cannot read market token file: %s' % exc)
    if not token:
        raise UsageError('market token file is empty')
    return token


def run(argv, context=None):
    parser = _parser()
    command_args = []
    if argv and argv[0] == 'test' and '--' in argv:
        separator = argv.index('--')
        command_args = argv[separator + 1:]
        argv = argv[:separator]
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    if args.command == 'init':
        target = _path(args.directory, context)
        ensure_target_available(target)
        metadata = _init_metadata(target, args)
        target = init_project(target, **metadata)
        print('Created plugin project: %s' % target)
        return 0
    if args.command == 'validate':
        manifest = validate_project(_path(args.directory, context))
        result = {'status': 'ok', 'id': manifest.plugin_id, 'version': manifest.version}
    elif args.command == 'build':
        directory = _path(args.directory, context)
        output = _path(args.output, context) if args.output else None
        target = build_project(directory, output_directory=output, backend_format=args.backend_format)
        result = {'status': 'ok', 'package': target}
    elif args.command == 'inspect':
        result = EpackArchive(_path(args.package, context)).inspect().summary()
    elif args.command in ('push', 'publish'):
        market = args.market or load_market_config(PluginPaths())['url']
        if not market:
            raise UsageError('plugin market is not configured; use --market or env plugin market set')
        token = _read_token(args.token_file, context) if args.token_file else None
        with tempfile.TemporaryDirectory(prefix='epack-push-') as output:
            package, project = _package_for_source(args.source, context, output, args.backend_format)
            result = push_package(package, market, changelog=args.changelog, token=token)
            if project:
                result['package'] = os.path.basename(package)
    elif args.command == 'test':
        if args.port < 0 or args.port > 65535:
            raise UsageError('WebUI port must be between 0 and 65535')
        with tempfile.TemporaryDirectory(prefix='epack-build-') as output:
            package, project = _package_for_source(args.source, context, output, args.backend_format)
            workspace = project or (context.workspace.root if context else os.getcwd())
            return test_package(
                package, workspace, command=args.plugin_command, command_args=command_args,
                no_browser=args.no_browser, host=args.host, port=args.port,
            )
    else:
        raise UsageError("unsupported epack command: %s" % args.command)
    if getattr(args, 'json', False):
        print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    elif args.command == 'validate':
        print('Valid plugin project: %s %s' % (result['id'], result['version']))
    elif args.command == 'build':
        print('Built plugin package: %s' % result['package'])
    elif args.command in ('push', 'publish'):
        print('Published %s %s to %s (%s)' % (result['id'], result['version'], result['market'], result['action']))
    else:
        print('Plugin: %s %s (%s)' % (result['name'], result['version'], result['id']))
        print('Signature: %s' % result['signing_status'])
        print('Integrity: %s' % result['integrity'])
        print('Commands: %s' % ', '.join(command['name'] for command in result['commands']))
    return 0


def main(argv=None, context=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        return run(argv, context=context)
    except PluginError as exc:
        print('epack: %s' % exc, file=sys.stderr)
        return exc.exit_code


if __name__ == '__main__':
    sys.exit(main())

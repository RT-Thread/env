"""Create, validate, build and inspect Env plugin packages."""

import argparse
import json
import os
import sys

from ..errors import PluginError, UsageError
from ..manifest import validate_manifest
from ..package import EpackArchive
from .builder import build_project
from .project import default_manifest, default_project_values, ensure_target_available, init_project, validate_project


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
    return parser


def run(argv, context=None):
    parser = _parser()
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
    else:
        raise UsageError("unsupported epack command: %s" % args.command)
    if getattr(args, 'json', False):
        print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    elif args.command == 'validate':
        print('Valid plugin project: %s %s' % (result['id'], result['version']))
    elif args.command == 'build':
        print('Built plugin package: %s' % result['package'])
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

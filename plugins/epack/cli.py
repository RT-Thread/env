"""Create, validate, build and inspect Env plugin packages."""

import argparse
import json
import os
import sys

from ..errors import PluginError, UsageError
from ..package import EpackArchive
from .builder import build_project
from .project import init_project, validate_project


def _path(value, context):
    if context is None:
        return os.path.abspath(value)
    return context.workspace.resolve(value)


def _parser():
    parser = argparse.ArgumentParser(prog='epack', description=__doc__)
    commands = parser.add_subparsers(dest='command')

    init = commands.add_parser('init', help='create a plugin project')
    init.add_argument('directory', nargs='?', default='env-plugin')
    init.add_argument('--id', dest='plugin_id', default='org.example.env-plugin')
    init.add_argument('--name', default='Env Plugin')

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
        target = init_project(_path(args.directory, context), args.plugin_id, args.name)
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

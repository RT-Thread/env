"""Build the official Env ``epack`` plugin from the source checkout."""

import argparse
import json
import os
import sys


REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT_ROOT = os.path.join(REPOSITORY_ROOT, 'plugins', 'bundled', 'epack')
if REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, REPOSITORY_ROOT)

if __package__:
    from .builder import build_project
    from ..errors import PluginError
else:
    from plugins.epack.builder import build_project
    from plugins.errors import PluginError


def _parser():
    parser = argparse.ArgumentParser(
        prog='build_epack',
        description='Build the official org.rt-thread.epack plugin package.',
    )
    parser.add_argument('-o', '--output', help='output directory; defaults to plugins/bundled/epack/dist')
    parser.add_argument(
        '--backend-format',
        choices=('source-wheel', 'pyc-wheel'),
        help='override the backend wheel format from the manifest',
    )
    parser.add_argument('--json', action='store_true', help='write a machine-readable result')
    return parser


def build_official_epack(output_directory=None, backend_format=None):
    output = os.path.abspath(output_directory) if output_directory else None
    return build_project(PROJECT_ROOT, output_directory=output, backend_format=backend_format)


def run(argv=None):
    args = _parser().parse_args(list(argv or sys.argv[1:]))
    package = build_official_epack(args.output, args.backend_format)
    result = {'status': 'ok', 'project': PROJECT_ROOT, 'package': package}
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print('Built official epack plugin package: %s' % package)
    return 0


def main(argv=None):
    try:
        return run(argv)
    except PluginError as exc:
        print('build_epack: %s' % exc, file=sys.stderr)
        return exc.exit_code


if __name__ == '__main__':
    sys.exit(main())

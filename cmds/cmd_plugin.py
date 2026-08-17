# -*- coding:utf-8 -*-
"""Manage local Env plugins."""

import json
import sys

from plugins.errors import PluginError, UsageError
from plugins.market import clear_market_url, load_market_config, save_market_url
from plugins.service import PluginService


def _service(args):
    return PluginService(env_root=args.env_root)


def _print_json(value):
    print(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True))


def _confirm(prompt, assume_yes):
    if assume_yes:
        return
    if not sys.stdin.isatty():
        raise UsageError("confirmation requires an interactive terminal or --yes")
    answer = input(prompt + ' [y/N] ').strip().lower()
    if answer not in ('y', 'yes'):
        raise UsageError('operation cancelled')


def _confirm_package(service, package_path, assume_yes):
    summary = service.inspect_package(package_path)
    if not assume_yes:
        print('Plugin: %s %s (%s)' % (summary['name'], summary['version'], summary['id']))
        print('Source: %s' % summary['path'])
        print('Signature: %s' % summary['signing_status'])
        print('Commands: %s' % ', '.join(command['name'] for command in summary['commands']))
        if summary['permissions']:
            print('Permissions:')
            for permission in summary['permissions']:
                required = 'required' if permission['required'] else 'optional'
                print('  %s (%s): %s' % (permission['name'], required, permission['reason']))
        else:
            print('Permissions: none')
        if summary['signing_status'] == 'unsigned':
            print('WARNING: This local package is unsigned. Its publisher identity cannot be verified.')
        _confirm('Continue?', False)
    return summary


def cmd(args):
    try:
        service = _service(args)
        operation = args.plugin_operation
        if operation == 'install':
            _confirm_package(service, args.package, args.yes)
            result = service.install(args.package, allow_unsigned=args.yes or sys.stdin.isatty())
        elif operation in ('upgrade', 'update'):
            _confirm_package(service, args.package, args.yes)
            result = service.upgrade(args.package, allow_unsigned=args.yes or sys.stdin.isatty())
        elif operation == 'uninstall':
            detail = ' and delete its configuration/data/cache' if args.purge_data else ' and retain its data'
            _confirm('Uninstall %s%s?' % (args.plugin_id, detail), args.yes)
            result = service.uninstall(args.plugin_id, purge_data=args.purge_data)
        elif operation == 'enable':
            result = service.enable(args.plugin_id)
        elif operation == 'disable':
            result = service.disable(args.plugin_id)
        elif operation == 'list':
            result = service.list()
        elif operation == 'info':
            result = service.info(args.plugin_id)
        elif operation == 'doctor':
            result = service.doctor(args.plugin_id)
        elif operation == 'market':
            result = _market_command(service, args)
        else:
            raise UsageError('missing plugin operation')
        _print_result(result, args.json)
    except PluginError as exc:
        print('env plugin: %s' % exc, file=sys.stderr)
        raise SystemExit(exc.exit_code)


def _market_command(service, args):
    action = getattr(args, 'market_operation', None)
    if action == 'set':
        return save_market_url(service.paths, args.market_url)
    if action == 'clear':
        return clear_market_url(service.paths)
    return load_market_config(service.paths)


def _print_result(value, as_json):
    if as_json:
        _print_json(value)
        return
    if isinstance(value, list):
        if not value:
            print('No plugins installed.')
            return
        print('%-40s %-12s %-9s %s' % ('ID', 'VERSION', 'STATUS', 'COMMANDS'))
        for item in value:
            print(
                '%-40s %-12s %-9s %s'
                % (
                    item['id'],
                    item['version'],
                    'enabled' if item['enabled'] else 'disabled',
                    ', '.join(item['commands']),
                )
            )
        return
    if isinstance(value, dict) and 'plugins' in value and 'status' in value:
        print('Plugin doctor: %s' % value['status'])
        for item in value['plugins']:
            print('%s: %s' % (item['id'], item['status']))
            for issue in item['issues']:
                print('  - %s' % issue)
        return
    if isinstance(value, dict) and set(value) >= set(['enabled', 'url', 'source']):
        if value.get('enabled'):
            source = 'environment variable' if value.get('source') == 'env' else 'configuration file'
            print('Plugin market: %s (%s)' % (value['url'], source))
        else:
            print('Plugin market is not configured.')
        return
    if isinstance(value, dict):
        for key in sorted(value):
            current = value[key]
            if isinstance(current, (dict, list)):
                current = json.dumps(current, ensure_ascii=True, sort_keys=True)
            print('%s: %s' % (key, current))


def _add_output_arguments(parser, include_yes=False):
    parser.add_argument('--json', action='store_true', help='write machine-readable JSON')
    if include_yes:
        parser.add_argument('-y', '--yes', action='store_true', help='accept confirmations')


def add_parser(sub):
    parser = sub.add_parser('plugin', help=__doc__, description=__doc__)
    parser.add_argument('--env-root', help='override the Env data root')
    operations = parser.add_subparsers(dest='plugin_operation')

    install = operations.add_parser('install', help='install a local .epack')
    install.add_argument('package')
    _add_output_arguments(install, include_yes=True)

    for name in ('upgrade', 'update'):
        upgrade = operations.add_parser(name, help='upgrade from a local .epack')
        upgrade.add_argument('package')
        _add_output_arguments(upgrade, include_yes=True)

    uninstall = operations.add_parser('uninstall', help='uninstall a plugin')
    uninstall.add_argument('plugin_id')
    uninstall.add_argument('--purge-data', action='store_true', help='also delete plugin configuration, data and cache')
    _add_output_arguments(uninstall, include_yes=True)

    for name in ('enable', 'disable', 'info'):
        operation = operations.add_parser(name, help='%s a plugin' % name)
        operation.add_argument('plugin_id')
        _add_output_arguments(operation)

    list_parser = operations.add_parser('list', help='list installed plugins')
    _add_output_arguments(list_parser)

    doctor = operations.add_parser('doctor', help='diagnose plugin state')
    doctor.add_argument('plugin_id', nargs='?')
    _add_output_arguments(doctor)

    market = operations.add_parser('market', help='show or configure the online plugin market URL')
    _add_output_arguments(market)
    market_ops = market.add_subparsers(dest='market_operation')
    market_set = market_ops.add_parser('set', help='save the online plugin market URL')
    market_set.add_argument('market_url')
    _add_output_arguments(market_set)
    market_clear = market_ops.add_parser('clear', help='remove the online plugin market URL')
    _add_output_arguments(market_clear)

    parser.set_defaults(func=cmd)

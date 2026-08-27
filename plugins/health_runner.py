"""Subprocess health probe for a staged plugin backend."""

import importlib
import inspect
import json
import os
import sys


def _load_entry(entry, site_packages):
    module_name, attribute = entry.split(':', 1)
    module = importlib.import_module(module_name)
    value = getattr(module, attribute, None)
    if not callable(value):
        raise TypeError("entry is not callable: %s" % entry)
    module_file = getattr(module, '__file__', None)
    if not module_file or os.path.commonpath([site_packages, os.path.abspath(module_file)]) != site_packages:
        raise TypeError("entry module is not provided by the plugin backend: %s" % entry)
    return value


def _accepts_command_abi(value, entry):
    try:
        signature = inspect.signature(value)
        signature.bind([], object())
    except (TypeError, ValueError):
        raise TypeError("command entry must accept (argv, context): %s" % entry)


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    if len(argv) != 2:
        print('health runner requires MANIFEST SITE_PACKAGES', file=sys.stderr)
        return 2
    manifest_path, site_packages = argv
    sys.path.insert(0, os.path.abspath(site_packages))
    with open(manifest_path, 'r', encoding='utf-8') as source:
        manifest = json.load(source)
    for command in manifest['commands']:
        entry = _load_entry(command['entry'], os.path.abspath(site_packages))
        _accepts_command_abi(entry, command['entry'])
    service = manifest.get('service')
    if service:
        _load_entry(service['entry'], os.path.abspath(site_packages))
    health_entry = manifest.get('health_check')
    if health_entry:
        result = _load_entry(health_entry, os.path.abspath(site_packages))()
        succeeded = result is None or result is True or (type(result) is int and result == 0)
        if not succeeded:
            raise RuntimeError("health check returned %r" % (result,))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('plugin health check failed: %s' % exc, file=sys.stderr)
        sys.exit(1)

"""Mandatory dispatcher for installed plugin commands."""

import importlib
import os
import sys

from .compatibility import ensure_compatible
from .errors import DispatchError, PluginError
from .manifest import validate_manifest
from .paths import PluginPaths
from .sdk import create_runtime_context
from .store import FileLock, StateStore


_SAFE_ENVIRONMENT = frozenset(
    [
        'COMSPEC',
        'ENV_ROOT',
        'HOME',
        'LANG',
        'LC_ALL',
        'PATH',
        'PATHEXT',
        'SYSTEMROOT',
        'TEMP',
        'TERM',
        'TMP',
        'TMPDIR',
        'USERPROFILE',
        'WINDIR',
    ]
)


def _load_command(state, command_name, paths):
    plugin_id = state['commands'].get(command_name)
    if plugin_id is None:
        raise DispatchError("plugin command is not registered: %s" % command_name)
    record = state['plugins'].get(plugin_id)
    if record is None:
        raise DispatchError("plugin command owner is missing: %s" % plugin_id)
    if not record['enabled']:
        raise DispatchError("plugin is disabled: %s" % plugin_id)
    version = record['active_version']
    version_record = record['versions'].get(version)
    if version_record is None:
        raise DispatchError("active plugin version is missing: %s" % version)
    manifest = validate_manifest(version_record['manifest'])
    ensure_compatible(manifest)
    command = manifest.command(command_name)
    if command is None:
        raise DispatchError("active plugin no longer declares command: %s" % command_name)
    required = set(permission['name'] for permission in manifest.permissions if permission['required'])
    granted = set(record['granted_permissions'])
    missing = sorted(required - granted)
    if missing:
        raise DispatchError("required permissions are not granted: %s" % ', '.join(missing))
    install_dir = paths.from_root(version_record['install_dir'])
    site_packages = os.path.join(install_dir, 'site-packages')
    if not os.path.isdir(site_packages):
        raise DispatchError("plugin backend is missing: %s" % plugin_id)
    return plugin_id, version, command, sorted(granted), site_packages


def dispatch(command_name, argv, env_root=None, workspace_root=None):
    paths = PluginPaths(env_root=env_root)
    paths.ensure()
    store = StateStore(paths)
    with store.lock():
        state = store.load()
        owner = state['commands'].get(command_name)
        if owner is None:
            raise DispatchError("plugin command is not registered: %s" % command_name)

    with FileLock(paths.runtime_lock(owner)):
        with store.lock():
            state = store.load()
            plugin_id, version, command, permissions, site_packages = _load_command(state, command_name, paths)
            if plugin_id != owner:
                raise DispatchError("plugin command ownership changed while dispatching: %s" % command_name)

        return _execute(plugin_id, version, command, permissions, site_packages, paths, argv, workspace_root)


def _execute(plugin_id, version, command, permissions, site_packages, paths, argv, workspace_root):

    sys.path.insert(0, site_packages)
    original_environment = dict(os.environ)
    imported_before = set(sys.modules)
    try:
        context = create_runtime_context(paths, plugin_id, version, permissions, workspace_root=workspace_root)
        for name in list(os.environ):
            if name.upper() not in _SAFE_ENVIRONMENT:
                del os.environ[name]
        module_name, attribute = command['entry'].split(':', 1)
        module = importlib.import_module(module_name)
        module_file = getattr(module, '__file__', None)
        if not module_file or os.path.commonpath([site_packages, os.path.abspath(module_file)]) != site_packages:
            raise DispatchError("plugin entry module is outside its backend: %s" % command['entry'])
        entry = getattr(module, attribute, None)
        if not callable(entry):
            raise DispatchError("plugin entry is not callable: %s" % command['entry'])
        result = entry(list(argv), context)
        if result is None:
            return 0
        if not isinstance(result, int):
            raise DispatchError("plugin command returned a non-integer exit status")
        return result
    finally:
        os.environ.clear()
        os.environ.update(original_environment)
        for name in set(sys.modules) - imported_before:
            module = sys.modules.get(name)
            module_file = getattr(module, '__file__', None)
            if module_file:
                try:
                    if os.path.commonpath([site_packages, os.path.abspath(module_file)]) == site_packages:
                        del sys.modules[name]
                except ValueError:
                    pass
        try:
            sys.path.remove(site_packages)
        except ValueError:
            pass


def launcher_main(argv=None):
    argv = list(argv or sys.argv[1:])
    if not argv:
        print('plugin dispatcher requires a command name', file=sys.stderr)
        return 2
    try:
        return dispatch(argv[0], argv[1:])
    except PluginError as exc:
        print('env plugin: %s' % exc, file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print('env plugin: command failed: %s' % exc, file=sys.stderr)
        return 5


if __name__ == '__main__':
    sys.exit(launcher_main())

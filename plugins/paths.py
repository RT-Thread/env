"""Filesystem locations owned by the plugin subsystem."""

import os
import platform
import sysconfig


def default_env_root():
    configured = os.environ.get('ENV_ROOT')
    if configured:
        return os.path.abspath(configured)
    if platform.system() == 'Windows':
        base = os.environ.get('USERPROFILE') or os.path.expanduser('~')
    else:
        base = os.environ.get('HOME') or os.path.expanduser('~')
    return os.path.abspath(os.path.join(base, '.env'))


class PluginPaths(object):
    def __init__(self, env_root=None, launcher_dir=None):
        self.env_root = os.path.abspath(env_root or default_env_root())
        self.root = os.path.join(self.env_root, 'var', 'plugins')
        self.state_file = os.path.join(self.root, 'state-v1.json')
        self.lock_file = os.path.join(self.root, 'state.lock')
        self.installed = os.path.join(self.root, 'installed')
        self.staging = os.path.join(self.root, 'staging')
        self.config = os.path.join(self.root, 'config')
        self.data = os.path.join(self.root, 'data')
        self.cache = os.path.join(self.root, 'cache')
        self.runtime = os.path.join(self.root, 'runtime')
        configured_launcher_dir = os.environ.get('ENV_PLUGIN_LAUNCHER_DIR')
        self.launchers = os.path.abspath(launcher_dir or configured_launcher_dir or sysconfig.get_path('scripts'))

    def ensure(self):
        for path in (
            self.root,
            self.installed,
            self.staging,
            self.config,
            self.data,
            self.cache,
            self.runtime,
            self.launchers,
        ):
            os.makedirs(path, exist_ok=True)

    def version_dir(self, plugin_id, version):
        return os.path.join(self.installed, plugin_id, version)

    def runtime_lock(self, plugin_id):
        return os.path.join(self.runtime, plugin_id + '.lock')

    def relative_to_root(self, path):
        return os.path.relpath(os.path.abspath(path), self.root)

    def from_root(self, relative_path):
        result = os.path.abspath(os.path.join(self.root, relative_path))
        if os.path.commonpath([self.root, result]) != self.root:
            raise ValueError("path escapes plugin root: %s" % relative_path)
        return result

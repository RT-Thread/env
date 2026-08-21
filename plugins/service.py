"""Shared plugin lifecycle facade for Env CLI and WebUI adapters."""

from .installer import PluginInstaller
from .backend import BackendServiceManager
from .launchers import LauncherManager
from .paths import PluginPaths
from .store import StateStore


class PluginService(object):
    def __init__(self, env_root=None, launcher_dir=None, system=None, python_executable=None, dispatcher_module=None):
        self.paths = PluginPaths(env_root=env_root, launcher_dir=launcher_dir)
        launchers = LauncherManager(
            self.paths,
            system=system,
            python_executable=python_executable,
            dispatcher_module=dispatcher_module,
        )
        self.installer = PluginInstaller(self.paths, launcher_manager=launchers, store=StateStore(self.paths))
        self.backend = BackendServiceManager(self.paths, store=self.installer.store)

    def inspect_package(self, path):
        return self.installer.inspect(path).summary()

    def install(self, path, allow_unsigned=False):
        return self.installer.install(path, allow_unsigned=allow_unsigned, upgrade=False)

    def upgrade(self, path, allow_unsigned=False):
        plugin_id = self._package_plugin_id(path)
        if plugin_id:
            self.stop_backend(plugin_id)
        return self.installer.install(path, allow_unsigned=allow_unsigned, upgrade=True)

    def uninstall(self, plugin_id, purge_data=False):
        self.stop_backend(plugin_id)
        return self.installer.uninstall(plugin_id, purge_data=purge_data)

    def enable(self, plugin_id):
        return self.installer.set_enabled(plugin_id, True)

    def disable(self, plugin_id):
        self.stop_backend(plugin_id)
        return self.installer.set_enabled(plugin_id, False)

    def set_permissions(self, plugin_id, permissions):
        self.stop_backend(plugin_id)
        return self.installer.set_permissions(plugin_id, permissions)

    def list(self):
        return self.installer.list_plugins()

    def info(self, plugin_id):
        return self.installer.info(plugin_id)

    def doctor(self, plugin_id=None):
        return self.installer.doctor(plugin_id)

    def resolve_webui_asset(self, plugin_id, asset_path=None):
        return self.installer.resolve_webui_asset(plugin_id, asset_path=asset_path)

    def backend_port(self, plugin_id, workspace):
        return self.backend.ensure(plugin_id, workspace)

    def stop_backend(self, plugin_id):
        self.backend.stop(plugin_id)

    def stop_backends(self):
        self.backend.stop_all()

    def _package_plugin_id(self, path):
        try:
            return self.installer.inspect(path).manifest.plugin_id
        except Exception:
            return None

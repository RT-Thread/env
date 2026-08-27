"""Lifecycle manager for plugin backend services."""

import http.client
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from .compatibility import ensure_compatible
from .errors import StateError, UsageError
from .manifest import validate_manifest
from .store import FileLock, StateStore


class BackendUnavailableError(RuntimeError):
    pass


class BackendServiceManager(object):
    def __init__(self, paths, store=None):
        self.paths = paths
        self.store = store or StateStore(paths)
        self._lock = threading.RLock()
        self._services = {}

    def ensure(self, plugin_id, workspace):
        workspace = os.path.abspath(workspace)
        with self._lock:
            current = self._services.get(plugin_id)
            if current and current['workspace'] == workspace and current['process'].poll() is None:
                return current['port']
            if current:
                self._stop_locked(plugin_id, current)
            _record, manifest, install_dir, permissions = self._plugin(plugin_id)
            if not manifest.service:
                raise StateError('plugin does not provide a backend service: %s' % plugin_id)
            if not os.path.isdir(workspace):
                raise UsageError('backend workspace is not a directory: %s' % workspace)
            port = _free_port()
            runtime_dir = os.path.join(self.paths.runtime, plugin_id)
            os.makedirs(runtime_dir, exist_ok=True)
            log_path = os.path.join(runtime_dir, 'service.log')
            site_packages = os.path.join(install_dir, 'site-packages')
            module_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            environment = _service_environment(site_packages, module_root)
            command = [
                sys.executable,
                '-m',
                'plugins.service_runner',
                '--entry',
                manifest.service['entry'],
                '--env-root',
                self.paths.env_root,
                '--plugin-id',
                plugin_id,
                '--version',
                manifest.version,
                '--permissions',
                ','.join(sorted(permissions)),
                '--workspace',
                workspace,
                '--host',
                '127.0.0.1',
                '--port',
                str(port),
            ]
            log_file = open(log_path, 'ab')
            try:
                process = subprocess.Popen(
                    command,
                    cwd=install_dir,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    close_fds=(os.name != 'nt'),
                    creationflags=(getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) if os.name == 'nt' else 0),
                    start_new_session=(os.name != 'nt'),
                )
            except Exception:
                log_file.close()
                raise
            log_file.close()
            service = {'process': process, 'port': port, 'workspace': workspace, 'log': log_path}
            self._services[plugin_id] = service
            try:
                _wait_health(process, port, manifest.service['health_path'], manifest.service['start_timeout'])
            except BackendUnavailableError:
                self._stop_locked(plugin_id, service)
                self._services.pop(plugin_id, None)
                raise
            except Exception:
                self._stop_locked(plugin_id, service)
                self._services.pop(plugin_id, None)
                raise BackendUnavailableError('plugin backend did not become ready')
            return port

    def stop(self, plugin_id):
        with self._lock:
            service = self._services.pop(plugin_id, None)
            if service:
                self._stop_locked(plugin_id, service)

    def stop_all(self):
        with self._lock:
            services = list(self._services.items())
            self._services.clear()
            for plugin_id, service in services:
                self._stop_locked(plugin_id, service)

    def _stop_locked(self, plugin_id, service):
        process = service['process']
        if process.poll() is not None:
            return
        try:
            if os.name == 'nt' and hasattr(process, 'send_signal'):
                process.send_signal(getattr(signal, 'CTRL_BREAK_EVENT', 1))
            else:
                process.terminate()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass

    def _plugin(self, plugin_id):
        with FileLock(self.paths.lock_file, shared=True):
            state = self.store.load()
        record = state['plugins'].get(plugin_id)
        if record is None:
            raise StateError('plugin is not installed: %s' % plugin_id)
        if not record['enabled']:
            raise StateError('plugin is disabled: %s' % plugin_id)
        version = record['versions'].get(record['active_version'])
        if version is None:
            raise StateError('active plugin version is missing: %s' % plugin_id)
        manifest = validate_manifest(version['manifest'])
        ensure_compatible(manifest)
        required = set(permission['name'] for permission in manifest.permissions if permission['required'])
        granted = set(record['granted_permissions'])
        missing = sorted(required - granted)
        if missing:
            raise StateError('required permissions are not granted: %s' % ', '.join(missing))
        return record, manifest, self.paths.from_root(version['install_dir']), granted


def _service_environment(site_packages, module_root):
    environment = {}
    for name in ('PATH', 'SYSTEMROOT', 'COMSPEC', 'PATHEXT', 'WINDIR', 'LANG', 'LC_ALL', 'TMP', 'TEMP', 'TMPDIR'):
        if name in os.environ:
            environment[name] = os.environ[name]
    environment['PYTHONPATH'] = os.pathsep.join([site_packages, module_root])
    return environment


def _free_port():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]
    finally:
        probe.close()


def _wait_health(process, port, path, timeout):
    deadline = time.monotonic() + timeout
    last_error = 'service did not become ready'
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise BackendUnavailableError('plugin service exited with status %s' % process.returncode)
        try:
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=0.5)
            connection.request('GET', path)
            response = connection.getresponse()
            response.read()
            connection.close()
            if 200 <= response.status < 300:
                return
            last_error = 'health check returned HTTP %s' % response.status
        except (OSError, http.client.HTTPException) as exc:
            last_error = str(exc)
        time.sleep(0.05)
    raise BackendUnavailableError(last_error)

"""Cross-platform command launcher management."""

import os
import shlex
import shutil
import sys
import tempfile

from .errors import CommandConflictError, TransactionError


MARKER = 'ENV_PLUGIN_LAUNCHER_V1'


class LauncherManager(object):
    def __init__(self, paths, system=None, python_executable=None, dispatcher_module=None):
        self.paths = paths
        self.system = (system or ('windows' if os.name == 'nt' else 'posix')).lower()
        self.python_executable = os.path.abspath(python_executable or sys.executable)
        package_dir = os.path.dirname(os.path.abspath(__file__))
        if __package__.startswith('env.'):
            self.dispatcher_module = dispatcher_module or 'env.plugins.dispatcher'
            self.module_root = os.path.dirname(os.path.dirname(package_dir))
        else:
            self.dispatcher_module = dispatcher_module or 'plugins.dispatcher'
            self.module_root = os.path.dirname(package_dir)

    def path(self, command):
        suffix = '.cmd' if self.system == 'windows' else ''
        return os.path.join(self.paths.launchers, command + suffix)

    def exists(self, command):
        return os.path.exists(self.path(command))

    def is_managed(self, command):
        path = self.path(command)
        try:
            with open(path, 'rb') as launcher:
                return MARKER.encode('ascii') in launcher.read(512)
        except OSError:
            return False

    def ensure_available(self, command, owned=False):
        path = self.path(command)
        if os.path.exists(path) and not (owned and self.is_managed(command)):
            raise CommandConflictError("launcher path already exists: %s" % path)
        discovered = shutil.which(command)
        if discovered and os.path.normcase(os.path.abspath(discovered)) != os.path.normcase(os.path.abspath(path)):
            raise CommandConflictError("command already exists on PATH: %s (%s)" % (command, discovered))

    def snapshot(self, commands):
        result = {}
        for command in set(commands):
            path = self.path(command)
            if os.path.exists(path):
                try:
                    with open(path, 'rb') as launcher:
                        result[path] = (launcher.read(), os.stat(path).st_mode)
                except OSError as exc:
                    raise TransactionError("cannot snapshot launcher %s: %s" % (path, exc))
            else:
                result[path] = None
        return result

    def restore(self, snapshot):
        for path, saved in snapshot.items():
            if saved is None:
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                except OSError:
                    pass
                continue
            content, mode = saved
            self._atomic_write(path, content, mode & 0o777)

    def write(self, command):
        self.paths.ensure()
        if self.system == 'windows':
            content = (
                '@echo off\r\n'
                'REM %s\r\n'
                'set "ENV_ROOT=%s"\r\n'
                'set "PYTHONPATH=%s;%%PYTHONPATH%%"\r\n'
                '"%s" -m %s %s %%*\r\n'
                'exit /b %%errorlevel%%\r\n'
                % (
                    MARKER,
                    self.paths.env_root,
                    self.module_root,
                    self.python_executable,
                    self.dispatcher_module,
                    command,
                )
            ).encode('utf-8')
            mode = 0o644
        else:
            content = (
                '#!/bin/sh\n'
                '# %s\n'
                'ENV_ROOT=%s PYTHONPATH=%s${PYTHONPATH:+:$PYTHONPATH} exec %s -m %s %s "$@"\n'
                % (
                    MARKER,
                    shlex.quote(self.paths.env_root),
                    shlex.quote(self.module_root),
                    shlex.quote(self.python_executable),
                    shlex.quote(self.dispatcher_module),
                    shlex.quote(command),
                )
            ).encode('utf-8')
            mode = 0o755
        self._atomic_write(self.path(command), content, mode)

    def remove(self, command):
        path = self.path(command)
        if not os.path.exists(path):
            return
        if not self.is_managed(command):
            raise TransactionError("refusing to remove unmanaged launcher: %s" % path)
        try:
            os.unlink(path)
        except OSError as exc:
            raise TransactionError("cannot remove launcher %s: %s" % (path, exc))

    def _atomic_write(self, path, content, mode):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        descriptor = None
        temporary = None
        try:
            descriptor, temporary = tempfile.mkstemp(prefix='.launcher-', dir=os.path.dirname(path))
            with os.fdopen(descriptor, 'wb') as launcher:
                descriptor = None
                launcher.write(content)
                launcher.flush()
                os.fsync(launcher.fileno())
            os.chmod(temporary, mode)
            os.replace(temporary, path)
            temporary = None
        except OSError as exc:
            raise TransactionError("cannot write launcher %s: %s" % (path, exc))
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

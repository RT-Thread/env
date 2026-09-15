"""Cross-platform command launcher management."""

import json
import glob
import os
import shlex
import shutil
import sys
import tempfile
import time

from .errors import CommandConflictError, TransactionError
from .manifest import is_windows_reserved_command


MARKER = 'ENV_PLUGIN_LAUNCHER_V1'


class LauncherManager(object):
    def __init__(self, paths, system=None, python_executable=None, dispatcher_module=None):
        self.paths = paths
        self.system = (system or ('windows' if os.name == 'nt' else 'posix')).lower()
        self.python_executable = os.path.abspath(python_executable or sys.executable)
        package_dir = os.path.dirname(os.path.abspath(__file__))
        # Source checkouts import ``plugins`` directly; installed wheels expose
        # the same files below the ``env.plugins`` package.
        package_name = __package__ or 'plugins'
        if package_name.startswith('env.'):
            default_dispatcher = 'env.plugins.dispatcher'
            self.module_root = os.path.dirname(os.path.dirname(package_dir))
        else:
            default_dispatcher = 'plugins.dispatcher'
            self.module_root = os.path.dirname(package_dir)
        self.dispatcher_module = dispatcher_module or default_dispatcher

    def path(self, command):
        suffix = '.cmd' if self.system == 'windows' else ''
        return os.path.join(self.paths.launchers, command + suffix)

    def helper_path(self, command):
        return os.path.join(self.paths.launchers, '.env-plugin-launcher-%s.py' % command)

    def exists(self, command):
        return os.path.exists(self.path(command))

    def is_managed(self, command):
        return self._is_managed_file(self.path(command))

    def _is_managed_file(self, path):
        try:
            with open(path, 'rb') as launcher:
                content = launcher.read(1024)
                if content.startswith((b'\xff\xfe', b'\xfe\xff')):
                    try:
                        text = content.decode('utf-16')
                    except UnicodeDecodeError:
                        return False
                else:
                    try:
                        text = content.decode('utf-8')
                    except UnicodeDecodeError:
                        return False
                return MARKER in text
        except OSError:
            return False

    def ensure_available(self, command, owned=False):
        if is_windows_reserved_command(command):
            raise CommandConflictError("launcher name is reserved on Windows: %s" % command)
        path = self.path(command)
        if os.path.exists(path) and not (owned and self.is_managed(command)):
            raise CommandConflictError("launcher path already exists: %s" % path)
        if self.system == 'windows':
            helper = self.helper_path(command)
            if os.path.exists(helper) and not (owned and self._is_managed_file(helper)):
                raise CommandConflictError("launcher helper path already exists: %s" % helper)
        discovered = shutil.which(command)
        if discovered and os.path.normcase(os.path.abspath(discovered)) != os.path.normcase(os.path.abspath(path)):
            raise CommandConflictError("command already exists on PATH: %s (%s)" % (command, discovered))

    def snapshot(self, commands):
        result = {}
        for command in set(commands):
            paths = [self.path(command)]
            if self.system == 'windows':
                paths.append(self.helper_path(command))
            for path in paths:
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
            helper = self.helper_path(command)
            helper_content = self._windows_helper_content(command).encode('ascii')
            self._atomic_write(helper, helper_content, 0o644)
            python_command = self.python_executable
            try:
                python_command.encode('ascii')
            except UnicodeEncodeError:
                python_command = 'python'
            if any(character in python_command for character in ('%', '!')):
                python_command = 'python'
            content = (
                '@"%s" "%%~dp0%s" %%* & rem %s\r\n'
                % (
                    python_command,
                    os.path.basename(helper),
                    MARKER,
                )
            ).encode('ascii')
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
        helper = self.helper_path(command) if self.system == 'windows' else None
        if helper and os.path.exists(helper) and not self._is_managed_file(helper):
            raise TransactionError("refusing to remove unmanaged launcher helper: %s" % helper)
        try:
            if self.system == 'windows':
                self._wait_for_running_command(command)
            if helper and os.path.exists(helper):
                os.unlink(helper)
            os.unlink(path)
        except OSError as exc:
            raise TransactionError("cannot remove launcher %s: %s" % (path, exc))

    def _wait_for_running_command(self, command):
        pattern = os.path.join(self.paths.launchers, '.env-plugin-launcher-%s.*.running' % command)
        deadline = time.monotonic() + 10.0
        while glob.glob(pattern):
            if time.monotonic() >= deadline:
                raise TransactionError("cannot remove launcher while it is running: %s" % command)
            time.sleep(0.05)

    def _windows_helper_content(self, command):
        values = {
            'env_root': self.paths.env_root,
            'module_root': self.module_root,
            'python_executable': self.python_executable,
            'dispatcher_module': self.dispatcher_module,
            'command': command,
        }
        watcher = (
            'import ctypes\n'
            'import os\n'
            'import sys\n'
            'import time\n'
            'from ctypes import wintypes\n'
            '\n'
            'parent = int(sys.argv[1])\n'
            'marker = sys.argv[2]\n'
            'kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)\n'
            'kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]\n'
            'kernel32.OpenProcess.restype = wintypes.HANDLE\n'
            'kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]\n'
            'kernel32.WaitForSingleObject.restype = wintypes.DWORD\n'
            'kernel32.CloseHandle.argtypes = [wintypes.HANDLE]\n'
            'kernel32.CloseHandle.restype = wintypes.BOOL\n'
            'handle = kernel32.OpenProcess(0x00100000, False, parent)\n'
            'if handle:\n'
            '    kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)\n'
            '    kernel32.CloseHandle(handle)\n'
            'else:\n'
            '    time.sleep(0.1)\n'
            'try:\n'
            '    os.unlink(marker)\n'
            'except OSError:\n'
            '    pass\n'
        )
        return (
            '# ENV_PLUGIN_LAUNCHER_V1\n'
            'import json\n'
            'import os\n'
            'import subprocess\n'
            'import sys\n'
            '\n'
            'CONFIG = json.loads(%s)\n'
            'WATCHER = %s\n'
            '\n'
            'def main():\n'
            '    environment = os.environ.copy()\n'
            '    environment["ENV_ROOT"] = CONFIG["env_root"]\n'
            '    existing = environment.get("PYTHONPATH")\n'
            '    environment["PYTHONPATH"] = os.pathsep.join(\n'
            '        item for item in (CONFIG["module_root"], existing) if item\n'
            '    )\n'
            '    marker = os.path.join(\n'
            '        os.path.dirname(__file__),\n'
            '        ".env-plugin-launcher-%%s.%%s.running" %% (CONFIG["command"], os.getpid()),\n'
            '    )\n'
            '    with open(marker, "w", encoding="ascii") as output:\n'
            '        output.write(str(os.getppid()))\n'
            '    try:\n'
            '        return subprocess.call(\n'
            '            [CONFIG["python_executable"], "-m", CONFIG["dispatcher_module"], CONFIG["command"]]\n'
            '            + sys.argv[1:],\n'
            '            env=environment,\n'
            '        )\n'
            '    finally:\n'
            '        try:\n'
            '            subprocess.Popen(\n'
            '                [sys.executable, "-c", WATCHER, str(os.getppid()), marker],\n'
            '                close_fds=True,\n'
            '                stdin=subprocess.DEVNULL,\n'
            '                stdout=subprocess.DEVNULL,\n'
            '                stderr=subprocess.DEVNULL,\n'
            '                cwd=os.path.dirname(CONFIG["python_executable"]),\n'
            '                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),\n'
            '            )\n'
            '        except OSError:\n'
            '            try:\n'
            '                os.unlink(marker)\n'
            '            except OSError:\n'
            '                pass\n'
            '\n'
            'if __name__ == "__main__":\n'
            '    sys.exit(main())\n'
        ) % (
            json.dumps(json.dumps(values, ensure_ascii=True), ensure_ascii=True),
            json.dumps(watcher, ensure_ascii=True),
        )

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

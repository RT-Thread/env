"""Locked and atomic JSON state persistence."""

import copy
import json
import os
import tempfile

from .errors import StateError


STATE_SCHEMA_VERSION = 1


if os.name == 'nt':
    import ctypes
    from ctypes import wintypes

    class _Overlapped(ctypes.Structure):
        _fields_ = [
            ('internal', ctypes.c_void_p),
            ('internal_high', ctypes.c_void_p),
            ('offset', wintypes.DWORD),
            ('offset_high', wintypes.DWORD),
            ('event', wintypes.HANDLE),
        ]

    _LOCKFILE_EXCLUSIVE_LOCK = 0x00000002


def _lock_windows(handle, shared):
    import msvcrt

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.LockFileEx.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_Overlapped),
    ]
    kernel32.LockFileEx.restype = wintypes.BOOL
    overlapped = _Overlapped()
    flags = 0 if shared else _LOCKFILE_EXCLUSIVE_LOCK
    file_handle = wintypes.HANDLE(msvcrt.get_osfhandle(handle))
    if not kernel32.LockFileEx(file_handle, flags, 0, 1, 0, ctypes.byref(overlapped)):
        raise ctypes.WinError(ctypes.get_last_error())
    return kernel32, file_handle, overlapped


def _unlock_windows(lock):
    kernel32, file_handle, overlapped = lock
    kernel32.UnlockFileEx.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_Overlapped),
    ]
    kernel32.UnlockFileEx.restype = wintypes.BOOL
    if not kernel32.UnlockFileEx(file_handle, 0, 1, 0, ctypes.byref(overlapped)):
        raise ctypes.WinError(ctypes.get_last_error())


def empty_state():
    return {'schema_version': STATE_SCHEMA_VERSION, 'plugins': {}, 'commands': {}}


class FileLock(object):
    def __init__(self, path, shared=False):
        self.path = path
        self.shared = bool(shared)
        self.handle = None
        self._windows_lock = None

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        try:
            self.handle = open(self.path, 'a+b')
            self.handle.seek(0)
            if os.name == 'nt':
                if os.path.getsize(self.path) == 0:
                    self.handle.write(b'0')
                    self.handle.flush()
                    self.handle.seek(0)
                self._windows_lock = _lock_windows(self.handle.fileno(), self.shared)
            else:
                import fcntl

                mode = fcntl.LOCK_SH if self.shared else fcntl.LOCK_EX
                fcntl.flock(self.handle.fileno(), mode)
        except Exception:
            if self.handle is not None:
                self.handle.close()
                self.handle = None
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.handle is None:
            return
        try:
            self.handle.seek(0)
            if os.name == 'nt':
                _unlock_windows(self._windows_lock)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None
            self._windows_lock = None


class StateStore(object):
    def __init__(self, paths):
        self.paths = paths

    def lock(self):
        return FileLock(self.paths.lock_file)

    def load(self):
        if not os.path.exists(self.paths.state_file):
            return empty_state()
        try:
            with open(self.paths.state_file, 'r', encoding='utf-8') as state_file:
                state = json.load(state_file)
        except (OSError, ValueError) as exc:
            raise StateError("cannot read plugin state: %s" % exc)
        self._validate(state)
        return state

    def save(self, state):
        self._validate(state)
        self.paths.ensure()
        descriptor = None
        temporary = None
        try:
            descriptor, temporary = tempfile.mkstemp(prefix='.state-', suffix='.json', dir=self.paths.root)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as state_file:
                descriptor = None
                json.dump(state, state_file, ensure_ascii=True, indent=2, sort_keys=True)
                state_file.write('\n')
                state_file.flush()
                os.fsync(state_file.fileno())
            os.replace(temporary, self.paths.state_file)
            temporary = None
            if hasattr(os, 'O_DIRECTORY'):
                directory_fd = os.open(self.paths.root, os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        except OSError as exc:
            raise StateError("cannot write plugin state: %s" % exc)
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def copy(self, state):
        return copy.deepcopy(state)

    def _validate(self, state):
        if not isinstance(state, dict) or set(state) != set(['schema_version', 'plugins', 'commands']):
            raise StateError("invalid plugin state structure")
        if state['schema_version'] != STATE_SCHEMA_VERSION:
            raise StateError("unsupported plugin state schema_version: %r" % state['schema_version'])
        if not isinstance(state['plugins'], dict) or not isinstance(state['commands'], dict):
            raise StateError("plugin state maps are invalid")
        for command, plugin_id in state['commands'].items():
            if plugin_id not in state['plugins']:
                raise StateError("command %s references missing plugin %s" % (command, plugin_id))

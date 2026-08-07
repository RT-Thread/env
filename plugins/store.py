"""Locked and atomic JSON state persistence."""

import copy
import json
import os
import tempfile

from .errors import StateError


STATE_SCHEMA_VERSION = 1


def empty_state():
    return {'schema_version': STATE_SCHEMA_VERSION, 'plugins': {}, 'commands': {}}


class FileLock(object):
    def __init__(self, path):
        self.path = path
        self.handle = None

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.handle = open(self.path, 'a+b')
        self.handle.seek(0)
        if os.name == 'nt':
            import msvcrt

            if os.path.getsize(self.path) == 0:
                self.handle.write(b'0')
                self.handle.flush()
                self.handle.seek(0)
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.handle is None:
            return
        try:
            self.handle.seek(0)
            if os.name == 'nt':
                import msvcrt

                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


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

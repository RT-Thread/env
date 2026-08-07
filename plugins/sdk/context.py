"""Runtime context and controlled workspace access."""

import json
import logging
import os
import platform
import tempfile

from ..compatibility import current_env_version
from ..errors import PermissionDenied, WorkspaceBoundaryError


_SENSITIVE_PARTS = frozenset(['.git-credentials', '.gnupg', '.ssh'])
_SENSITIVE_NAMES = frozenset(['.env', 'id_dsa', 'id_ecdsa', 'id_ed25519', 'id_rsa'])
_SENSITIVE_SUFFIXES = ('.key', '.pem', '.p12', '.pfx')


def _display_name(paths):
    configured = os.environ.get('ENV_USER_DISPLAY_NAME', '').strip()
    if configured:
        return configured
    config_path = os.path.join(paths.root, 'user.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as source:
            value = json.load(source).get('display_name', '').strip()
            if value:
                return value
    except (OSError, AttributeError, ValueError):
        pass
    return platform.node() or 'local-user'


def _language():
    value = os.environ.get('LANG', 'en')
    return value.split('.', 1)[0].replace('_', '-') or 'en'


class Workspace(object):
    def __init__(self, root, permissions):
        self.root = os.path.realpath(os.path.abspath(root))
        self.permissions = frozenset(permissions)

    def resolve(self, relative_path, sensitive=False):
        if not isinstance(relative_path, str) or not relative_path or os.path.isabs(relative_path):
            raise WorkspaceBoundaryError("workspace path must be a non-empty relative path")
        normalized = os.path.normpath(relative_path)
        if normalized == '..' or normalized.startswith('..' + os.sep):
            raise WorkspaceBoundaryError("workspace path cannot contain parent traversal")
        candidate = os.path.realpath(os.path.join(self.root, normalized))
        try:
            inside = os.path.commonpath([self.root, candidate]) == self.root
        except ValueError:
            inside = False
        if not inside:
            raise WorkspaceBoundaryError("workspace path resolves outside the workspace")
        if not sensitive and self._is_sensitive(normalized):
            raise PermissionDenied("sensitive workspace path requires a future dedicated permission")
        return candidate

    def read_bytes(self, relative_path):
        self._require_read()
        path = self.resolve(relative_path)
        with open(path, 'rb') as source:
            return source.read()

    def read_text(self, relative_path, encoding='utf-8'):
        return self.read_bytes(relative_path).decode(encoding)

    def write_bytes(self, relative_path, content):
        self._require_write()
        if not isinstance(content, bytes):
            raise TypeError('content must be bytes')
        path = self.resolve(relative_path)
        parent = os.path.dirname(path)
        if not os.path.isdir(parent):
            raise WorkspaceBoundaryError("workspace parent directory does not exist")
        descriptor = None
        temporary = None
        try:
            descriptor, temporary = tempfile.mkstemp(prefix='.env-plugin-', dir=parent)
            with os.fdopen(descriptor, 'wb') as output:
                descriptor = None
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
            temporary = None
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def write_text(self, relative_path, content, encoding='utf-8'):
        if not isinstance(content, str):
            raise TypeError('content must be text')
        self.write_bytes(relative_path, content.encode(encoding))

    def _require_read(self):
        if 'workspace.read' not in self.permissions and 'workspace.write' not in self.permissions:
            raise PermissionDenied("plugin does not have workspace read permission")

    def _require_write(self):
        if 'workspace.write' not in self.permissions:
            raise PermissionDenied("plugin does not have workspace write permission")

    def _is_sensitive(self, relative_path):
        parts = [part.lower() for part in relative_path.replace('\\', '/').split('/')]
        basename = parts[-1]
        return (
            any(part in _SENSITIVE_PARTS for part in parts)
            or basename in _SENSITIVE_NAMES
            or basename.endswith(_SENSITIVE_SUFFIXES)
        )


class RuntimeContext(object):
    def __init__(
        self,
        plugin_id,
        plugin_version,
        display_name,
        env_version,
        language,
        workspace,
        config_dir,
        data_dir,
        cache_dir,
        permissions,
        logger,
    ):
        self.plugin_id = plugin_id
        self.plugin_version = plugin_version
        self.display_name = display_name
        self.env_version = env_version
        self.language = language
        self.workspace = workspace
        self.config_dir = config_dir
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.permissions = frozenset(permissions)
        self.logger = logger


def create_runtime_context(paths, plugin_id, plugin_version, permissions, workspace_root=None):
    config_dir = os.path.join(paths.config, plugin_id)
    data_dir = os.path.join(paths.data, plugin_id)
    cache_dir = os.path.join(paths.cache, plugin_id)
    for path in (config_dir, data_dir, cache_dir):
        os.makedirs(path, exist_ok=True)
    logger = logging.getLogger('env.plugin.%s' % plugin_id)
    return RuntimeContext(
        plugin_id=plugin_id,
        plugin_version=plugin_version,
        display_name=_display_name(paths),
        env_version=current_env_version(),
        language=_language(),
        workspace=Workspace(workspace_root or os.getcwd(), permissions),
        config_dir=config_dir,
        data_dir=data_dir,
        cache_dir=cache_dir,
        permissions=permissions,
        logger=logger,
    )

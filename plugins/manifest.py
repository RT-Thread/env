"""Strict `.epack` v1 manifest model."""

import json
import os
import re
from pathlib import PurePosixPath

from .errors import ManifestError


SCHEMA_VERSION = 1
PLUGIN_ID_RE = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$')
VERSION_RE = re.compile(r'^[0-9]+(?:\.[0-9]+){2}(?:[-+][A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*)?$')
COMMAND_RE = re.compile(r'^[a-z][a-z0-9-]{0,62}$')
ENTRY_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$')
ABI_RE = re.compile(r'^(?:py3|cp[0-9]{2,3})$')
ICON_RE = re.compile(r'^[a-z][a-z0-9-]{0,62}$')

ALLOWED_PERMISSIONS = frozenset(
    [
        'workspace.read',
        'workspace.write',
        'process.execute',
        'network.access',
        'credentials.use',
        'device.serial',
    ]
)
ALLOWED_PLATFORMS = frozenset(['any', 'linux', 'windows', 'darwin'])
ALLOWED_ARCHITECTURES = frozenset(['any', 'x86_64', 'x86', 'aarch64', 'arm', 'riscv64'])
ALLOWED_IMPLEMENTATIONS = frozenset(['cpython'])
ALLOWED_ARTIFACT_FORMATS = frozenset(['source-wheel', 'pyc-wheel'])
ALLOWED_ARTIFACT_ROLES = frozenset(['plugin', 'dependency'])


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError("duplicate JSON key: %s" % key)
        result[key] = value
    return result


def load_json_bytes(content, label):
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ManifestError("%s must be UTF-8: %s" % (label, exc))
    try:
        return json.loads(text, object_pairs_hook=_unique_object)
    except ManifestError:
        raise
    except (TypeError, ValueError) as exc:
        raise ManifestError("invalid JSON in %s: %s" % (label, exc))


def _object(value, path):
    if not isinstance(value, dict):
        raise ManifestError("%s must be an object" % path)
    return value


def _list(value, path, allow_empty=False):
    if not isinstance(value, list) or (not allow_empty and not value):
        suffix = '' if allow_empty else ' and cannot be empty'
        raise ManifestError("%s must be an array%s" % (path, suffix))
    return value


def _string(value, path, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        suffix = '' if allow_empty else ' non-empty'
        raise ManifestError("%s must be a%s string" % (path, suffix))
    return value


def _boolean(value, path):
    if not isinstance(value, bool):
        raise ManifestError("%s must be a boolean" % path)
    return value


def _keys(value, required, optional, path):
    missing = sorted(set(required) - set(value))
    unknown = sorted(set(value) - set(required) - set(optional))
    if missing:
        raise ManifestError("%s is missing fields: %s" % (path, ', '.join(missing)))
    if unknown:
        raise ManifestError("%s has unknown fields: %s" % (path, ', '.join(unknown)))


def _enum_list(value, allowed, path):
    items = _list(value, path)
    seen = set()
    for index, item in enumerate(items):
        item_path = "%s[%d]" % (path, index)
        _string(item, item_path)
        if item not in allowed:
            raise ManifestError("%s has unsupported value: %s" % (item_path, item))
        if item in seen:
            raise ManifestError("%s contains duplicate value: %s" % (path, item))
        seen.add(item)
    if 'any' in seen and len(seen) != 1:
        raise ManifestError("%s cannot combine 'any' with other values" % path)
    return tuple(items)


class Manifest(object):
    """Validated immutable-by-convention manifest wrapper."""

    def __init__(self, data):
        self.data = data

    @property
    def plugin_id(self):
        return self.data['id']

    @property
    def name(self):
        return self.data['name']

    @property
    def version(self):
        return self.data['version']

    @property
    def compatibility(self):
        return self.data['compatibility']

    @property
    def commands(self):
        return tuple(self.data['commands'])

    @property
    def permissions(self):
        return tuple(self.data['permissions'])

    @property
    def webui(self):
        return self.data.get('webui')

    @property
    def artifacts(self):
        return tuple(self.data['backend']['artifacts'])

    @property
    def health_check(self):
        return self.data.get('health_check')

    def to_dict(self):
        return json.loads(json.dumps(self.data, sort_keys=True))

    def command(self, name):
        for command in self.commands:
            if command['name'] == name:
                return command
        return None


def validate_manifest(data):
    data = _object(data, 'manifest')
    required = [
        'schema_version',
        'id',
        'name',
        'version',
        'description',
        'author',
        'license',
        'compatibility',
        'permissions',
        'commands',
        'backend',
    ]
    _keys(data, required, ['health_check', 'webui'], 'manifest')

    if data['schema_version'] != SCHEMA_VERSION:
        raise ManifestError("unsupported manifest schema_version: %r" % data['schema_version'])
    plugin_id = _string(data['id'], 'manifest.id')
    if not PLUGIN_ID_RE.match(plugin_id):
        raise ManifestError("manifest.id must be a lowercase reverse-domain identifier")
    _string(data['name'], 'manifest.name')
    version = _string(data['version'], 'manifest.version')
    if not VERSION_RE.match(version):
        raise ManifestError("manifest.version must use three-part semantic version syntax")
    _string(data['description'], 'manifest.description')

    author = _object(data['author'], 'manifest.author')
    _keys(author, ['name'], ['url'], 'manifest.author')
    _string(author['name'], 'manifest.author.name')
    if 'url' in author:
        _string(author['url'], 'manifest.author.url')

    license_data = _object(data['license'], 'manifest.license')
    _keys(license_data, ['spdx', 'file'], [], 'manifest.license')
    _string(license_data['spdx'], 'manifest.license.spdx')
    license_path = _string(license_data['file'], 'manifest.license.file')
    if not license_path.startswith('licenses/'):
        raise ManifestError("manifest.license.file must be below licenses/")

    compatibility = _object(data['compatibility'], 'manifest.compatibility')
    _keys(
        compatibility,
        ['env', 'python', 'implementations', 'abis', 'platforms', 'architectures'],
        [],
        'manifest.compatibility',
    )
    _string(compatibility['env'], 'manifest.compatibility.env')
    _string(compatibility['python'], 'manifest.compatibility.python')
    _enum_list(compatibility['implementations'], ALLOWED_IMPLEMENTATIONS, 'manifest.compatibility.implementations')
    abis = _list(compatibility['abis'], 'manifest.compatibility.abis')
    if len(set(abis)) != len(abis) or any(not isinstance(abi, str) or not ABI_RE.match(abi) for abi in abis):
        raise ManifestError("manifest.compatibility.abis contains invalid or duplicate tags")
    _enum_list(compatibility['platforms'], ALLOWED_PLATFORMS, 'manifest.compatibility.platforms')
    _enum_list(compatibility['architectures'], ALLOWED_ARCHITECTURES, 'manifest.compatibility.architectures')

    permissions = _list(data['permissions'], 'manifest.permissions', allow_empty=True)
    permission_names = set()
    for index, permission in enumerate(permissions):
        path = "manifest.permissions[%d]" % index
        permission = _object(permission, path)
        _keys(permission, ['name', 'reason', 'required'], [], path)
        name = _string(permission['name'], path + '.name')
        if name not in ALLOWED_PERMISSIONS:
            raise ManifestError("%s.name is unsupported: %s" % (path, name))
        if name in permission_names:
            raise ManifestError("manifest.permissions contains duplicate permission: %s" % name)
        permission_names.add(name)
        _string(permission['reason'], path + '.reason')
        _boolean(permission['required'], path + '.required')
    if 'workspace.read' in permission_names and 'workspace.write' in permission_names:
        raise ManifestError("workspace.write already includes read access; do not declare both")

    commands = _list(data['commands'], 'manifest.commands', allow_empty=True)
    command_names = set()
    for index, command in enumerate(commands):
        path = "manifest.commands[%d]" % index
        command = _object(command, path)
        _keys(command, ['name', 'entry', 'description'], [], path)
        name = _string(command['name'], path + '.name')
        if not COMMAND_RE.match(name):
            raise ManifestError("%s.name is not a valid command name" % path)
        if name in command_names:
            raise ManifestError("manifest.commands contains duplicate command: %s" % name)
        command_names.add(name)
        entry = _string(command['entry'], path + '.entry')
        if not ENTRY_RE.match(entry):
            raise ManifestError("%s.entry must use module.path:callable syntax" % path)
        _string(command['description'], path + '.description')

    backend = _object(data['backend'], 'manifest.backend')
    _keys(backend, ['artifacts'], [], 'manifest.backend')
    artifacts = _list(backend['artifacts'], 'manifest.backend.artifacts', allow_empty=True)
    artifact_paths = set()
    plugin_artifacts = 0
    uses_pyc = False
    for index, artifact in enumerate(artifacts):
        path = "manifest.backend.artifacts[%d]" % index
        artifact = _object(artifact, path)
        _keys(artifact, ['path', 'format', 'role'], [], path)
        artifact_path = _string(artifact['path'], path + '.path')
        if not artifact_path.startswith('backend/') or not artifact_path.endswith('.whl'):
            raise ManifestError("%s.path must name a wheel below backend/" % path)
        if artifact_path in artifact_paths:
            raise ManifestError("manifest.backend.artifacts contains duplicate path: %s" % artifact_path)
        artifact_paths.add(artifact_path)
        artifact_format = _string(artifact['format'], path + '.format')
        if artifact_format not in ALLOWED_ARTIFACT_FORMATS:
            raise ManifestError("%s.format is unsupported: %s" % (path, artifact_format))
        role = _string(artifact['role'], path + '.role')
        if role not in ALLOWED_ARTIFACT_ROLES:
            raise ManifestError("%s.role is unsupported: %s" % (path, role))
        if role == 'plugin':
            plugin_artifacts += 1
            uses_pyc = artifact_format == 'pyc-wheel'
    if plugin_artifacts > 1:
        raise ManifestError("manifest.backend.artifacts can contain at most one plugin artifact")
    requires_backend = bool(commands or data.get('health_check'))
    if requires_backend and plugin_artifacts != 1:
        raise ManifestError("commands and health_check require exactly one plugin artifact")
    if artifacts and plugin_artifacts != 1:
        raise ManifestError("dependency artifacts require exactly one plugin artifact")
    if uses_pyc:
        if 'cpython' not in compatibility['implementations']:
            raise ManifestError("pyc-wheel requires the cpython implementation")
        if any(not abi.startswith('cp') for abi in compatibility['abis']):
            raise ManifestError("pyc-wheel requires only exact CPython ABI tags")
        plugin_artifact = next(artifact for artifact in artifacts if artifact['role'] == 'plugin')
        wheel_name = os.path.basename(plugin_artifact['path'])
        if not any('-%s-' % abi in wheel_name for abi in compatibility['abis']):
            raise ManifestError("pyc-wheel filename must contain one of its declared ABI tags")
    elif plugin_artifacts:
        plugin_artifact = next(artifact for artifact in artifacts if artifact['role'] == 'plugin')
        if plugin_artifact['format'] == 'source-wheel' and '-py3-' not in os.path.basename(plugin_artifact['path']):
            raise ManifestError("source-wheel filename must use the py3 tag")

    if 'health_check' in data:
        health_check = _string(data['health_check'], 'manifest.health_check')
        if not ENTRY_RE.match(health_check):
            raise ManifestError("manifest.health_check must use module.path:callable syntax")

    if 'webui' in data:
        webui = _object(data['webui'], 'manifest.webui')
        _keys(webui, ['entry', 'icon', 'frontend_sdk'], [], 'manifest.webui')
        entry = _string(webui['entry'], 'manifest.webui.entry')
        if '\\' in entry or ':' in entry:
            raise ManifestError("manifest.webui.entry must use a safe POSIX path below frontend/")
        entry_path = PurePosixPath(entry)
        if (
            entry_path.is_absolute()
            or any(part in ('', '.', '..') for part in entry_path.parts)
            or not entry.startswith('frontend/')
            or not entry.lower().endswith('.html')
        ):
            raise ManifestError("manifest.webui.entry must name an HTML file below frontend/")
        icon = _string(webui['icon'], 'manifest.webui.icon')
        if not ICON_RE.match(icon):
            raise ManifestError("manifest.webui.icon must be a lowercase icon identifier")
        _string(webui['frontend_sdk'], 'manifest.webui.frontend_sdk')

    if not commands and 'webui' not in data and 'health_check' not in data:
        raise ManifestError("manifest must declare a command, WebUI page or health_check")

    return Manifest(data)


def parse_manifest(content):
    return validate_manifest(load_json_bytes(content, 'manifest.json'))

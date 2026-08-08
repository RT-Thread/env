"""Safe inspection and extraction of `.epack` v1 archives."""

import hashlib
import importlib.util
import json
import os
from pathlib import PurePosixPath
import stat
import unicodedata
import zipfile

from .errors import IntegrityError, PackageError
from .manifest import load_json_bytes, parse_manifest


class PackageLimits(object):
    def __init__(self, max_files=2048, max_file_size=64 * 1024 * 1024, max_total_size=256 * 1024 * 1024):
        self.max_files = max_files
        self.max_file_size = max_file_size
        self.max_total_size = max_total_size


def _safe_member_name(name, label):
    if not name or '\\' in name or '\x00' in name:
        raise PackageError("unsafe %s member path: %r" % (label, name))
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ('', '.', '..') for part in path.parts):
        raise PackageError("unsafe %s member path: %s" % (label, name))
    reserved = set(['con', 'prn', 'aux', 'nul'])
    reserved.update('com%d' % index for index in range(1, 10))
    reserved.update('lpt%d' % index for index in range(1, 10))
    for part in path.parts:
        stem = part.split('.', 1)[0].casefold()
        if ':' in part or part.endswith((' ', '.')) or stem in reserved:
            raise PackageError("unsafe %s member path: %s" % (label, name))
    return path


def _validate_members(archive, label, limits):
    seen = set()
    files = []
    total_size = 0
    for info in archive.infolist():
        path = _safe_member_name(info.filename, label)
        normalized = str(path)
        comparison_key = unicodedata.normalize('NFC', normalized).casefold()
        if comparison_key in seen:
            raise PackageError("duplicate %s member: %s" % (label, normalized))
        seen.add(comparison_key)
        unix_mode = (info.external_attr >> 16) & 0xFFFF
        if unix_mode and stat.S_ISLNK(unix_mode):
            raise PackageError("symbolic links are not allowed in %s: %s" % (label, normalized))
        if info.flag_bits & 0x1:
            raise PackageError("encrypted members are not allowed in %s: %s" % (label, normalized))
        if info.is_dir():
            continue
        if info.file_size > limits.max_file_size:
            raise PackageError("%s member exceeds size limit: %s" % (label, normalized))
        total_size += info.file_size
        if total_size > limits.max_total_size:
            raise PackageError("%s exceeds total uncompressed size limit" % label)
        files.append(info)
    if len(files) > limits.max_files:
        raise PackageError("%s contains too many files" % label)
    return files


def _load_integrity(content):
    data = load_json_bytes(content, 'integrity.json')
    if not isinstance(data, dict):
        raise IntegrityError("integrity.json must be an object")
    required = set(['schema_version', 'algorithm', 'files'])
    if set(data) != required:
        raise IntegrityError("integrity.json must contain only schema_version, algorithm and files")
    if data['schema_version'] != 1:
        raise IntegrityError("unsupported integrity schema_version: %r" % data['schema_version'])
    if data['algorithm'] != 'sha256':
        raise IntegrityError("unsupported integrity algorithm: %r" % data['algorithm'])
    if not isinstance(data['files'], dict) or not data['files']:
        raise IntegrityError("integrity.json files must be a non-empty object")
    for name, digest in data['files'].items():
        _safe_member_name(name, 'integrity')
        if name == 'integrity.json':
            raise IntegrityError("integrity.json cannot include itself")
        if not isinstance(digest, str) or len(digest) != 64:
            raise IntegrityError("invalid SHA-256 digest for %s" % name)
        try:
            int(digest, 16)
        except ValueError:
            raise IntegrityError("invalid SHA-256 digest for %s" % name)
    return data


def _read_checked(archive, info):
    try:
        return archive.read(info)
    except (RuntimeError, zipfile.BadZipFile, OSError) as exc:
        raise PackageError("cannot read archive member %s: %s" % (info.filename, exc))


class EpackArchive(object):
    def __init__(self, path, limits=None):
        self.path = os.path.abspath(path)
        self.limits = limits or PackageLimits()
        self.manifest = None
        self.integrity = None
        self.signing_status = 'unsigned'
        self._members = None

    def inspect(self):
        if not os.path.isfile(self.path):
            raise PackageError("plugin package does not exist: %s" % self.path)
        if not self.path.lower().endswith('.epack'):
            raise PackageError("plugin package must use the .epack extension")
        try:
            with zipfile.ZipFile(self.path, 'r') as archive:
                infos = _validate_members(archive, '.epack', self.limits)
                by_name = dict((info.filename, info) for info in infos)
                if 'manifest.json' not in by_name or 'integrity.json' not in by_name:
                    raise PackageError(".epack requires manifest.json and integrity.json")
                manifest_content = _read_checked(archive, by_name['manifest.json'])
                integrity_content = _read_checked(archive, by_name['integrity.json'])
                manifest = parse_manifest(manifest_content)
                integrity = _load_integrity(integrity_content)

                actual_names = set(by_name) - set(['integrity.json'])
                expected_names = set(integrity['files'])
                if actual_names != expected_names:
                    missing = sorted(expected_names - actual_names)
                    unexpected = sorted(actual_names - expected_names)
                    details = []
                    if missing:
                        details.append("missing: %s" % ', '.join(missing))
                    if unexpected:
                        details.append("not listed: %s" % ', '.join(unexpected))
                    raise IntegrityError("package inventory mismatch (%s)" % '; '.join(details))

                for name in sorted(expected_names):
                    digest = hashlib.sha256(_read_checked(archive, by_name[name])).hexdigest()
                    if digest.lower() != integrity['files'][name].lower():
                        raise IntegrityError("SHA-256 mismatch for %s" % name)

                required_paths = set([manifest.data['license']['file']])
                required_paths.update(artifact['path'] for artifact in manifest.artifacts)
                if manifest.webui:
                    required_paths.add(manifest.webui['entry'])
                missing_required = sorted(required_paths - actual_names)
                if missing_required:
                    raise PackageError("manifest references missing files: %s" % ', '.join(missing_required))
                frontend_files = [name for name in actual_names if name.startswith('frontend/')]
                if frontend_files and not manifest.webui:
                    raise PackageError("frontend resources require an explicit manifest.webui entry")

                self.manifest = manifest
                self.integrity = integrity
                self._members = tuple(sorted(actual_names))
                if any(name.startswith('security/') or name.startswith('signatures/') for name in actual_names):
                    raise PackageError(".epack v1 does not support verifiable signatures; remove signature material")
                return self
        except zipfile.BadZipFile as exc:
            raise PackageError("invalid .epack ZIP container: %s" % exc)

    def summary(self):
        if self.manifest is None:
            self.inspect()
        return {
            'path': self.path,
            'id': self.manifest.plugin_id,
            'name': self.manifest.name,
            'version': self.manifest.version,
            'description': self.manifest.data['description'],
            'author': self.manifest.data['author'],
            'license': self.manifest.data['license'],
            'compatibility': self.manifest.compatibility,
            'permissions': list(self.manifest.permissions),
            'commands': list(self.manifest.commands),
            'backend': self.manifest.data['backend'],
            'webui': self.manifest.webui,
            'files': list(self._members),
            'signing_status': self.signing_status,
            'integrity': 'verified',
        }

    def install_wheels(self, target):
        if self.manifest is None:
            self.inspect()
        os.makedirs(target, exist_ok=True)
        try:
            with zipfile.ZipFile(self.path, 'r') as package_archive:
                installed_members = set()
                for artifact in self.manifest.artifacts:
                    wheel_content = package_archive.read(artifact['path'])
                    self._install_wheel_bytes(wheel_content, artifact, target, installed_members)
        except zipfile.BadZipFile as exc:
            raise PackageError("invalid wheel archive: %s" % exc)

    def install_frontend(self, target):
        if self.manifest is None:
            self.inspect()
        if not self.manifest.webui:
            return
        os.makedirs(target, exist_ok=True)
        try:
            with zipfile.ZipFile(self.path, 'r') as package_archive:
                for name in self._members:
                    if not name.startswith('frontend/'):
                        continue
                    relative = PurePosixPath(name).relative_to('frontend')
                    destination = os.path.abspath(os.path.join(target, *relative.parts))
                    root = os.path.abspath(target)
                    if os.path.commonpath([root, destination]) != root:
                        raise PackageError("frontend member escapes install root: %s" % name)
                    os.makedirs(os.path.dirname(destination), exist_ok=True)
                    with open(destination, 'wb') as output:
                        output.write(package_archive.read(name))
        except zipfile.BadZipFile as exc:
            raise PackageError("invalid frontend archive: %s" % exc)

    def _install_wheel_bytes(self, content, artifact, target, installed_members):
        import io

        try:
            with zipfile.ZipFile(io.BytesIO(content), 'r') as wheel:
                infos = _validate_members(wheel, 'wheel', self.limits)
                py_files = []
                for info in infos:
                    path = _safe_member_name(info.filename, 'wheel')
                    member_key = unicodedata.normalize('NFC', str(path)).casefold()
                    if member_key in installed_members:
                        raise PackageError("backend wheels contain overlapping file: %s" % info.filename)
                    installed_members.add(member_key)
                    if '.data' in path.parts:
                        raise PackageError("wheel .data layouts are not supported in v1: %s" % info.filename)
                    if info.filename.endswith('.py') and '.dist-info/' not in info.filename:
                        py_files.append(info.filename)
                    destination = os.path.abspath(os.path.join(target, *path.parts))
                    root = os.path.abspath(target)
                    if os.path.commonpath([root, destination]) != root:
                        raise PackageError("wheel member escapes install root: %s" % info.filename)
                    os.makedirs(os.path.dirname(destination), exist_ok=True)
                    member_content = _read_checked(wheel, info)
                    if artifact['format'] == 'pyc-wheel' and info.filename.endswith('.pyc'):
                        if member_content[:4] != importlib.util.MAGIC_NUMBER:
                            raise PackageError("pyc-wheel contains incompatible bytecode: %s" % info.filename)
                    with open(destination, 'wb') as output:
                        output.write(member_content)
                if artifact['format'] == 'pyc-wheel' and artifact['role'] == 'plugin' and py_files:
                    raise PackageError("pyc-wheel contains plugin source files: %s" % ', '.join(sorted(py_files)))
        except zipfile.BadZipFile as exc:
            raise PackageError("invalid wheel %s: %s" % (artifact['path'], exc))


def write_integrity(files):
    return {
        'schema_version': 1,
        'algorithm': 'sha256',
        'files': dict((name, hashlib.sha256(content).hexdigest()) for name, content in sorted(files.items())),
    }


def canonical_json(data):
    return (json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True) + '\n').encode('utf-8')

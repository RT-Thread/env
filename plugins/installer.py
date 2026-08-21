"""Transactional plugin lifecycle implementation."""

from datetime import datetime, timezone
import hashlib
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import PurePosixPath

from .compatibility import compare_versions, compatibility_issues, ensure_compatible
from .errors import CommandConflictError, StateError, TransactionError, UsageError
from .launchers import LauncherManager
from .manifest import validate_manifest
from .package import EpackArchive, canonical_json
from .store import FileLock, StateStore


BUILTIN_COMMANDS = frozenset(['env', 'rt-env', 'menuconfig', 'pkgs', 'sdk', 'system', 'plugin'])


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _remove_tree(path):
    if path and os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


class PluginInstaller(object):
    def __init__(self, paths, launcher_manager=None, store=None):
        self.paths = paths
        self.store = store or StateStore(paths)
        self.launchers = launcher_manager or LauncherManager(paths)

    def inspect(self, package_path):
        archive = EpackArchive(package_path).inspect()
        ensure_compatible(archive.manifest)
        return archive

    def install(self, package_path, allow_unsigned=False, upgrade=False):
        archive = self.inspect(package_path)
        if archive.signing_status == 'unsigned' and not allow_unsigned:
            raise UsageError("unsigned local package requires explicit confirmation or --yes")
        self.paths.ensure()
        with self.store.lock():
            state = self.store.load()
            plugin_id = archive.manifest.plugin_id
            current = state['plugins'].get(plugin_id)
            if upgrade and current is None:
                raise StateError("plugin is not installed: %s" % plugin_id)
            if not upgrade and current is not None:
                raise StateError("plugin is already installed; use upgrade: %s" % plugin_id)
            if current is not None:
                active = current['active_version']
                if archive.manifest.version == active:
                    raise StateError("plugin version is already active: %s" % active)
                if compare_versions(archive.manifest.version, active) <= 0:
                    raise StateError("upgrade version %s must be newer than %s" % (archive.manifest.version, active))
            self._check_command_conflicts(state, archive.manifest, plugin_id)
            return self._activate_archive(state, archive, current)

    def _activate_archive(self, state, archive, current):
        manifest = archive.manifest
        plugin_id = manifest.plugin_id
        version = manifest.version
        stage = os.path.join(self.paths.staging, '%s-%s' % (plugin_id, uuid.uuid4().hex))
        target = self.paths.version_dir(plugin_id, version)
        if os.path.exists(target):
            raise StateError("version directory already exists: %s" % target)
        os.makedirs(stage)
        moved = False
        old_commands = [command['name'] for command in self._active_commands(current)]
        new_commands = [command['name'] for command in manifest.commands]
        activation_enabled = current is None or current['enabled']
        snapshot = None
        try:
            site_packages = os.path.join(stage, 'site-packages')
            archive.install_wheels(site_packages)
            archive.install_frontend(os.path.join(stage, 'frontend'))
            with open(os.path.join(stage, 'manifest.json'), 'wb') as output:
                output.write(canonical_json(manifest.to_dict()))
            with open(os.path.join(stage, 'integrity.json'), 'wb') as output:
                output.write(canonical_json(archive.integrity))
            self._run_health_check(stage, site_packages)

            os.makedirs(os.path.dirname(target), exist_ok=True)
            os.replace(stage, target)
            moved = True
            snapshot = self.launchers.snapshot(set(old_commands + new_commands))
            if activation_enabled:
                for command in set(old_commands) - set(new_commands):
                    self.launchers.remove(command)
                for command in new_commands:
                    self.launchers.write(command)

            next_state = self.store.copy(state)
            installed_at = _now()
            if current is None:
                record = {
                    'id': plugin_id,
                    'name': manifest.name,
                    'enabled': True,
                    'active_version': version,
                    'granted_permissions': [permission['name'] for permission in manifest.permissions],
                    'installed_at': installed_at,
                    'updated_at': installed_at,
                    'versions': {},
                }
            else:
                record = next_state['plugins'][plugin_id]
                record['name'] = manifest.name
                record['enabled'] = bool(activation_enabled)
                record['active_version'] = version
                record['granted_permissions'] = [permission['name'] for permission in manifest.permissions]
                record['updated_at'] = installed_at
            record['versions'][version] = {
                'manifest': manifest.to_dict(),
                'install_dir': self.paths.relative_to_root(target),
                'package_path': archive.path,
                'package_sha256': _sha256_file(archive.path),
                'signing_status': archive.signing_status,
                'installed_at': installed_at,
            }
            next_state['plugins'][plugin_id] = record
            for command, owner in list(next_state['commands'].items()):
                if owner == plugin_id:
                    del next_state['commands'][command]
            for command in new_commands:
                next_state['commands'][command] = plugin_id
            self.store.save(next_state)
            return self._public_record(next_state['plugins'][plugin_id])
        except Exception:
            if snapshot is not None:
                self.launchers.restore(snapshot)
            if moved:
                _remove_tree(target)
            else:
                _remove_tree(stage)
            raise

    def uninstall(self, plugin_id, purge_data=False):
        self.paths.ensure()
        with FileLock(self.paths.runtime_lock(plugin_id)):
            with self.store.lock():
                state = self.store.load()
                record = state['plugins'].get(plugin_id)
                if record is None:
                    raise StateError("plugin is not installed: %s" % plugin_id)
                commands = [command['name'] for command in self._active_commands(record)]
                snapshot = self.launchers.snapshot(commands)
                trash_root = os.path.join(self.paths.staging, 'uninstall-%s-%s' % (plugin_id, uuid.uuid4().hex))
                os.makedirs(trash_root)
                moved = []
                try:
                    plugin_root = os.path.join(self.paths.installed, plugin_id)
                    if os.path.exists(plugin_root):
                        destination = os.path.join(trash_root, 'installed')
                        os.replace(plugin_root, destination)
                        moved.append((destination, plugin_root))
                    if purge_data:
                        roots = [('config', self.paths.config), ('data', self.paths.data), ('cache', self.paths.cache)]
                        for label, root in roots:
                            source = os.path.join(root, plugin_id)
                            if os.path.exists(source):
                                destination = os.path.join(trash_root, label)
                                os.replace(source, destination)
                                moved.append((destination, source))
                    for command in commands:
                        self.launchers.remove(command)
                    next_state = self.store.copy(state)
                    del next_state['plugins'][plugin_id]
                    for command, owner in list(next_state['commands'].items()):
                        if owner == plugin_id:
                            del next_state['commands'][command]
                    self.store.save(next_state)
                except Exception:
                    self.launchers.restore(snapshot)
                    for source, destination in reversed(moved):
                        if os.path.exists(source):
                            os.makedirs(os.path.dirname(destination), exist_ok=True)
                            os.replace(source, destination)
                    _remove_tree(trash_root)
                    raise
                _remove_tree(trash_root)
                return {'id': plugin_id, 'uninstalled': True, 'data_removed': bool(purge_data)}

    def set_enabled(self, plugin_id, enabled):
        self.paths.ensure()
        with self.store.lock():
            state = self.store.load()
            record = state['plugins'].get(plugin_id)
            if record is None:
                raise StateError("plugin is not installed: %s" % plugin_id)
            if record['enabled'] == enabled:
                return self._public_record(record)
            manifest = validate_manifest(self._active_version(record)['manifest'])
            if enabled:
                ensure_compatible(manifest)
                self._check_command_conflicts(state, manifest, plugin_id)
            commands = [command['name'] for command in manifest.commands]
            snapshot = self.launchers.snapshot(commands)
            try:
                if enabled:
                    for command in commands:
                        self.launchers.write(command)
                else:
                    for command in commands:
                        self.launchers.remove(command)
                next_state = self.store.copy(state)
                next_state['plugins'][plugin_id]['enabled'] = bool(enabled)
                next_state['plugins'][plugin_id]['updated_at'] = _now()
                self.store.save(next_state)
                return self._public_record(next_state['plugins'][plugin_id])
            except Exception:
                self.launchers.restore(snapshot)
                raise

    def set_permissions(self, plugin_id, permissions):
        if not isinstance(permissions, (list, tuple)):
            raise UsageError("permissions must be an array")
        if len(set(permissions)) != len(permissions) or any(not isinstance(item, str) for item in permissions):
            raise UsageError("permissions must contain unique permission names")
        self.paths.ensure()
        with self.store.lock():
            state = self.store.load()
            record = state['plugins'].get(plugin_id)
            if record is None:
                raise StateError("plugin is not installed: %s" % plugin_id)
            manifest = validate_manifest(self._active_version(record)['manifest'])
            declared = set(permission['name'] for permission in manifest.permissions)
            unknown = sorted(set(permissions) - declared)
            if unknown:
                raise UsageError("permissions are not declared by the plugin: %s" % ', '.join(unknown))
            next_state = self.store.copy(state)
            next_state['plugins'][plugin_id]['granted_permissions'] = sorted(permissions)
            next_state['plugins'][plugin_id]['updated_at'] = _now()
            self.store.save(next_state)
            return self._public_record(next_state['plugins'][plugin_id], details=True)

    def list_plugins(self):
        with self.store.lock():
            state = self.store.load()
        return [self._public_record(state['plugins'][plugin_id]) for plugin_id in sorted(state['plugins'])]

    def info(self, plugin_id):
        with self.store.lock():
            state = self.store.load()
        record = state['plugins'].get(plugin_id)
        if record is None:
            raise StateError("plugin is not installed: %s" % plugin_id)
        return self._public_record(record, details=True)

    def doctor(self, plugin_id=None):
        with self.store.lock():
            state = self.store.load()
        if plugin_id is not None and plugin_id not in state['plugins']:
            raise StateError("plugin is not installed: %s" % plugin_id)
        plugin_ids = [plugin_id] if plugin_id else sorted(state['plugins'])
        results = []
        for current_id in plugin_ids:
            record = state['plugins'][current_id]
            issues = []
            try:
                version_record = self._active_version(record)
                manifest = validate_manifest(version_record['manifest'])
                issues.extend(compatibility_issues(manifest))
                install_dir = self.paths.from_root(version_record['install_dir'])
                if manifest.artifacts and not os.path.isdir(os.path.join(install_dir, 'site-packages')):
                    issues.append('active version files are missing')
                if manifest.webui:
                    frontend_entry = self._frontend_entry(install_dir, manifest)
                    if not os.path.isfile(frontend_entry):
                        issues.append('WebUI entry is missing')
                required = set(permission['name'] for permission in manifest.permissions if permission['required'])
                missing_permissions = sorted(required - set(record['granted_permissions']))
                if missing_permissions:
                    issues.append('required permissions are not granted: %s' % ', '.join(missing_permissions))
                for command in manifest.commands:
                    name = command['name']
                    if state['commands'].get(name) != current_id:
                        issues.append('command ownership is inconsistent: %s' % name)
                    if record['enabled'] and not self.launchers.is_managed(name):
                        issues.append('launcher is missing or unmanaged: %s' % name)
                    if not record['enabled'] and self.launchers.exists(name):
                        issues.append('disabled plugin still has launcher: %s' % name)
            except Exception as exc:
                issues.append(str(exc))
            results.append({'id': current_id, 'status': 'ok' if not issues else 'error', 'issues': issues})
        return {'status': 'ok' if all(item['status'] == 'ok' for item in results) else 'error', 'plugins': results}

    def resolve_webui_asset(self, plugin_id, asset_path=None):
        with self.store.lock():
            state = self.store.load()
        record = state['plugins'].get(plugin_id)
        if record is None:
            raise StateError("plugin is not installed: %s" % plugin_id)
        if not record['enabled']:
            raise StateError("plugin is disabled: %s" % plugin_id)
        active = self._active_version(record)
        manifest = validate_manifest(active['manifest'])
        ensure_compatible(manifest)
        if not manifest.webui:
            raise StateError("plugin does not provide a WebUI page: %s" % plugin_id)
        required = set(permission['name'] for permission in manifest.permissions if permission['required'])
        missing = sorted(required - set(record['granted_permissions']))
        if missing:
            raise StateError("required permissions are not granted: %s" % ', '.join(missing))
        entry_relative = manifest.webui['entry'][len('frontend/'):]
        relative = asset_path or entry_relative
        if not isinstance(relative, str) or '\\' in relative or ':' in relative:
            raise UsageError("invalid WebUI asset path")
        path = PurePosixPath(relative)
        if path.is_absolute() or any(part in ('', '.', '..') for part in path.parts):
            raise UsageError("invalid WebUI asset path")
        install_dir = self.paths.from_root(active['install_dir'])
        frontend_root = os.path.realpath(os.path.join(install_dir, 'frontend'))
        target = os.path.realpath(os.path.join(frontend_root, *path.parts))
        if os.path.commonpath([frontend_root, target]) != frontend_root or not os.path.isfile(target):
            raise StateError("WebUI asset is missing: %s" % relative)
        return target

    def _check_command_conflicts(self, state, manifest, plugin_id):
        for command in manifest.commands:
            name = command['name']
            if name in BUILTIN_COMMANDS:
                raise CommandConflictError("command is reserved by Env: %s" % name)
            owner = state['commands'].get(name)
            if owner is not None and owner != plugin_id:
                raise CommandConflictError("command %s is owned by plugin %s" % (name, owner))
            self.launchers.ensure_available(name, owned=(owner == plugin_id))

    def _run_health_check(self, stage, site_packages):
        manifest_path = os.path.join(stage, 'manifest.json')
        module = __package__ + '.health_runner'
        package_dir = os.path.dirname(os.path.abspath(__file__))
        if module.startswith('env.'):
            module_root = os.path.dirname(os.path.dirname(package_dir))
        else:
            module_root = os.path.dirname(package_dir)
        environment = {}
        for name in ('PATH', 'SYSTEMROOT', 'COMSPEC', 'PATHEXT', 'WINDIR', 'LANG', 'LC_ALL', 'TMP', 'TEMP', 'TMPDIR'):
            if name in os.environ:
                environment[name] = os.environ[name]
        environment['PYTHONPATH'] = os.pathsep.join([site_packages, module_root])
        process = subprocess.run(
            [sys.executable, '-m', module, manifest_path, site_packages],
            cwd=stage,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        if process.returncode != 0:
            detail = (process.stderr or process.stdout).strip()
            raise TransactionError("plugin health check failed: %s" % (detail or 'unknown error'))

    def _active_version(self, record):
        version = record['active_version']
        try:
            return record['versions'][version]
        except KeyError:
            raise StateError("active plugin version is missing from state: %s" % version)

    def _active_commands(self, record):
        if record is None:
            return ()
        return validate_manifest(self._active_version(record)['manifest']).commands

    def _public_record(self, record, details=False):
        result = {
            'id': record['id'],
            'name': record['name'],
            'version': record['active_version'],
            'enabled': bool(record['enabled']),
            'updated_at': record['updated_at'],
        }
        active = self._active_version(record)
        manifest = active['manifest']
        result['commands'] = [command['name'] for command in manifest['commands']]
        result['webui'] = manifest.get('webui')
        result['service'] = manifest.get('service')
        if details:
            result.update(
                {
                    'description': manifest['description'],
                    'author': manifest['author'],
                    'license': manifest['license'],
                    'compatibility': manifest['compatibility'],
                    'compatibility_issues': compatibility_issues(validate_manifest(manifest)),
                    'permissions': manifest['permissions'],
                    'granted_permissions': list(record['granted_permissions']),
                    'source': active['package_path'],
                    'package_sha256': active['package_sha256'],
                    'signing_status': active['signing_status'],
                    'installed_versions': sorted(record['versions']),
                    'installed_at': record['installed_at'],
                }
            )
        return result

    def _frontend_entry(self, install_dir, manifest):
        relative = manifest.webui['entry'][len('frontend/'):]
        return os.path.join(install_dir, 'frontend', *PurePosixPath(relative).parts)

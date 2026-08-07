"""Deterministic wheel and `.epack` v1 construction."""

import base64
import hashlib
import io
import os
import py_compile
import shutil
import tempfile
import zipfile

from ..compatibility import python_abi
from ..errors import PackageError
from ..manifest import validate_manifest
from ..package import EpackArchive, canonical_json, write_integrity
from . import EPACK_VERSION
from .project import distribution_name, validate_project


_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def _zip_bytes(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, _ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, content)
    return output.getvalue()


def _record_hash(content):
    digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b'=').decode('ascii')
    return 'sha256=' + digest


def _source_files(source_root, backend_format):
    result = {}
    temporary = tempfile.mkdtemp(prefix='epack-pyc-')
    try:
        for root, directories, files in os.walk(source_root):
            directories[:] = sorted(item for item in directories if item != '__pycache__')
            for filename in sorted(files):
                if filename.endswith(('.pyc', '.pyo', '.map')):
                    continue
                source_path = os.path.join(root, filename)
                if os.path.islink(source_path):
                    raise PackageError("symbolic links are not allowed in plugin source: %s" % source_path)
                relative = os.path.relpath(source_path, source_root).replace(os.sep, '/')
                if backend_format == 'pyc-wheel' and filename.endswith('.py'):
                    pyc_relative = relative[:-3] + '.pyc'
                    pyc_path = os.path.join(temporary, *pyc_relative.split('/'))
                    os.makedirs(os.path.dirname(pyc_path), exist_ok=True)
                    kwargs = {'dfile': relative, 'doraise': True, 'optimize': 0}
                    invalidation_mode = getattr(py_compile, 'PycInvalidationMode', None)
                    if invalidation_mode is not None:
                        kwargs['invalidation_mode'] = invalidation_mode.CHECKED_HASH
                    try:
                        py_compile.compile(source_path, cfile=pyc_path, **kwargs)
                    except py_compile.PyCompileError as exc:
                        raise PackageError("cannot compile %s: %s" % (relative, exc))
                    with open(pyc_path, 'rb') as compiled:
                        result[pyc_relative] = compiled.read()
                else:
                    with open(source_path, 'rb') as source:
                        result[relative] = source.read()
        return result
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def build_wheel(directory, manifest, backend_format):
    distribution = distribution_name(manifest.plugin_id)
    tag = 'py3-none-any' if backend_format == 'source-wheel' else '%s-none-any' % python_abi()
    wheel_name = '%s-%s-%s.whl' % (distribution, manifest.version, tag)
    files = _source_files(os.path.join(directory, 'src'), backend_format)
    dist_info = '%s-%s.dist-info' % (distribution, manifest.version)
    files[dist_info + '/METADATA'] = (
        'Metadata-Version: 2.1\n'
        'Name: %s\n'
        'Version: %s\n'
        'Summary: %s\n'
        'License: %s\n'
        '\n' % (manifest.plugin_id, manifest.version, manifest.data['description'], manifest.data['license']['spdx'])
    ).encode('utf-8')
    files[dist_info + '/WHEEL'] = (
        'Wheel-Version: 1.0\n'
        'Generator: epack %s\n'
        'Root-Is-Purelib: true\n'
        'Tag: %s\n\n' % (EPACK_VERSION, tag)
    ).encode('ascii')
    record_name = dist_info + '/RECORD'
    rows = []
    for name, content in sorted(files.items()):
        rows.append('%s,%s,%d' % (name, _record_hash(content), len(content)))
    rows.append('%s,,' % record_name)
    files[record_name] = ('\n'.join(rows) + '\n').encode('utf-8')
    return wheel_name, _zip_bytes(files)


def build_project(directory, output_directory=None, backend_format=None):
    directory = os.path.abspath(directory)
    manifest = validate_project(directory)
    plugin_artifact = next((artifact for artifact in manifest.artifacts if artifact['role'] == 'plugin'), None)
    if plugin_artifact:
        backend_format = backend_format or plugin_artifact['format']
        if backend_format not in ('source-wheel', 'pyc-wheel'):
            raise PackageError("unsupported backend format: %s" % backend_format)
        wheel_name, wheel_content = build_wheel(directory, manifest, backend_format)
    elif backend_format is not None:
        raise PackageError("backend format cannot be selected for a WebUI-only plugin")
    package_manifest = manifest.to_dict()
    dependency_artifacts = [artifact for artifact in manifest.artifacts if artifact['role'] == 'dependency']
    if plugin_artifact:
        package_manifest['backend']['artifacts'] = [
            {'path': 'backend/' + wheel_name, 'format': backend_format, 'role': 'plugin'}
        ] + list(dependency_artifacts)
        package_manifest['compatibility']['abis'] = ['py3'] if backend_format == 'source-wheel' else [python_abi()]
    package_manifest = validate_manifest(package_manifest)

    with open(os.path.join(directory, 'LICENSE'), 'rb') as license_file:
        license_content = license_file.read()
    files = {
        'manifest.json': canonical_json(package_manifest.to_dict()),
        package_manifest.data['license']['file']: license_content,
        'build/build.json': canonical_json(
            {
                'schema_version': 1,
                'builder': 'epack',
                'builder_version': EPACK_VERSION,
                'backend_format': backend_format or 'none',
                'python_abi': python_abi(),
            }
        ),
    }
    if plugin_artifact:
        files['backend/' + wheel_name] = wheel_content
    for artifact in dependency_artifacts:
        dependency_path = os.path.join(directory, 'wheels', os.path.basename(artifact['path']))
        with open(dependency_path, 'rb') as dependency:
            files[artifact['path']] = dependency.read()
    if package_manifest.webui:
        frontend_root = os.path.join(directory, 'frontend')
        for root, directories, filenames in os.walk(frontend_root):
            directories[:] = sorted(directories)
            for filename in sorted(filenames):
                source_path = os.path.join(root, filename)
                relative = os.path.relpath(source_path, directory).replace(os.sep, '/')
                with open(source_path, 'rb') as source:
                    files[relative] = source.read()
    files['integrity.json'] = canonical_json(write_integrity(files))
    output_directory = os.path.abspath(output_directory or os.path.join(directory, 'dist'))
    os.makedirs(output_directory, exist_ok=True)
    target_tag = 'py3-none-any' if backend_format in (None, 'source-wheel') else '%s-none-any' % python_abi()
    package_name = '%s-%s-%s.epack' % (manifest.plugin_id, manifest.version, target_tag)
    target = os.path.join(output_directory, package_name)
    temporary = target + '.tmp'
    try:
        with open(temporary, 'wb') as output:
            output.write(_zip_bytes(files))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    EpackArchive(target).inspect()
    return target

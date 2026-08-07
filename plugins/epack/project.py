"""Plugin project scaffolding and validation."""

import ast
import os
import re

from ..errors import PackageError, UsageError
from ..manifest import parse_manifest, validate_manifest
from ..package import canonical_json


def module_name(plugin_id):
    return re.sub(r'[^A-Za-z0-9_]', '_', plugin_id)


def distribution_name(plugin_id):
    return re.sub(r'[-_.]+', '_', plugin_id)


def default_manifest(plugin_id, name, version='0.1.0'):
    module = module_name(plugin_id)
    wheel = '%s-%s-py3-none-any.whl' % (distribution_name(plugin_id), version)
    return {
        'schema_version': 1,
        'id': plugin_id,
        'name': name,
        'version': version,
        'description': '%s Env plugin' % name,
        'author': {'name': 'Plugin Author'},
        'license': {'spdx': 'Apache-2.0', 'file': 'licenses/LICENSE'},
        'compatibility': {
            'env': '>=2.0.2,<3.0.0',
            'python': '>=3.6.0,<4.0.0',
            'implementations': ['cpython'],
            'abis': ['py3'],
            'platforms': ['any'],
            'architectures': ['any'],
        },
        'permissions': [],
        'commands': [
            {
                'name': module.replace('_', '-'),
                'entry': '%s.cli:main' % module,
                'description': 'Run %s' % name,
            }
        ],
        'backend': {'artifacts': [{'path': 'backend/' + wheel, 'format': 'source-wheel', 'role': 'plugin'}]},
    }


def init_project(directory, plugin_id, name):
    directory = os.path.abspath(directory)
    if os.path.exists(directory) and os.listdir(directory):
        raise UsageError("target directory is not empty: %s" % directory)
    os.makedirs(directory, exist_ok=True)
    manifest = validate_manifest(default_manifest(plugin_id, name))
    package = module_name(plugin_id)
    source_dir = os.path.join(directory, 'src', package)
    tests_dir = os.path.join(directory, 'tests')
    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(tests_dir, exist_ok=True)
    _write_new(os.path.join(directory, 'manifest.json'), canonical_json(manifest.to_dict()))
    _write_new(
        os.path.join(directory, 'LICENSE'),
        b'Apache License 2.0\n\nReplace this placeholder with the complete license text before release.\n',
    )
    _write_new(os.path.join(source_dir, '__init__.py'), b'__version__ = "0.1.0"\n')
    command_source = (
        'def main(argv, context):\n'
        '    """Run the plugin command."""\n'
        '    print("Hello from %s 0.1.0")\n'
        '    if argv:\n'
        '        print("Arguments: %%s" %% " ".join(argv))\n'
        '    return 0\n' % name.replace('"', '\\"')
    ).encode('utf-8')
    _write_new(os.path.join(source_dir, 'cli.py'), command_source)
    _write_new(
        os.path.join(tests_dir, 'test_plugin.py'),
        (
            'import unittest\n\n'
            'from %s.cli import main\n\n\n'
            'class PluginTest(unittest.TestCase):\n'
            '    def test_command_succeeds(self):\n'
            '        self.assertEqual(main([], object()), 0)\n'
        )
        .replace('%s', package)
        .encode('utf-8'),
    )
    return directory


def _write_new(path, content):
    if os.path.exists(path):
        raise UsageError("refusing to overwrite existing file: %s" % path)
    with open(path, 'wb') as output:
        output.write(content)


def load_project_manifest(directory):
    path = os.path.join(os.path.abspath(directory), 'manifest.json')
    try:
        with open(path, 'rb') as source:
            content = source.read()
    except OSError as exc:
        raise PackageError("cannot read project manifest: %s" % exc)
    return parse_manifest(content)


def validate_project(directory):
    directory = os.path.abspath(directory)
    manifest = load_project_manifest(directory)
    license_path = os.path.join(directory, 'LICENSE')
    if not os.path.isfile(license_path) or os.path.getsize(license_path) == 0:
        raise PackageError("project requires a non-empty LICENSE file")
    source_root = os.path.join(directory, 'src')
    requires_backend = bool(manifest.commands or manifest.health_check or manifest.artifacts)
    if requires_backend and not os.path.isdir(source_root):
        raise PackageError("project requires a src directory")
    for artifact in manifest.artifacts:
        if artifact['role'] == 'dependency':
            dependency = os.path.join(directory, 'wheels', os.path.basename(artifact['path']))
            if not os.path.isfile(dependency):
                raise PackageError("dependency wheel is missing: %s" % dependency)
    for command in manifest.commands:
        _validate_source_entry(source_root, command['entry'])
    if manifest.health_check:
        _validate_source_entry(source_root, manifest.health_check)
    if os.path.isdir(source_root):
        _validate_resource_tree(source_root, 'plugin source')
    frontend_root = os.path.join(directory, 'frontend')
    if manifest.webui:
        entry = os.path.join(directory, *manifest.webui['entry'].split('/'))
        if not os.path.isfile(entry):
            raise PackageError("WebUI entry is missing: %s" % manifest.webui['entry'])
        _validate_resource_tree(frontend_root, 'plugin frontend')
    elif os.path.exists(frontend_root):
        raise PackageError("frontend directory requires manifest.webui")
    return manifest


def _validate_resource_tree(root, label):
    if os.path.islink(root):
        raise PackageError("symbolic links are not allowed in %s: %s" % (label, root))
    for current, directories, files in os.walk(root):
        directories[:] = sorted(item for item in directories if item != '__pycache__')
        for directory in directories:
            path = os.path.join(current, directory)
            if os.path.islink(path):
                raise PackageError("symbolic links are not allowed in %s: %s" % (label, path))
        for filename in files:
            if filename.lower().endswith(('.map', '.pyc', '.pyo')):
                raise PackageError(
                    "generated debug files are not allowed in %s: %s"
                    % (label, os.path.join(current, filename))
                )
            path = os.path.join(current, filename)
            if os.path.islink(path):
                raise PackageError("symbolic links are not allowed in %s: %s" % (label, path))


def _validate_source_entry(source_root, entry):
    module, attribute = entry.split(':', 1)
    relative = module.replace('.', os.sep)
    candidates = [os.path.join(source_root, relative + '.py'), os.path.join(source_root, relative, '__init__.py')]
    source_path = next((path for path in candidates if os.path.isfile(path)), None)
    if source_path is None:
        raise PackageError("entry module is missing from src: %s" % module)
    try:
        with open(source_path, 'r', encoding='utf-8') as source:
            tree = ast.parse(source.read(), filename=source_path)
    except (OSError, SyntaxError, UnicodeError) as exc:
        raise PackageError("cannot parse entry module %s: %s" % (module, exc))
    definitions = set(
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )
    if attribute not in definitions:
        raise PackageError("entry callable is not defined at module scope: %s" % entry)

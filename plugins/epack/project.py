"""Plugin project scaffolding and validation."""

import ast
import html
import os
import re

from ..errors import PackageError, UsageError
from ..manifest import parse_manifest, validate_manifest
from ..package import canonical_json


def module_name(plugin_id):
    return re.sub(r'[^A-Za-z0-9_]', '_', plugin_id)


def distribution_name(plugin_id):
    return re.sub(r'[-_.]+', '_', plugin_id)


def _project_basename(directory):
    basename = os.path.basename(os.path.normpath(os.path.abspath(directory)))
    return basename or 'env-plugin'


def default_project_values(directory):
    basename = _project_basename(directory)
    slug = re.sub(r'[^a-z0-9]+', '-', basename.lower()).strip('-') or 'env-plugin'
    words = [word for word in re.split(r'[-_.\s]+', basename) if word]
    name = ' '.join(word[:1].upper() + word[1:] for word in words) or 'Env Plugin'
    return {
        'plugin_id': 'org.example.' + slug,
        'name': name,
        'version': '0.1.0',
        'description': '%s Env plugin' % name,
        'author': 'Plugin Author',
    }


def default_manifest(
    plugin_id,
    name,
    version='0.1.0',
    description=None,
    author='Plugin Author',
    register_command=True,
    webui=False,
):
    if description is None:
        description = '%s Env plugin' % name
    if author is None:
        author = 'Plugin Author'
    module = module_name(plugin_id)
    wheel = '%s-%s-py3-none-any.whl' % (distribution_name(plugin_id), version)
    manifest = {
        'schema_version': 1,
        'id': plugin_id,
        'name': name,
        'version': version,
        'description': description,
        'author': {'name': author},
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
        'commands': [],
        'backend': {'artifacts': []},
    }
    if register_command:
        manifest['commands'] = [
            {
                'name': module.replace('_', '-'),
                'entry': '%s.cli:main' % module,
                'description': 'Run %s' % name,
            }
        ]
        manifest['backend']['artifacts'] = [
            {'path': 'backend/' + wheel, 'format': 'source-wheel', 'role': 'plugin'}
        ]
    if webui:
        manifest['webui'] = {
            'entry': 'frontend/index.html',
            'icon': 'puzzle',
            'frontend_sdk': '>=1.0.0,<2.0.0',
            'keep_alive': False,
        }
    return manifest


def ensure_target_available(directory):
    directory = os.path.abspath(directory)
    if not os.path.exists(directory):
        return
    if not os.path.isdir(directory):
        raise UsageError("target path is not a directory: %s" % directory)
    if os.listdir(directory):
        raise UsageError("target directory is not empty: %s" % directory)


def init_project(
    directory,
    plugin_id=None,
    name=None,
    version=None,
    description=None,
    author=None,
    register_command=True,
    webui=False,
):
    directory = os.path.abspath(directory)
    defaults = default_project_values(directory)
    plugin_id = defaults['plugin_id'] if plugin_id is None else plugin_id
    name = defaults['name'] if name is None else name
    version = defaults['version'] if version is None else version
    description = '%s Env plugin' % name if description is None else description
    author = defaults['author'] if author is None else author
    ensure_target_available(directory)
    if not register_command and not webui:
        raise UsageError('a plugin must provide a command or a WebUI page')
    os.makedirs(directory, exist_ok=True)
    manifest = validate_manifest(
        default_manifest(
            plugin_id,
            name,
            version,
            description,
            author,
            register_command=register_command,
            webui=webui,
        )
    )
    package = module_name(plugin_id)
    _write_new(os.path.join(directory, 'manifest.json'), canonical_json(manifest.to_dict()))
    _write_new(
        os.path.join(directory, 'LICENSE'),
        b'Apache License 2.0\n\nReplace this placeholder with the complete license text before release.\n',
    )
    if register_command:
        source_dir = os.path.join(directory, 'src', package)
        tests_dir = os.path.join(directory, 'tests')
        os.makedirs(source_dir, exist_ok=True)
        os.makedirs(tests_dir, exist_ok=True)
        _write_new(
            os.path.join(source_dir, '__init__.py'),
            ('__version__ = "%s"\n' % version).encode('utf-8'),
        )
        command_source = (
            'def main(argv, context):\n'
            '    """Run the plugin command."""\n'
            '    print("Hello from %s %s")\n'
            '    if argv:\n'
            '        print("Arguments: %%s" %% " ".join(argv))\n'
            '    return 0\n' % (name.replace('"', '\\"'), version)
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
    if webui:
        frontend_dir = os.path.join(directory, 'frontend')
        os.makedirs(frontend_dir, exist_ok=True)
        escaped_name = html.escape(name, quote=True)
        _write_new(
            os.path.join(frontend_dir, 'index.html'),
            (
                '<!doctype html>\n'
                '<html lang="en">\n'
                '<head>\n'
                '  <meta charset="utf-8">\n'
                '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
                '  <title>%s</title>\n'
                '</head>\n'
                '<body>\n'
                '  <main>\n'
                '    <h1>%s</h1>\n'
                '    <p>Replace this page with your plugin WebUI.</p>\n'
                '  </main>\n'
                '</body>\n'
                '</html>\n' % (escaped_name, escaped_name)
            ).encode('utf-8'),
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
    requires_backend = bool(manifest.commands or manifest.health_check or manifest.service or manifest.artifacts)
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
    if manifest.service:
        _validate_source_entry(source_root, manifest.service['entry'])
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

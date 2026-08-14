import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from plugins.epack.builder import build_project
from plugins.epack import cli as epack_cli
from plugins.epack.project import init_project, validate_project
from plugins.errors import UsageError
from plugins.package import EpackArchive
from plugins.service import PluginService
from plugins.tests.helpers import build_epack_plugin, build_example


PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_EPACK_SCRIPT = os.path.join(PLUGIN_ROOT, 'epack', 'build_epack.py')


class EpackToolTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temporary.cleanup()

    def test_init_wizard_accepts_defaults(self):
        project = os.path.join(self.temporary.name, 'my-plugin')
        with mock.patch.object(epack_cli, '_interactive_terminal', return_value=True), mock.patch(
            'builtins.input', side_effect=['', '', '', '', '', '', '']
        ):
            result = epack_cli.run(['init', project])

        self.assertEqual(result, 0)
        with open(os.path.join(project, 'manifest.json'), 'r', encoding='utf-8') as manifest_file:
            manifest = json.load(manifest_file)
        self.assertEqual(manifest['id'], 'org.example.my-plugin')
        self.assertEqual(manifest['name'], 'My Plugin')
        self.assertEqual(manifest['version'], '0.1.0')
        self.assertEqual(manifest['description'], 'My Plugin Env plugin')
        self.assertEqual(manifest['author']['name'], 'Plugin Author')
        self.assertEqual(len(manifest['commands']), 1)
        self.assertNotIn('webui', manifest)

    def test_init_wizard_accepts_custom_metadata(self):
        project = os.path.join(self.temporary.name, 'custom')
        answers = ['org.example.custom', 'Custom Tool', '1.2.3', 'Custom description', 'Alice', '', '']
        with mock.patch.object(epack_cli, '_interactive_terminal', return_value=True), mock.patch(
            'builtins.input', side_effect=answers
        ):
            epack_cli.run(['init', project])

        with open(os.path.join(project, 'manifest.json'), 'r', encoding='utf-8') as manifest_file:
            manifest = json.load(manifest_file)
        self.assertEqual(manifest['id'], 'org.example.custom')
        self.assertEqual(manifest['name'], 'Custom Tool')
        self.assertEqual(manifest['version'], '1.2.3')
        self.assertEqual(manifest['description'], 'Custom description')
        self.assertEqual(manifest['author']['name'], 'Alice')
        with open(
            os.path.join(project, 'src', 'org_example_custom', '__init__.py'), 'r', encoding='utf-8'
        ) as version_file:
            self.assertIn('__version__ = "1.2.3"', version_file.read())

    def test_init_wizard_can_create_webui_only_project(self):
        project = os.path.join(self.temporary.name, 'web-tool')
        answers = ['', '', '', '', '', 'n', 'y']
        with mock.patch.object(epack_cli, '_interactive_terminal', return_value=True), mock.patch(
            'builtins.input', side_effect=answers
        ):
            epack_cli.run(['init', project])

        with open(os.path.join(project, 'manifest.json'), 'r', encoding='utf-8') as manifest_file:
            manifest = json.load(manifest_file)
        self.assertEqual(manifest['commands'], [])
        self.assertEqual(manifest['backend']['artifacts'], [])
        self.assertEqual(manifest['webui']['entry'], 'frontend/index.html')
        self.assertFalse(os.path.exists(os.path.join(project, 'src')))
        self.assertTrue(os.path.isfile(os.path.join(project, 'frontend', 'index.html')))
        validate_project(project)
        package = build_project(project, output_directory=os.path.join(self.temporary.name, 'dist'))
        summary = EpackArchive(package).inspect().summary()
        self.assertEqual(summary['commands'], [])
        self.assertEqual(summary['webui']['entry'], 'frontend/index.html')

    def test_init_explicit_capability_options(self):
        project = os.path.join(self.temporary.name, 'combined')
        epack_cli.run(['init', project, '--with-command', '--with-webui'])

        with open(os.path.join(project, 'manifest.json'), 'r', encoding='utf-8') as manifest_file:
            manifest = json.load(manifest_file)
        self.assertEqual(len(manifest['commands']), 1)
        self.assertEqual(manifest['webui']['entry'], 'frontend/index.html')
        self.assertTrue(os.path.isfile(os.path.join(project, 'src', 'org_example_combined', 'cli.py')))
        self.assertTrue(os.path.isfile(os.path.join(project, 'frontend', 'index.html')))

    def test_init_rejects_project_without_command_or_webui(self):
        project = os.path.join(self.temporary.name, 'empty-plugin')
        with self.assertRaisesRegex(UsageError, 'command or a WebUI'):
            epack_cli.run(['init', project, '--without-command', '--without-webui'])
        self.assertFalse(os.path.exists(project))

    def test_init_explicit_arguments_skip_wizard(self):
        project = os.path.join(self.temporary.name, 'explicit')
        with mock.patch.object(epack_cli, '_interactive_terminal', return_value=True), mock.patch(
            'builtins.input'
        ) as input_mock:
            epack_cli.run(['init', project, '--id', 'org.example.explicit', '--name', 'Explicit'])

        input_mock.assert_not_called()
        with open(os.path.join(project, 'manifest.json'), 'r', encoding='utf-8') as manifest_file:
            manifest = json.load(manifest_file)
        self.assertEqual(manifest['id'], 'org.example.explicit')
        self.assertEqual(manifest['name'], 'Explicit')
        self.assertEqual(manifest['description'], 'Explicit Env plugin')

    def test_init_non_tty_skips_wizard(self):
        project = os.path.join(self.temporary.name, 'noninteractive')
        with mock.patch.object(epack_cli, '_interactive_terminal', return_value=False), mock.patch(
            'builtins.input'
        ) as input_mock:
            epack_cli.run(['init', project])

        input_mock.assert_not_called()
        with open(os.path.join(project, 'manifest.json'), 'r', encoding='utf-8') as manifest_file:
            manifest = json.load(manifest_file)
        self.assertEqual(manifest['id'], 'org.example.noninteractive')

    def test_init_wizard_retries_invalid_value(self):
        project = os.path.join(self.temporary.name, 'retry')
        answers = ['invalid id', 'org.example.retry', '', '', '', '', '', '']
        with mock.patch.object(epack_cli, '_interactive_terminal', return_value=True), mock.patch(
            'builtins.input', side_effect=answers
        ):
            epack_cli.run(['init', project])

        with open(os.path.join(project, 'manifest.json'), 'r', encoding='utf-8') as manifest_file:
            manifest = json.load(manifest_file)
        self.assertEqual(manifest['id'], 'org.example.retry')

    def test_init_wizard_eof_is_usage_error(self):
        project = os.path.join(self.temporary.name, 'cancelled')
        with mock.patch.object(epack_cli, '_interactive_terminal', return_value=True), mock.patch(
            'builtins.input', side_effect=EOFError
        ):
            with self.assertRaisesRegex(UsageError, 'interactive initialization cancelled'):
                epack_cli.run(['init', project])

        self.assertFalse(os.path.exists(project))

    def test_init_validate_and_source_build(self):
        project = os.path.join(self.temporary.name, 'project')
        init_project(project, 'org.example.demo', 'Demo')
        manifest = validate_project(project)
        self.assertEqual(manifest.plugin_id, 'org.example.demo')
        package = build_project(project, output_directory=os.path.join(self.temporary.name, 'dist'))
        summary = EpackArchive(package).inspect().summary()
        self.assertEqual(summary['id'], 'org.example.demo')
        self.assertEqual(summary['backend']['artifacts'][0]['format'], 'source-wheel')

    def test_pyc_build_has_exact_abi(self):
        project = os.path.join(self.temporary.name, 'project')
        init_project(project, 'org.example.bytecode', 'Bytecode')
        package = build_project(
            project,
            output_directory=os.path.join(self.temporary.name, 'dist'),
            backend_format='pyc-wheel',
        )
        summary = EpackArchive(package).inspect().summary()
        self.assertTrue(summary['compatibility']['abis'][0].startswith('cp'))
        self.assertEqual(summary['backend']['artifacts'][0]['format'], 'pyc-wheel')
        env_root = os.path.join(self.temporary.name, 'env')
        launcher_dir = os.path.join(self.temporary.name, 'launchers')
        service = PluginService(env_root=env_root, launcher_dir=launcher_dir)
        service.install(package, allow_unsigned=True)
        launcher = os.path.join(launcher_dir, 'org-example-bytecode' + ('.cmd' if os.name == 'nt' else ''))
        process = subprocess.run(
            [launcher],
            cwd=self.temporary.name,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn('Hello from Bytecode', process.stdout)

    def test_build_is_reproducible(self):
        project = os.path.join(self.temporary.name, 'project')
        init_project(project, 'org.example.reproducible', 'Reproducible')
        first = build_project(project, output_directory=os.path.join(self.temporary.name, 'first'))
        second = build_project(project, output_directory=os.path.join(self.temporary.name, 'second'))
        with open(first, 'rb') as first_package, open(second, 'rb') as second_package:
            self.assertEqual(first_package.read(), second_package.read())

    def test_official_epack_is_optional_plugin(self):
        env_root = os.path.join(self.temporary.name, 'env')
        launcher_dir = os.path.join(self.temporary.name, 'launchers')
        packages = os.path.join(self.temporary.name, 'packages')
        os.makedirs(packages)
        epack_package = build_epack_plugin(packages)
        hello_package = build_example('1.0.0', packages)
        service = PluginService(env_root=env_root, launcher_dir=launcher_dir)
        service.install(epack_package, allow_unsigned=True)
        epack_launcher = os.path.join(launcher_dir, 'epack' + ('.cmd' if os.name == 'nt' else ''))
        workspace = os.path.join(self.temporary.name, 'workspace')
        os.makedirs(workspace)
        process = subprocess.run(
            [epack_launcher, 'init', 'created', '--id', 'org.example.created', '--name', 'Created'],
            cwd=workspace,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertTrue(os.path.isfile(os.path.join(workspace, 'created', 'manifest.json')))
        service.uninstall('org.rt-thread.epack')
        self.assertFalse(os.path.exists(epack_launcher))
        installed = service.install(hello_package, allow_unsigned=True)
        self.assertEqual(installed['id'], 'org.rt-thread.examples.hello')

    def test_official_build_script_supports_json_output(self):
        output = os.path.join(self.temporary.name, 'official-dist')
        process = subprocess.run(
            [sys.executable, BUILD_EPACK_SCRIPT, '--output', output, '--json'],
            cwd=self.temporary.name,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(os.path.isfile(result['package']))
        summary = EpackArchive(result['package']).inspect().summary()
        self.assertEqual(summary['id'], 'org.rt-thread.epack')


if __name__ == '__main__':
    unittest.main()

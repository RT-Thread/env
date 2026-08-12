import os
import subprocess
import tempfile
import unittest

from plugins.epack.builder import build_project
from plugins.epack.project import init_project, validate_project
from plugins.package import EpackArchive
from plugins.service import PluginService
from plugins.tests.helpers import build_epack_plugin, build_example


class EpackToolTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temporary.cleanup()

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


if __name__ == '__main__':
    unittest.main()

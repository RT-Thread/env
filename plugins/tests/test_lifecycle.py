import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest

from plugins.errors import CommandConflictError, CompatibilityError, StateError, TransactionError, UsageError
from plugins.installer import PluginInstaller
from plugins.launchers import LauncherManager
from plugins.paths import PluginPaths
from plugins.package import canonical_json, write_integrity
from plugins.service import PluginService
from plugins.store import StateStore
from plugins.tests.helpers import EXAMPLES, build_example, copy_project, rewrite_zip, update_manifest


class FailingStore(StateStore):
    def save(self, state):
        raise StateError('injected state write failure')


class LifecycleTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.env_root = os.path.join(self.temporary.name, 'env')
        self.launcher_dir = os.path.join(self.temporary.name, 'launchers')
        self.packages = os.path.join(self.temporary.name, 'packages')
        os.makedirs(self.packages)
        self.v1 = build_example('1.0.0', self.packages)
        self.v2 = build_example('1.1.0', self.packages)
        self.service = PluginService(env_root=self.env_root, launcher_dir=self.launcher_dir)

    def tearDown(self):
        self.temporary.cleanup()

    def launcher(self):
        return os.path.join(self.launcher_dir, 'env-plugin-hello' + ('.cmd' if os.name == 'nt' else ''))

    def invoke(self, *arguments, env=None):
        return subprocess.run(
            [self.launcher()] + list(arguments),
            cwd=self.temporary.name,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

    def test_full_lifecycle(self):
        with self.assertRaises(UsageError):
            self.service.install(self.v1)
        installed = self.service.install(self.v1, allow_unsigned=True)
        self.assertEqual(installed['version'], '1.0.0')
        first = self.invoke('argument')
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn('1.0.0', first.stdout)
        self.assertIn('Arguments: argument', first.stdout)

        upgraded = self.service.upgrade(self.v2, allow_unsigned=True)
        self.assertEqual(upgraded['version'], '1.1.0')
        second = self.invoke('--json')
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout)['version'], '1.1.0')
        self.assertEqual(self.service.doctor()['status'], 'ok')

        self.service.disable('org.rt-thread.examples.hello')
        self.assertFalse(os.path.exists(self.launcher()))
        self.service.enable('org.rt-thread.examples.hello')
        self.assertTrue(os.path.exists(self.launcher()))

        data_dir = os.path.join(self.env_root, 'var', 'plugins', 'data', 'org.rt-thread.examples.hello')
        self.assertTrue(os.path.isdir(data_dir))
        self.service.uninstall('org.rt-thread.examples.hello')
        self.assertFalse(os.path.exists(self.launcher()))
        self.assertTrue(os.path.isdir(data_dir))
        self.assertEqual(self.service.list(), [])

    def test_upgrade_preserves_disabled_state(self):
        self.service.install(self.v1, allow_unsigned=True)
        self.service.disable('org.rt-thread.examples.hello')
        result = self.service.upgrade(self.v2, allow_unsigned=True)
        self.assertFalse(result['enabled'])
        self.assertFalse(os.path.exists(self.launcher()))
        self.service.enable('org.rt-thread.examples.hello')
        self.assertIn('1.1.0', self.invoke().stdout)

    def test_incompatible_package_is_rejected_before_install(self):
        target = os.path.join(self.packages, 'incompatible.epack')

        def make_incompatible(files):
            manifest = json.loads(files['manifest.json'].decode('utf-8'))
            manifest['compatibility']['platforms'] = ['windows' if os.name != 'nt' else 'linux']
            files['manifest.json'] = canonical_json(manifest)
            payload = dict((name, content) for name, content in files.items() if name != 'integrity.json')
            files['integrity.json'] = canonical_json(write_integrity(payload))
            return files

        rewrite_zip(self.v1, target, make_incompatible)
        with self.assertRaises(CompatibilityError):
            self.service.install(target, allow_unsigned=True)
        self.assertEqual(self.service.list(), [])
        self.assertFalse(os.path.exists(self.launcher()))

    def test_failed_health_check_leaves_no_state(self):
        project = copy_project(os.path.join(EXAMPLES, 'hello-1.0.0'), os.path.join(self.temporary.name, 'unhealthy'))
        source_path = os.path.join(project, 'src', 'env_plugin_hello', 'cli.py')
        with open(source_path, 'w', encoding='utf-8') as source:
            source.write(
                'def health_check():\n'
                '    return 1\n\n'
                'def main(argv, context):\n'
                '    return 0\n'
            )
        package = build_example_project(project, self.packages)
        with self.assertRaisesRegex(TransactionError, 'health check failed'):
            self.service.install(package, allow_unsigned=True)
        self.assertEqual(self.service.list(), [])
        self.assertFalse(os.path.exists(self.launcher()))

    def test_purge_removes_private_data(self):
        self.service.install(self.v1, allow_unsigned=True)
        self.assertEqual(self.invoke().returncode, 0)
        private_root = os.path.join(self.env_root, 'var', 'plugins')
        plugin_id = 'org.rt-thread.examples.hello'
        for category in ('config', 'data', 'cache'):
            self.assertTrue(os.path.isdir(os.path.join(private_root, category, plugin_id)))
        self.service.uninstall(plugin_id, purge_data=True)
        for category in ('config', 'data', 'cache'):
            self.assertFalse(os.path.exists(os.path.join(private_root, category, plugin_id)))

    def test_command_conflict_is_rejected(self):
        self.service.install(self.v1, allow_unsigned=True)
        project = copy_project(os.path.join(EXAMPLES, 'hello-1.0.0'), os.path.join(self.temporary.name, 'conflict'))
        update_manifest(project, lambda data: data.update({'id': 'org.example.conflicting-plugin'}))
        conflicting = build_example_project(project, self.packages)
        with self.assertRaises(CommandConflictError):
            self.service.install(conflicting, allow_unsigned=True)

    def test_existing_path_command_is_rejected(self):
        self.assertIsNotNone(shutil.which('git'))
        project = copy_project(os.path.join(EXAMPLES, 'hello-1.0.0'), os.path.join(self.temporary.name, 'path-conflict'))

        def use_git(data):
            data['id'] = 'org.example.path-conflict'
            data['commands'][0]['name'] = 'git'

        update_manifest(project, use_git)
        conflicting = build_example_project(project, self.packages)
        with self.assertRaisesRegex(CommandConflictError, 'PATH'):
            self.service.install(conflicting, allow_unsigned=True)

    def test_dispatcher_hides_sensitive_environment(self):
        project = copy_project(os.path.join(EXAMPLES, 'hello-1.0.0'), os.path.join(self.temporary.name, 'environment'))
        source_path = os.path.join(project, 'src', 'env_plugin_hello', 'cli.py')
        with open(source_path, 'w', encoding='utf-8') as source:
            source.write(
                'import os\n\n'
                'def health_check():\n'
                '    return 0\n\n'
                'def main(argv, context):\n'
                '    print(os.environ.get("ENV_TEST_SECRET_TOKEN", "hidden"))\n'
                '    return 0\n'
            )
        package = build_example_project(project, self.packages)
        self.service.install(package, allow_unsigned=True)
        environment = dict(os.environ)
        environment['ENV_TEST_SECRET_TOKEN'] = 'must-not-reach-plugin'
        result = self.invoke(env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'hidden')

    def test_failed_install_rolls_back_files_and_launcher(self):
        paths = PluginPaths(env_root=self.env_root, launcher_dir=self.launcher_dir)
        installer = PluginInstaller(paths, LauncherManager(paths), FailingStore(paths))
        with self.assertRaisesRegex(StateError, 'injected'):
            installer.install(self.v1, allow_unsigned=True)
        self.assertFalse(os.path.exists(self.launcher()))
        self.assertFalse(os.path.exists(paths.version_dir('org.rt-thread.examples.hello', '1.0.0')))

    def test_failed_upgrade_retains_active_version(self):
        self.service.install(self.v1, allow_unsigned=True)
        paths = self.service.paths
        installer = PluginInstaller(paths, LauncherManager(paths), FailingStore(paths))
        with self.assertRaisesRegex(StateError, 'injected'):
            installer.install(self.v2, allow_unsigned=True, upgrade=True)
        self.assertEqual(self.service.info('org.rt-thread.examples.hello')['version'], '1.0.0')
        self.assertIn('1.0.0', self.invoke().stdout)
        self.assertFalse(os.path.exists(paths.version_dir('org.rt-thread.examples.hello', '1.1.0')))

    def test_failed_uninstall_restores_files_and_launcher(self):
        self.service.install(self.v1, allow_unsigned=True)
        paths = self.service.paths
        installer = PluginInstaller(paths, LauncherManager(paths), FailingStore(paths))
        with self.assertRaisesRegex(StateError, 'injected'):
            installer.uninstall('org.rt-thread.examples.hello')
        self.assertTrue(os.path.exists(self.launcher()))
        self.assertEqual(self.service.info('org.rt-thread.examples.hello')['version'], '1.0.0')
        self.assertIn('1.0.0', self.invoke().stdout)

    def test_uninstall_waits_for_running_command(self):
        project = copy_project(os.path.join(EXAMPLES, 'hello-1.0.0'), os.path.join(self.temporary.name, 'running'))
        source_path = os.path.join(project, 'src', 'env_plugin_hello', 'cli.py')
        with open(source_path, 'w', encoding='utf-8') as source:
            source.write(
                'import os\n'
                'import time\n\n'
                'def health_check():\n'
                '    return 0\n\n'
                'def main(argv, context):\n'
                '    with open(os.path.join(context.data_dir, "started"), "w") as marker:\n'
                '        marker.write("started")\n'
                '    time.sleep(1.0)\n'
                '    print("finished")\n'
                '    return 0\n'
            )
        package = build_example_project(project, self.packages)
        self.service.install(package, allow_unsigned=True)
        process = subprocess.Popen(
            [self.launcher()],
            cwd=self.temporary.name,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        marker = os.path.join(
            self.env_root,
            'var',
            'plugins',
            'data',
            'org.rt-thread.examples.hello',
            'started',
        )
        deadline = time.monotonic() + 5.0
        while not os.path.exists(marker) and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(os.path.exists(marker), 'plugin command did not start')
        started = time.monotonic()
        self.service.uninstall('org.rt-thread.examples.hello')
        elapsed = time.monotonic() - started
        stdout, stderr = process.communicate(timeout=2.0)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertIn('finished', stdout)
        self.assertGreater(elapsed, 0.5)
        self.assertFalse(os.path.exists(self.launcher()))


def build_example_project(project, output):
    from plugins.epack.builder import build_project

    return build_project(project, output_directory=output)


if __name__ == '__main__':
    unittest.main()

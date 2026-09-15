import ast
import json
import os
import stat
import tempfile
import unittest

from plugins.errors import CommandConflictError
from plugins.launchers import MARKER, LauncherManager
from plugins.paths import PluginPaths


class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.paths = PluginPaths(
            env_root=os.path.join(self.temporary.name, 'env root'),
            launcher_dir=os.path.join(self.temporary.name, 'launchers'),
        )

    def tearDown(self):
        self.temporary.cleanup()

    @unittest.skipIf(os.name == 'nt', 'POSIX launcher mode is not meaningful on Windows')
    def test_posix_launcher_is_executable_and_dispatches(self):
        manager = LauncherManager(self.paths, system='posix', dispatcher_module='plugins.dispatcher')
        manager.write('env-launcher-test')
        path = manager.path('env-launcher-test')
        with open(path, 'r', encoding='utf-8') as source:
            content = source.read()
        self.assertIn(MARKER, content)
        self.assertIn('plugins.dispatcher', content)
        self.assertTrue(os.stat(path).st_mode & stat.S_IXUSR)

    def test_default_launcher_dir_uses_env_venv_scripts(self):
        paths = PluginPaths(env_root=os.path.join(self.temporary.name, 'default env'))
        expected = os.path.abspath(
            os.path.join(paths.env_root, '.venv', 'Scripts' if os.name == 'nt' else 'bin')
        )
        self.assertEqual(paths.launchers, expected)
        paths.ensure()
        self.assertTrue(os.path.isdir(paths.launchers))

    def test_launcher_defaults_to_plugins_dispatcher(self):
        import plugins.launchers as launchers_module

        manager = LauncherManager(self.paths, system='windows')
        self.assertEqual(manager.dispatcher_module, 'plugins.dispatcher')
        self.assertEqual(
            manager.module_root,
            os.path.dirname(os.path.dirname(os.path.abspath(launchers_module.__file__))),
        )

    def test_windows_launcher_is_direct_cmd_entry(self):
        manager = LauncherManager(self.paths, system='windows', dispatcher_module='plugins.dispatcher')
        manager.write('env-launcher-test')
        path = manager.path('env-launcher-test')
        self.assertTrue(path.endswith('.cmd'))
        with open(path, 'r', encoding='ascii') as source:
            content = source.read()
        self.assertIn('rem ' + MARKER, content)
        self.assertIn('"%s" "%%~dp0.env-plugin-launcher-env-launcher-test.py" %%*' % manager.python_executable, content)
        self.assertTrue(os.path.isfile(manager.helper_path('env-launcher-test')))
        self.assertTrue(manager.is_managed('env-launcher-test'))

    def test_windows_launcher_preserves_unicode_paths(self):
        paths = PluginPaths(
            env_root=os.path.join(self.temporary.name, 'env-\u6d4b\u8bd5'),
            launcher_dir=os.path.join(self.temporary.name, 'launchers-\u6d4b\u8bd5'),
        )
        python_executable = os.path.join(self.temporary.name, 'Python-\u6d4b\u8bd5', 'python.exe')
        manager = LauncherManager(
            paths,
            system='windows',
            python_executable=python_executable,
            dispatcher_module='env.plugins.dispatcher',
        )
        manager.write('env-launcher-test')
        path = manager.path('env-launcher-test')
        with open(path, 'rb') as source:
            content = source.read().decode('ascii')
        self.assertNotIn('\u6d4b', content)
        with open(manager.helper_path('env-launcher-test'), 'r', encoding='ascii') as source:
            helper = source.read()
        config_line = next(line for line in helper.splitlines() if line.startswith('CONFIG = '))
        expression = config_line.split('=', 1)[1].strip()
        serialized = ast.literal_eval(expression[len('json.loads(') : -1])
        config = json.loads(serialized)
        self.assertEqual(config['env_root'], paths.env_root)
        self.assertEqual(config['python_executable'], os.path.abspath(python_executable))
        self.assertTrue(manager.is_managed('env-launcher-test'))
        self.assertTrue(manager._is_managed_file(manager.helper_path('env-launcher-test')))

    def test_windows_reserved_launcher_name_is_rejected(self):
        manager = LauncherManager(self.paths, system='windows', dispatcher_module='env.plugins.dispatcher')
        with self.assertRaises(CommandConflictError):
            manager.ensure_available('nul')


if __name__ == '__main__':
    unittest.main()

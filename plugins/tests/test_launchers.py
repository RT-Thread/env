import os
import stat
import tempfile
import unittest

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

    def test_posix_launcher_is_executable_and_dispatches(self):
        manager = LauncherManager(self.paths, system='posix', dispatcher_module='plugins.dispatcher')
        manager.write('env-launcher-test')
        path = manager.path('env-launcher-test')
        with open(path, 'r', encoding='utf-8') as source:
            content = source.read()
        self.assertIn(MARKER, content)
        self.assertIn('plugins.dispatcher', content)
        self.assertTrue(os.stat(path).st_mode & stat.S_IXUSR)

    def test_windows_launcher_is_direct_cmd_entry(self):
        manager = LauncherManager(self.paths, system='windows', dispatcher_module='env.plugins.dispatcher')
        manager.write('env-launcher-test')
        path = manager.path('env-launcher-test')
        self.assertTrue(path.endswith('.cmd'))
        with open(path, 'r', encoding='utf-8') as source:
            content = source.read()
        self.assertIn('REM ' + MARKER, content)
        self.assertIn('set "ENV_ROOT=', content)
        self.assertIn('-m env.plugins.dispatcher env-launcher-test %*', content)


if __name__ == '__main__':
    unittest.main()

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import vars
from cmds.cmd_package import cmd_package_update
from cmds.cmd_package import cmd_package_utils


class _Package:
    def __init__(self, url, repository):
        self._url = url
        self.pkg = {'repository': repository}

    def get_url(self, version):
        return self._url


class PackageUpdateSafetyTest(unittest.TestCase):
    def test_restore_url_does_not_convert_repository_homepage(self):
        package = _Package(
            'https://download.rt-thread.org/toolchain.tar.bz2',
            'http://gcc.gnu.org',
        )

        self.assertIsNone(cmd_package_update._get_git_restore_url(package, 'latest'))

    def test_restore_url_uses_version_specific_git_url(self):
        package = _Package(
            'https://github.com/example/package.git',
            'https://example.invalid/package',
        )

        self.assertEqual(
            'https://github.com/example/package.git',
            cmd_package_update._get_git_restore_url(package, 'latest'),
        )

    def test_env_repository_config_mutations_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_root = Path(temporary) / 'env'
            child = env_root / 'packages' / 'package'
            child.mkdir(parents=True)
            subprocess.check_call(['git', 'init', '-q', str(env_root)])
            subprocess.check_call(
                ['git', '-C', str(env_root), 'remote', 'add', 'origin', 'https://example.invalid/env.git']
            )

            with mock.patch.dict(vars.env_vars, {'env_root': str(env_root)}, clear=False):
                self.assertTrue(cmd_package_utils.is_env_repository(str(child)))
                cmd_package_utils.execute_command(
                    'git remote set-url origin http://gcc.gnu.org.git',
                    cwd=str(child),
                )

            self.assertEqual(
                'https://example.invalid/env.git',
                subprocess.check_output(
                    ['git', '-C', str(env_root), 'config', '--local', '--get', 'remote.origin.url'],
                    universal_newlines=True,
                ).strip(),
            )

    def test_gitee_package_remote_can_be_switched_for_prefetch(self):
        with tempfile.TemporaryDirectory() as temporary:
            package_root = Path(temporary) / 'package'
            package_root.mkdir()
            subprocess.check_call(['git', 'init', '-q', str(package_root)])
            subprocess.check_call(
                ['git', '-C', str(package_root), 'remote', 'add', 'origin',
                 'https://gitee.com/RT-Thread-Mirror/packages.git']
            )

            with mock.patch.dict(vars.env_vars, {'env_root': str(Path(temporary) / 'env')}, clear=False):
                self.assertFalse(cmd_package_utils.is_env_repository(str(package_root)))
                cmd_package_utils.execute_command(
                    'git remote set-url origin https://github.com/RT-Thread/packages.git',
                    cwd=str(package_root),
                )

            self.assertEqual(
                'https://github.com/RT-Thread/packages.git',
                subprocess.check_output(
                    ['git', '-C', str(package_root), 'config', '--local', '--get', 'remote.origin.url'],
                    universal_newlines=True,
                ).strip(),
            )

    def test_git_c_repository_config_mutations_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_root = Path(temporary) / 'env'
            env_root.mkdir()
            subprocess.check_call(['git', 'init', '-q', str(env_root)])
            subprocess.check_call(
                ['git', '-C', str(env_root), 'remote', 'add', 'origin', 'https://example.invalid/env.git']
            )

            with mock.patch.dict(vars.env_vars, {'env_root': str(env_root)}, clear=False):
                cmd_package_utils.execute_command(
                    'git -C "{}" remote set-url origin http://gcc.gnu.org.git'.format(env_root),
                    cwd=temporary,
                )

            self.assertEqual(
                'https://example.invalid/env.git',
                subprocess.check_output(
                    ['git', '-C', str(env_root), 'config', '--local', '--get', 'remote.origin.url'],
                    universal_newlines=True,
                ).strip(),
            )

    def test_relative_git_c_repository_config_mutations_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_root = Path(temporary) / 'env'
            env_root.mkdir()
            subprocess.check_call(['git', 'init', '-q', str(env_root)])
            subprocess.check_call(
                ['git', '-C', str(env_root), 'remote', 'add', 'origin', 'https://example.invalid/env.git']
            )

            with mock.patch.dict(vars.env_vars, {'env_root': str(env_root)}, clear=False):
                cmd_package_utils.execute_command(
                    'git -C env remote set-url origin http://gcc.gnu.org.git',
                    cwd=temporary,
                )

            self.assertEqual(
                'https://example.invalid/env.git',
                subprocess.check_output(
                    ['git', '-C', str(env_root), 'config', '--local', '--get', 'remote.origin.url'],
                    universal_newlines=True,
                ).strip(),
            )

    def test_tools_scripts_repository_is_protected_by_env_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_root = Path(temporary) / 'env'
            scripts_root = env_root / 'tools' / 'scripts'
            child = scripts_root / 'packages' / 'package'
            child.mkdir(parents=True)
            subprocess.check_call(['git', 'init', '-q', str(scripts_root)])

            with mock.patch.dict(vars.env_vars, {'env_root': str(env_root)}, clear=False):
                self.assertTrue(cmd_package_utils.is_env_repository(str(child)))


if __name__ == '__main__':
    unittest.main()

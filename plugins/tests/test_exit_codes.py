import argparse
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import env
import vars
from cmds import cmd_menuconfig, cmd_sdk
from cmds.cmd_package import cmd_package_update, cmd_package_utils


REPOSITORY = Path(__file__).resolve().parents[2]


class ExitCodeTest(unittest.TestCase):
    def test_boolean_legacy_and_integer_results(self):
        for result, expected in ((None, 0), (True, 0), (False, 1), (0, 0), (7, 7), (-1, 1)):
            with self.subTest(result=result):
                args = argparse.Namespace(func=lambda args: result)
                self.assertEqual(env.run_command(args), expected)

    def test_expected_errors_and_child_failures(self):
        for error, expected in ((OSError('missing'), 1), (ValueError('invalid'), 1),
                                (subprocess.CalledProcessError(7, ['tool']), 7)):
            with self.subTest(error=error), mock.patch('sys.stderr'):
                self.assertEqual(env.run_command(argparse.Namespace(func=mock.Mock(side_effect=error))), expected)

    def test_missing_configuration_is_a_process_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ, ENV_ROOT=directory)
            for arguments in (['menuconfig'], ['pkg', '--update'], ['pkg', '--list'], ['sdk']):
                with self.subTest(arguments=arguments):
                    result = subprocess.run(
                        [sys.executable, str(REPOSITORY / 'env.py')] + arguments,
                        cwd=directory, env=environment, capture_output=True, text=True, timeout=20,
                    )
                    self.assertNotEqual(result.returncode, 0)
            result = subprocess.run([sys.executable, str(REPOSITORY / 'env.py'), '--help'],
                                    cwd=directory, env=environment, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0)

    def test_missing_header_source_returns_failure(self):
        self.assertFalse(cmd_menuconfig.mk_rtconfig('/missing-env-test/config'))

    def test_package_stage_failure_is_propagated(self):
        with mock.patch.object(cmd_package_update, 'pre_package_update', return_value=False):
            self.assertFalse(cmd_package_update.package_update())
        with mock.patch.object(cmd_package_update, 'pre_package_update', return_value=['state']), mock.patch.object(
            cmd_package_update, 'delete_useless_packages', return_value=False,
        ):
            self.assertFalse(cmd_package_update.package_update())

    def test_subprocess_helper_checks_return_code(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {'ENV_ROOT': directory}):
            with self.assertRaises(subprocess.CalledProcessError) as failure:
                cmd_package_utils.execute_command([sys.executable, '-c', 'raise SystemExit(7)'], shell=False)
            self.assertEqual(failure.exception.returncode, 7)
            self.assertEqual(cmd_package_utils.execute_command([sys.executable, '-c', 'print("ok")'], shell=False), 'ok\n')

    def test_failed_auto_package_update_does_not_print_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_dir = root / 'tools' / 'scripts' / 'cmds'
            config_dir.mkdir(parents=True)
            (config_dir / '.config').write_text('CONFIG_SYS_AUTO_UPDATE_PKGS=y\n', encoding='ascii')
            args = argparse.Namespace(menuconfig_setting=False, menuconfig_g=False,
                                      menuconfig_fn=None, menuconfig_silent=False)
            with mock.patch.dict(vars.env_vars, {'env_root': directory, 'bsp_root': directory}), mock.patch.object(
                cmd_menuconfig, 'get_rtt_root', return_value=None,
            ), mock.patch.object(cmd_menuconfig.os.path, 'exists', return_value=True), mock.patch(
                'menuconfig.menuconfig',
            ), mock.patch('kconfiglib.Kconfig'), mock.patch.object(
                cmd_menuconfig.subprocess, 'call', return_value=7,
            ), mock.patch('builtins.print') as output:
                self.assertEqual(cmd_menuconfig.cmd(args), 7)
            self.assertFalse(any('updated completely' in str(call) for call in output.call_args_list))

    def test_sdk_restores_working_directory_and_context_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'tools' / 'scripts'
            root.mkdir(parents=True)
            before = os.getcwd()
            before_argv = sys.argv
            before_hostos = os.environ.get('HOSTOS')
            with mock.patch.dict(vars.env_vars, {'env_root': directory, 'bsp_root': before}), mock.patch(
                'menuconfig.menuconfig',
            ), mock.patch('kconfiglib.Kconfig'), mock.patch('cmds.cmd_package.package_update', return_value=False):
                self.assertFalse(cmd_sdk.cmd(argparse.Namespace()))
                self.assertEqual(os.getcwd(), before)
                self.assertEqual(vars.env_vars['bsp_root'], before)
                self.assertIs(sys.argv, before_argv)
                self.assertEqual(os.environ.get('HOSTOS'), before_hostos)
            self.assertFalse((root / 'sdk_list.json').exists())


if __name__ == '__main__':
    unittest.main()

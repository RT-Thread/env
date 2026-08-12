import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import env_venv


REPOSITORY = Path(__file__).resolve().parents[2]


class FakeRunner:
    def __init__(self, venv_root, source_root):
        self.venv_root = Path(venv_root)
        self.source_root = Path(source_root).resolve()
        self.commands = []

    def __call__(self, command):
        command = [str(value) for value in command]
        self.commands.append(command)
        if command[1:3] == ['-m', 'venv']:
            layout = env_venv.venv_layout(self.venv_root)
            layout['python'].parent.mkdir(parents=True, exist_ok=True)
            layout['python'].write_text('python\n', encoding='utf-8')
            layout['activate'].write_text('activate\n', encoding='utf-8')
        if command[1:4] == ['-m', 'pip', 'install'] and command[-1] == str(self.source_root):
            layout = env_venv.venv_layout(self.venv_root)
            layout['rt_env'].write_text('rt-env\n', encoding='utf-8')


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def read(self, size=-1):
        return self.content[:size]


class EnvVenvTest(unittest.TestCase):
    def setUp(self):
        self.environment = mock.patch.dict(os.environ, {'ENV_PYPI_INDEX_URL': ''})
        self.environment.start()
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / 'tools' / 'scripts'
        self.venv = self.root / '.venv'
        self.activation = self.root / 'env.sh'
        self._create_source()

    def tearDown(self):
        self.temporary.cleanup()
        self.environment.stop()

    def _write(self, relative, content):
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def _create_source(self):
        self._write('setup.py', 'from setuptools import setup\n')
        self._write('pyproject.toml', '[tool.black]\n')
        self._write('env.json', '{"version": "v2.0.2"}\n')
        self._write('env.sh', 'source activation v1\n')
        self._write('env.ps1', 'powershell activation v1\n')
        self._write('env_venv.py', 'bootstrap v1\n')
        self._write('env.py', 'runtime root v1\n')
        self._write('cmds/tool.py', 'command v1\n')
        self._write('plugins/runtime.py', 'plugin v1\n')
        self._write('plugins/README.md', 'plugin documentation v1\n')
        self._write('plugins/webui/static/index.html', '<p>runtime v1</p>\n')
        self._write('plugins/tests/test_ignored.py', 'test v1\n')
        self._write('plugins/examples/example.txt', 'example v1\n')
        self._write('plugins/webui/frontend/src/App.vue', 'frontend v1\n')
        self._write('docs/ignored.md', 'docs v1\n')

    def _install(self, country='US'):
        runner = FakeRunner(self.venv, self.source)
        status = env_venv.ensure_environment(
            self.venv,
            self.source,
            self.activation,
            command_runner=runner,
            country_detector=lambda: country,
        )
        return status, runner

    def test_fingerprint_tracks_runtime_and_ignores_development_files(self):
        original = env_venv.source_fingerprint(self.source)
        self._write('docs/ignored.md', 'docs v2\n')
        self._write('plugins/tests/test_ignored.py', 'test v2\n')
        self._write('plugins/examples/example.txt', 'example v2\n')
        self._write('plugins/webui/frontend/src/App.vue', 'frontend v2\n')
        self._write('plugins/README.md', 'plugin documentation v2\n')
        self.assertEqual(env_venv.source_fingerprint(self.source), original)

        self._write('cmds/tool.py', 'command v2\n')
        self.assertNotEqual(env_venv.source_fingerprint(self.source), original)

    def test_initial_install_uses_aliyun_and_writes_sanitized_state(self):
        status, runner = self._install(country='CN')
        self.assertEqual(status, 'created')
        self.assertEqual(self.activation.read_text(encoding='utf-8'), 'source activation v1\n')
        pip_commands = [command for command in runner.commands if command[1:4] == ['-m', 'pip', 'install']]
        self.assertEqual(len(pip_commands), 2)
        self.assertTrue(all(env_venv.ALIYUN_INDEX_URL in command for command in pip_commands))

        with (self.venv / env_venv.STATE_FILENAME).open('r', encoding='utf-8') as source:
            state = json.load(source)
        self.assertEqual(state['schema'], env_venv.STATE_SCHEMA)
        self.assertEqual(state['index'], 'aliyun')
        self.assertNotIn('index_url', state)

    def test_current_install_does_not_prompt_run_pip_or_detect_country(self):
        self._install()
        runner = FakeRunner(self.venv, self.source)

        def unexpected():
            raise AssertionError('current installations must not prompt or detect the country')

        status = env_venv.ensure_environment(
            self.venv,
            self.source,
            self.activation,
            command_runner=runner,
            country_detector=unexpected,
            confirmation=unexpected,
        )
        self.assertEqual(status, 'current')
        self.assertEqual(runner.commands, [])

    def test_declined_upgrade_keeps_state_and_activation_copy(self):
        self._install()
        old_state = (self.venv / env_venv.STATE_FILENAME).read_text(encoding='utf-8')
        self._write('env.sh', 'source activation v2\n')
        runner = FakeRunner(self.venv, self.source)
        status = env_venv.ensure_environment(
            self.venv,
            self.source,
            self.activation,
            command_runner=runner,
            country_detector=lambda: (_ for _ in ()).throw(AssertionError('must not detect country')),
            confirmation=lambda: False,
        )
        self.assertEqual(status, 'declined')
        self.assertEqual(runner.commands, [])
        self.assertEqual(self.activation.read_text(encoding='utf-8'), 'source activation v1\n')
        self.assertEqual((self.venv / env_venv.STATE_FILENAME).read_text(encoding='utf-8'), old_state)

    def test_confirmed_upgrade_reinstalls_and_synchronizes_activation(self):
        self._install()
        self._write('env.sh', 'source activation v2\n')
        runner = FakeRunner(self.venv, self.source)
        status = env_venv.ensure_environment(
            self.venv,
            self.source,
            self.activation,
            command_runner=runner,
            country_detector=lambda: 'US',
            confirmation=lambda: True,
        )
        self.assertEqual(status, 'upgraded')
        self.assertEqual(self.activation.read_text(encoding='utf-8'), 'source activation v2\n')
        pip_commands = [command for command in runner.commands if command[1:4] == ['-m', 'pip', 'install']]
        self.assertEqual(len(pip_commands), 1)
        self.assertNotIn('--index-url', pip_commands[0])
        self.assertEqual(env_venv.read_state(self.venv)['fingerprint'], env_venv.source_fingerprint(self.source))

    def test_missing_package_is_repaired_without_upgrade_prompt(self):
        layout = env_venv.venv_layout(self.venv)
        layout['python'].parent.mkdir(parents=True)
        layout['python'].write_text('python\n', encoding='utf-8')
        layout['activate'].write_text('activate\n', encoding='utf-8')
        runner = FakeRunner(self.venv, self.source)
        status = env_venv.ensure_environment(
            self.venv,
            self.source,
            self.activation,
            command_runner=runner,
            country_detector=lambda: 'US',
            confirmation=lambda: (_ for _ in ()).throw(AssertionError('repair must not prompt')),
        )
        self.assertEqual(status, 'repaired')
        self.assertTrue(layout['rt_env'].is_file())

    def test_country_detection_and_explicit_index_override(self):
        with mock.patch.object(env_venv, 'urlopen', return_value=FakeResponse(b'CN\n')) as request:
            self.assertEqual(env_venv.detect_country(), 'CN')
        self.assertEqual(request.call_args[1]['timeout'], 3)

        with mock.patch.object(env_venv, 'urlopen', side_effect=OSError('offline')):
            self.assertIsNone(env_venv.detect_country())

        output = io.StringIO()
        with mock.patch('sys.stdout', new=output):
            selected = env_venv.select_index_url(
                country_detector=lambda: (_ for _ in ()).throw(AssertionError('override must skip detection')),
                environ={'ENV_PYPI_INDEX_URL': 'https://user:secret@example.invalid/simple'},
            )
        self.assertEqual(selected, 'https://user:secret@example.invalid/simple')
        self.assertNotIn('secret', output.getvalue())

    def test_windows_layout_uses_scripts_directory(self):
        layout = env_venv.venv_layout(self.venv, platform_name='nt')
        self.assertEqual(layout['python'], self.venv.resolve() / 'Scripts' / 'python.exe')
        self.assertEqual(layout['activate'], self.venv.resolve() / 'Scripts' / 'Activate.ps1')
        self.assertEqual(layout['rt_env'], self.venv.resolve() / 'Scripts' / 'rt-env.exe')

    def test_default_activation_script_is_beside_the_venv(self):
        self.assertEqual(
            env_venv.default_activation_script(self.venv, platform_name='posix'),
            self.root.resolve() / 'env.sh',
        )
        self.assertEqual(
            env_venv.default_activation_script(self.venv, platform_name='nt'),
            self.root.resolve() / 'env.ps1',
        )

    def test_legacy_arguments_derive_source_and_activation_defaults(self):
        with mock.patch.object(env_venv, 'ensure_environment', return_value='current') as ensure:
            result = env_venv.main(['--venv', str(self.venv)])

        self.assertEqual(result, 0)
        self.assertEqual(ensure.call_args.args[0], str(self.venv))
        self.assertEqual(ensure.call_args.args[1], Path(env_venv.__file__).resolve().parent)
        self.assertEqual(ensure.call_args.args[2], self.root.resolve() / 'env.sh')

    def test_mark_current_legacy_argument_records_state_and_syncs_activation(self):
        layout = env_venv.venv_layout(self.venv)
        layout['python'].parent.mkdir(parents=True)
        layout['python'].write_text('python\n', encoding='utf-8')
        layout['activate'].write_text('activate\n', encoding='utf-8')
        layout['rt_env'].write_text('rt-env\n', encoding='utf-8')

        result = env_venv.main(
            [
                '--venv',
                str(self.venv),
                '--source',
                str(self.source),
                '--mark-current',
            ]
        )

        self.assertEqual(result, 0)
        self.assertEqual(self.activation.read_text(encoding='utf-8'), 'source activation v1\n')
        state = env_venv.read_state(self.venv)
        self.assertEqual(state['source'], str(self.source.resolve()))
        self.assertEqual(state['fingerprint'], env_venv.source_fingerprint(self.source))
        self.assertEqual(state['index'], 'existing')

    def test_legacy_env_sh_can_call_new_helper_with_only_venv(self):
        env_root = self.root / 'legacy-env'
        scripts = env_root / 'tools' / 'scripts'
        scripts.mkdir(parents=True)
        scripts_env_venv = scripts / 'env_venv.py'
        scripts_env_venv.write_text((REPOSITORY / 'env_venv.py').read_text(encoding='utf-8'), encoding='utf-8')
        for name in ('env.sh', 'env.ps1', 'setup.py', 'env.py', 'env.json'):
            (scripts / name).write_text((REPOSITORY / name).read_text(encoding='utf-8'), encoding='utf-8')
        for directory_name in ('cmds', 'plugins'):
            (scripts / directory_name).mkdir()

        copied_legacy_script = env_root / 'env.sh'
        copied_legacy_script.write_text(
            'VENV_ROOT="$ENV_ROOT/.venv"\n'
            'ENV_SCRIPTS="$ENV_ROOT/tools/scripts"\n'
            '. "$VENV_ROOT/bin/activate"\n'
            'python "$ENV_SCRIPTS/env_venv.py" --venv "$VENV_ROOT" --mark-current || return $?\n'
            'python "$ENV_SCRIPTS/env_venv.py" --venv "$VENV_ROOT"\n',
            encoding='utf-8',
        )
        layout = env_venv.venv_layout(env_root / '.venv')
        layout['python'].parent.mkdir(parents=True)
        layout['python'].symlink_to(Path(sys.executable).resolve())
        layout['activate'].write_text(
            'PATH="%s:$PATH"\nexport PATH\nENV_TEST_ACTIVATED=1\nexport ENV_TEST_ACTIVATED\n'
            % layout['python'].parent,
            encoding='utf-8',
        )
        layout['rt_env'].write_text('rt-env\n', encoding='utf-8')

        result = subprocess.run(
            [
                'sh',
                '-c',
                '. "$ENV_ROOT/env.sh"; env_status=$?; '
                'test "$ENV_TEST_ACTIVATED" = 1 && test "$env_status" -eq 0',
            ],
            env=dict(os.environ, HOME=str(self.root), ENV_ROOT=str(env_root)),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('arguments are required', result.stderr)
        self.assertEqual(
            copied_legacy_script.read_text(encoding='utf-8'),
            (scripts / 'env.sh').read_text(encoding='utf-8'),
        )
        self.assertIsNotNone(env_venv.read_state(env_root / '.venv'))

    def test_env_sh_attempts_activation_after_bootstrap_failure(self):
        env_root = self.root / 'shell-env'
        scripts = env_root / 'tools' / 'scripts'
        scripts.mkdir(parents=True)
        (env_root / 'env.sh').write_text((REPOSITORY / 'env.sh').read_text(encoding='utf-8'), encoding='utf-8')
        (scripts / 'env_venv.py').write_text('raise SystemExit(7)\n', encoding='utf-8')
        activate = env_root / '.venv' / 'bin' / 'activate'
        activate.parent.mkdir(parents=True)
        activate.write_text('ENV_TEST_ACTIVATED=1\nexport ENV_TEST_ACTIVATED\n', encoding='utf-8')

        result = subprocess.run(
            [
                'sh',
                '-c',
                '. "$ENV_ROOT/env.sh"; env_status=$?; '
                'test "$ENV_TEST_ACTIVATED" = 1 && test "$env_status" -eq 7',
            ],
            env=dict(os.environ, ENV_ROOT=str(env_root)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()

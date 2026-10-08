import os
import sys

import pytest

import env
import vars
from cmds.cmd_package import cmd_package_utils


@pytest.fixture(autouse=True)
def restore_command_context(monkeypatch):
    monkeypatch.setattr(vars, 'env_vars', vars.env_vars.copy())
    for name in ('ENV_ROOT', 'PKGS_ROOT', 'PKGS_DIR', 'BSP_ROOT', 'BSP_DIR'):
        monkeypatch.setenv(name, os.environ.get(name, ''))


@pytest.mark.parametrize('command', ('pkg', 'system', 'menuconfig', 'sdk'))
def test_command_adapter_passes_arguments_without_mutating_process_state(monkeypatch, command):
    arguments = ['entry', '--help']
    monkeypatch.setattr(sys, 'argv', arguments)
    received = []
    monkeypatch.setattr(env, 'main', lambda argv: received.append(argv) or 7)
    assert env.exec_arg(command) == 7
    assert sys.argv is arguments
    assert arguments == ['entry', '--help']
    assert received == [[command, '--help']]


def test_explicit_arguments_are_not_modified(monkeypatch):
    arguments = ['--generate']
    received = []
    monkeypatch.setattr(env, 'main', lambda argv: received.append(argv) or 0)
    assert env.exec_arg('menuconfig', arguments) == 0
    assert arguments == ['--generate']
    assert received == [['menuconfig', '--generate']]


def test_package_help_does_not_require_a_shell_entrypoint(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('ENV_ROOT', str(tmp_path))
    monkeypatch.setenv('PATH', '')
    monkeypatch.setattr(env, 'show_version_warning', lambda: None)
    assert env.main(['pkg']) == 0
    help_text = capsys.readouterr().out
    assert 'usage: rt-env pkg' in help_text
    assert '--update' in help_text
    assert '--upgrade-modules' in help_text


def test_repeated_entry_calls_do_not_accumulate_arguments(tmp_path, monkeypatch, capsys):
    arguments = ['pkgs']
    monkeypatch.setattr(sys, 'argv', arguments)
    monkeypatch.setenv('ENV_ROOT', str(tmp_path))
    monkeypatch.setattr(env, 'show_version_warning', lambda: None)
    assert env.pkgs() == 0
    assert env.pkgs() == 0
    assert arguments == ['pkgs']
    assert capsys.readouterr().out.count('usage: rt-env pkg') == 2


def test_python_input_helper_keeps_optional_prompt(monkeypatch):
    received = []
    monkeypatch.setattr('builtins.input', lambda *args: received.append(args) or 'answer')
    assert cmd_package_utils.user_input() == 'answer'
    assert cmd_package_utils.user_input('prompt') == 'answer'
    assert received == [(), ('prompt',)]

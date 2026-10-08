from pathlib import Path

import pytest

import env
import env_paths
import vars
from cmds import cmd_menuconfig
from ebuild import toolchain
from plugins.paths import default_env_root
from sdk_manager import _default_env_root


@pytest.fixture(autouse=True)
def clean_root_overrides(monkeypatch):
    for name in ('ENV_ROOT', 'PKGS_ROOT', 'RTT_ROOT'):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize('system, home_variable', [('Linux', 'HOME'), ('Windows', 'USERPROFILE')])
def test_default_env_root_is_shared(tmp_path, monkeypatch, system, home_variable):
    monkeypatch.setattr(env_paths.platform, 'system', lambda: system)
    monkeypatch.setenv(home_variable, str(tmp_path))
    expected = str(tmp_path / '.env')
    assert env.get_env_root() == expected
    assert default_env_root() == expected
    assert _default_env_root() == expected
    assert toolchain._env_root() == expected


def test_custom_relative_env_root_is_normalized(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('ENV_ROOT', 'custom env')
    expected = str(tmp_path / 'custom env')
    assert env.get_env_root() == expected
    assert default_env_root() == expected
    assert _default_env_root() == expected
    assert toolchain._env_root() == expected
    assert env.get_package_root() == str(Path(expected) / 'packages')


def test_package_root_override(tmp_path, monkeypatch):
    monkeypatch.setenv('PKGS_ROOT', str(tmp_path / 'custom packages'))
    assert env.get_package_root() == str(tmp_path / 'custom packages')


@pytest.mark.parametrize('contents', [
    'config RTT_DIR\n    string "Root"\n    help\n        Variable length help.\n    default "../RT Thread"\n',
    'RTT_DIR := "../RT Thread"\n',
])
def test_kconfig_root_is_independent_of_line_offsets(tmp_path, monkeypatch, contents):
    bsp = tmp_path / 'board'
    bsp.mkdir()
    (bsp / 'Kconfig').write_text(contents, encoding='ascii')
    monkeypatch.chdir(bsp)
    monkeypatch.setitem(vars.env_vars, 'bsp_root', str(bsp))
    expected = str(tmp_path / 'RT Thread')
    assert env.get_rtt_root() == expected
    assert cmd_menuconfig.get_rtt_root() == expected


def test_rtt_root_override_has_priority(tmp_path, monkeypatch):
    (tmp_path / 'Kconfig').write_text('RTT_DIR := ignored\n', encoding='ascii')
    monkeypatch.setenv('RTT_ROOT', str(tmp_path / 'override'))
    assert env_paths.get_rtt_root(str(tmp_path)) == str(tmp_path / 'override')


def test_embedded_and_ancestor_root_detection(tmp_path):
    embedded_include = tmp_path / 'rt-thread' / 'include'
    embedded_include.mkdir(parents=True)
    (embedded_include / 'rtdef.h').touch()
    assert env_paths.get_rtt_root(str(tmp_path)) == str(embedded_include.parent)

    tree = tmp_path / 'source'
    include = tree / 'include'
    include.mkdir(parents=True)
    (include / 'rtdef.h').touch()
    bsp = tree / 'bsp' / 'vendor' / 'board'
    bsp.mkdir(parents=True)
    assert env_paths.get_rtt_root(str(bsp)) == str(tree)


def test_incomplete_or_commented_kconfig_does_not_raise(tmp_path):
    (tmp_path / 'Kconfig').write_text(
        '# config RTT_DIR\nconfig RTT_DIR\nconfig OTHER\n    default "not-a-root"\n', encoding='ascii',
    )
    assert env_paths.get_rtt_root(str(tmp_path)) is None

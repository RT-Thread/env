import argparse
import json
import os
import sys
from pathlib import Path

import kconfiglib
import menuconfig
import pytest

import env
import vars
from cmds import cmd_menuconfig, cmd_sdk
from cmds import cmd_package
from ebuild.kconfig import KconfigManager


REPOSITORY = Path(__file__).resolve().parents[1]
KCONFIG = '''mainmenu "Test configuration"

config ENABLE_FEATURE
    bool "Enable feature"

config FEATURE_VALUE
    string "Feature value"
    depends on ENABLE_FEATURE
    default "fallback"

config RETRY_COUNT
    int "Retry count"
    default 3
'''


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / 'project with spaces'
    root.mkdir()
    (root / 'Kconfig').write_text(KCONFIG, encoding='ascii')
    (root / 'packages').mkdir()
    monkeypatch.chdir(root)
    monkeypatch.setitem(vars.env_vars, 'env_root', str(tmp_path))
    monkeypatch.setitem(vars.env_vars, 'bsp_root', str(root))
    monkeypatch.setenv('LANG', 'C')
    monkeypatch.delenv('KCONFIG_CONFIG', raising=False)
    monkeypatch.delenv('RTT_ROOT', raising=False)
    return root


def menuconfig_args(*arguments):
    return env.init_argparse().parse_args(['menuconfig'] + list(arguments))


def save_configuration(kconf):
    assert isinstance(kconf, kconfiglib.Kconfig)
    kconf.syms['ENABLE_FEATURE'].set_value('y')
    kconf.write_config()


def test_native_frontend_is_not_bundled():
    assert not (REPOSITORY / 'kconfig-mconf.zip').exists()
    assert not hasattr(cmd_menuconfig, 'build_kconfig_frontends')
    assert not hasattr(cmd_menuconfig, 'is_in_powershell')


def test_frontend_cleanup_removes_unused_dependency():
    tomllib = pytest.importorskip('tomllib')
    with (REPOSITORY / 'pyproject.toml').open('rb') as source:
        configuration = tomllib.load(source)
    dependencies = configuration['project']['dependencies']
    assert not any(requirement.split(';', 1)[0].strip() == 'psutil' for requirement in dependencies)


def test_menuconfig_uses_public_frontend_without_changing_arguments(project, monkeypatch):
    arguments = sys.argv
    seen = []

    def frontend(kconf):
        assert sys.argv is arguments
        seen.append(kconf)
        save_configuration(kconf)

    monkeypatch.setattr(menuconfig, 'menuconfig', frontend)
    assert cmd_menuconfig.cmd(menuconfig_args()) is None
    assert len(seen) == 1
    assert sys.argv is arguments
    header = (project / 'rtconfig.h').read_text(encoding='ascii')
    assert '#define ENABLE_FEATURE\n' in header
    assert '#define FEATURE_VALUE "fallback"\n' in header


def test_env_settings_restore_directory_on_frontend_failure(project, tmp_path, monkeypatch):
    settings = tmp_path / 'tools' / 'scripts' / 'cmds'
    settings.mkdir(parents=True)
    (settings / 'Kconfig').write_text(KCONFIG, encoding='ascii')
    arguments = sys.argv

    def frontend(kconf):
        assert Path.cwd() == settings
        assert sys.argv is arguments
        assert isinstance(kconf, kconfiglib.Kconfig)
        raise RuntimeError('frontend failed')

    monkeypatch.setattr(menuconfig, 'menuconfig', frontend)
    with pytest.raises(RuntimeError, match='frontend failed'):
        cmd_menuconfig.cmd(menuconfig_args('--setting'))
    assert Path.cwd() == project
    assert sys.argv is arguments


@pytest.mark.parametrize('use_custom_config', (False, True))
def test_silent_configuration_needs_no_terminal_frontend(project, monkeypatch, use_custom_config):
    source = project / ('custom.config' if use_custom_config else '.config')
    source.write_text(
        '# CONFIG_ENABLE_FEATURE is not set\nCONFIG_FEATURE_VALUE="ignored"\n', encoding='ascii',
    )
    monkeypatch.setitem(sys.modules, 'menuconfig', None)
    monkeypatch.setitem(sys.modules, 'defconfig', None)
    arguments = sys.argv
    options = ['--silent']
    if use_custom_config:
        options.extend(['--config', str(source)])

    assert cmd_menuconfig.cmd(menuconfig_args(*options)) is None
    assert sys.argv is arguments
    configuration = (project / '.config').read_text(encoding='ascii')
    assert 'CONFIG_FEATURE_VALUE=' not in configuration
    assert 'CONFIG_RETRY_COUNT=3\n' in configuration
    header = (project / 'rtconfig.h').read_text(encoding='ascii')
    assert '#define RETRY_COUNT 3\n' in header
    assert '#define FEATURE_VALUE' not in header


def test_header_generation_needs_no_kconfig_frontend(project, monkeypatch):
    (project / '.config').write_text('CONFIG_ENABLE_FEATURE=y\n', encoding='ascii')
    for module in ('menuconfig', 'defconfig', 'kconfiglib'):
        monkeypatch.setitem(sys.modules, module, None)
    arguments = sys.argv

    assert cmd_menuconfig.cmd(menuconfig_args('--generate')) is True
    assert sys.argv is arguments
    assert '#define ENABLE_FEATURE\n' in (project / 'rtconfig.h').read_text(encoding='ascii')


def test_sdk_uses_public_frontend_and_restores_context(project, tmp_path, monkeypatch):
    sdk = tmp_path / 'tools' / 'scripts'
    sdk.mkdir(parents=True)
    (sdk / 'Kconfig').write_text(KCONFIG, encoding='ascii')
    monkeypatch.setenv('HOSTOS', 'original-host')
    arguments = sys.argv

    def frontend(kconf):
        assert Path.cwd() == sdk
        assert vars.env_vars['bsp_root'] == str(sdk)
        assert os.environ['HOSTOS'] == cmd_sdk.platform.system()
        assert sys.argv is arguments
        save_configuration(kconf)

    monkeypatch.setattr(menuconfig, 'menuconfig', frontend)
    monkeypatch.setattr(cmd_package, 'package_update', lambda: True)
    monkeypatch.setattr(cmd_package, 'get_packages', lambda: [{'name': 'demo', 'ver': '1.0'}])
    assert cmd_sdk.cmd(argparse.Namespace()) is True
    assert Path.cwd() == project
    assert vars.env_vars['bsp_root'] == str(project)
    assert os.environ['HOSTOS'] == 'original-host'
    assert sys.argv is arguments
    assert json.loads((sdk / 'sdk_list.json').read_text(encoding='ascii')) == [
        {'name': 'demo', 'path': 'demo-1.0'},
    ]


@pytest.mark.parametrize('previous_host', (None, 'original-host'))
def test_sdk_restores_context_on_frontend_failure(project, tmp_path, monkeypatch, previous_host):
    sdk = tmp_path / 'tools' / 'scripts'
    sdk.mkdir(parents=True)
    (sdk / 'Kconfig').write_text(KCONFIG, encoding='ascii')
    if previous_host is None:
        monkeypatch.delenv('HOSTOS', raising=False)
    else:
        monkeypatch.setenv('HOSTOS', previous_host)
    arguments = sys.argv

    def frontend(kconf):
        raise RuntimeError('frontend failed')

    monkeypatch.setattr(menuconfig, 'menuconfig', frontend)
    with pytest.raises(RuntimeError, match='frontend failed'):
        cmd_sdk.cmd(argparse.Namespace())
    assert Path.cwd() == project
    assert vars.env_vars['bsp_root'] == str(project)
    assert os.environ.get('HOSTOS') == previous_host
    assert sys.argv is arguments
    assert not (sdk / 'sdk_list.json').exists()


def test_ebuild_menuconfig_uses_public_frontend(project, monkeypatch):
    manager = KconfigManager(str(project), str(project / 'proj_config.h'))
    arguments = sys.argv

    def frontend(kconf):
        assert sys.argv is arguments
        save_configuration(kconf)

    monkeypatch.setattr(menuconfig, 'menuconfig', frontend)
    manager.menuconfig()
    assert sys.argv is arguments
    assert (project / '.config.old').read_bytes() == (project / '.config').read_bytes()
    header = (project / 'proj_config.h').read_text(encoding='ascii')
    assert '#define PROJ_CONFIG_H__\n' in header
    assert '#define ENABLE_FEATURE\n' in header
    assert not (project / 'rtconfig.h').exists()


def test_ebuild_defconfig_needs_no_terminal_frontend(project, monkeypatch):
    (project / '.config').write_text('CONFIG_ENABLE_FEATURE=y\n', encoding='ascii')
    monkeypatch.setitem(sys.modules, 'menuconfig', None)
    monkeypatch.setitem(sys.modules, 'defconfig', None)
    manager = KconfigManager(str(project), str(project / 'proj_config.h'))
    arguments = sys.argv

    manager.defconfig()
    assert sys.argv is arguments
    assert 'CONFIG_FEATURE_VALUE="fallback"\n' in (project / '.config').read_text(encoding='ascii')
    header = (project / 'proj_config.h').read_text(encoding='ascii')
    assert '#define PROJ_CONFIG_H__\n' in header
    assert '#define FEATURE_VALUE "fallback"\n' in header

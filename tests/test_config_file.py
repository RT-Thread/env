import pytest

import kconfig
from config_file import find_setting, iter_settings, read_config, write_header
from cmds import cmd_menuconfig
from cmds.cmd_package import cmd_package_utils
from ebuild.kconfig import KconfigManager


CONFIG = '''#
# Feature settings
#
CONFIG_FEATURE=y
# CONFIG_DISABLED is not set
CONFIG_MESSAGE="first=second"
CONFIG_COUNT=3
#
CONFIG_PKG_DEMO_VER="v1.0"
CONFIG_PKG_DEMO_PATH="/packages/demo"
CONFIG_PKG_USING_DEMO=y
'''


@pytest.fixture
def config_file(tmp_path):
    filename = tmp_path / '.config'
    filename.write_text(CONFIG, encoding='ascii')
    return filename


def test_read_settings_preserves_comments_and_full_values(config_file):
    lines = read_config(config_file)
    assert lines[:3] == ['#', '# Feature settings', '#']
    assert dict(iter_settings(lines))['CONFIG_MESSAGE'] == '"first=second"'
    assert find_setting(lines, 'CONFIG_DISABLED') is None
    assert find_setting(lines, 'CONFIG_UNKNOWN', 'fallback') == 'fallback'


def test_lookup_preserves_first_definition_and_empty_values(tmp_path):
    filename = tmp_path / '.config'
    filename.write_text(' CONFIG_VALUE=first\nCONFIG_VALUE=second\nCONFIG_EMPTY=\n', encoding='ascii')
    assert cmd_package_utils.find_string_in_config(filename, 'VALUE') == (True, 'first')
    assert cmd_package_utils.find_string_in_config(filename, 'EMPTY') == (True, '')


def test_legacy_macro_helpers_share_configuration_reader(config_file):
    assert cmd_package_utils.find_bool_macro_in_config(config_file, 'FEATURE')
    assert not cmd_package_utils.find_bool_macro_in_config(config_file, 'DISABLED')
    assert cmd_package_utils.find_string_macro_in_config(config_file, 'MESSAGE') == 'first=second'
    assert cmd_package_utils.find_string_macro_in_config(config_file, 'UNKNOWN') is None


def test_package_metadata_keeps_order_and_ignores_enable_symbols(tmp_path):
    filename = tmp_path / '.config'
    filename.write_text(
        'CONFIG_PKG_FIRST_VER="1=2"\nCONFIG_PKG_USING_FAKE_PATH="ignored"\n'
        'CONFIG_PKG_SECOND_PATH="/packages/second"\nCONFIG_PKG_FIRST_PATH="/packages/first"\n'
        'CONFIG_PKG_FIRST_VER="1.0"\nCONFIG_PKG_SECOND_VER="latest"\n', encoding='ascii',
    )
    assert kconfig.parse(filename) == [
        {'name': 'FIRST', 'ver': '1.0', 'path': '/packages/first'},
        {'name': 'SECOND', 'path': '/packages/second', 'ver': 'latest'},
    ]


def test_legacy_package_field_helpers_are_retained():
    packages = []
    kconfig.pkgs_ver(packages, 'DEMO', '1.0')
    kconfig.pkgs_path(packages, 'DEMO', '/packages/demo')
    kconfig.pkgs_ver(packages, 'DEMO', '2.0')
    assert packages == [{'name': 'DEMO', 'ver': '2.0', 'path': '/packages/demo'}]


def test_header_format_and_metadata_filter_are_preserved(config_file, tmp_path):
    header = tmp_path / 'generated.h'
    write_header(read_config(config_file), header, 'TEST_CONFIG_H__', ['project.h'])
    assert header.read_text(encoding='ascii') == (
        '#ifndef TEST_CONFIG_H__\n#define TEST_CONFIG_H__\n\n'
        '/* Feature settings */\n\n#define FEATURE\n#define MESSAGE "first=second"\n'
        '#define COUNT 3\n\n#define PKG_USING_DEMO\n#include "project.h"\n\n#endif\n'
    )


def test_rtconfig_target_and_project_include_are_preserved(config_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with config_file.open('a', encoding='ascii') as output:
        output.write('CONFIG_TARGET_FILE="custom.h"\n')
    (tmp_path / 'rtconfig_project.h').write_text('/* custom */\n', encoding='ascii')
    assert cmd_menuconfig.get_target_file(config_file) == 'custom.h'
    assert cmd_menuconfig.mk_rtconfig(config_file)
    header = (tmp_path / 'custom.h').read_text(encoding='ascii')
    assert '#define RT_CONFIG_H__\n' in header
    assert '#include "rtconfig_project.h"\n' in header
    assert not (tmp_path / 'rtconfig.h').exists()


def test_disabled_target_writes_no_header(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    filename = tmp_path / '.config'
    filename.write_text('CONFIG_TARGET_FILE=""\nCONFIG_FEATURE=y\n', encoding='ascii')
    assert cmd_menuconfig.get_target_file(filename) is None
    assert cmd_menuconfig.mk_rtconfig(filename)
    assert not list(tmp_path.glob('*.h'))


def test_ebuild_keeps_its_guard_and_has_no_rtconfig_include(config_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'rtconfig_project.h').write_text('/* custom */\n', encoding='ascii')
    header = tmp_path / 'proj_config.h'
    KconfigManager(str(tmp_path), str(header))._mk_proj_config(str(config_file))
    contents = header.read_text(encoding='ascii')
    assert '#define PROJ_CONFIG_H__\n' in contents
    assert '#include' not in contents
    assert '#define MESSAGE "first=second"\n' in contents


def test_missing_config_keeps_legacy_failure_conventions(tmp_path):
    filename = tmp_path / 'missing'
    assert kconfig.parse(filename) == []
    assert cmd_package_utils.find_string_in_config(filename, 'VALUE') == (False, None)
    assert cmd_menuconfig.get_target_file(filename) is None
    assert cmd_menuconfig.mk_rtconfig(filename) is False

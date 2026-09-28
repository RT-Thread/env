import os
import subprocess
import sys
from pathlib import Path


ENV_SCRIPT = Path(__file__).resolve().parents[1] / 'env.py'


def test_env_commands_from_unicode_bsp_path(tmp_path):
    bsp_root = tmp_path / '中文 project'
    include = bsp_root / 'rt-thread' / 'include'
    include.mkdir(parents=True)
    (include / 'rtdef.h').write_text(
        '#define RT_VERSION_MAJOR 5\n#define RT_VERSION_MINOR 2\n#define RT_VERSION_PATCH 0\n', encoding='ascii'
    )
    (bsp_root / 'Kconfig').write_text('mainmenu "Test"\n', encoding='ascii')
    (bsp_root / '.config').write_text('CONFIG_TEST_OPTION=y\n', encoding='ascii')

    environment = os.environ.copy()
    environment['PYTHONIOENCODING'] = 'utf-8'

    info = subprocess.run(
        [sys.executable, str(ENV_SCRIPT), '--info'],
        cwd=bsp_root,
        env=environment,
        capture_output=True,
        text=True,
        encoding='utf-8',
        timeout=20,
    )
    assert info.returncode == 0, info.stderr or info.stdout
    assert 'BSP_ROOT : %s' % bsp_root in info.stdout
    assert 'RTT_ROOT : %s' % (bsp_root / 'rt-thread') in info.stdout

    packages = subprocess.run(
        [sys.executable, str(ENV_SCRIPT), 'package', '--list'],
        cwd=bsp_root,
        env=environment,
        capture_output=True,
        text=True,
        encoding='utf-8',
        timeout=20,
    )
    assert packages.returncode == 0, packages.stderr or packages.stdout
    assert 'Packages list is empty.' in packages.stdout

    generated = subprocess.run(
        [sys.executable, str(ENV_SCRIPT), 'menuconfig', '--generate'],
        cwd=bsp_root,
        env=environment,
        capture_output=True,
        text=True,
        encoding='utf-8',
        timeout=20,
    )
    assert generated.returncode == 0, generated.stderr or generated.stdout
    assert '#define TEST_OPTION' in (bsp_root / 'rtconfig.h').read_text(encoding='ascii')

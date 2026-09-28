import os
import subprocess
from unittest import mock

import pytest

from file_context_menu import FileContextMenuManager


@pytest.mark.skipif(os.name != 'nt', reason='requires Windows PowerShell')
def test_windows_helper_only_starts_env_in_an_existing_directory(tmp_path):
    manager = FileContextMenuManager(str(tmp_path), platform_name='Windows')
    with mock.patch.object(manager, '_windows_module', return_value=mock.MagicMock()):
        manager._install_windows()

    helper = manager.windows_helper
    with open(os.path.join(os.path.dirname(helper), 'env.ps1'), 'w', encoding='ascii') as output:
        output.write("Write-Output 'ENV_STARTED'\n")

    valid = tmp_path / 'test space'
    valid.mkdir()
    invalid_file = tmp_path / 'not-a-directory.txt'
    invalid_file.write_text('', encoding='ascii')

    def launch(target):
        return subprocess.run(
            ['powershell.exe', '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', helper, str(target)],
            capture_output=True,
            text=True,
            errors='replace',
            timeout=15,
        )

    started = launch(valid)
    assert started.returncode == 0, started.stderr
    assert 'ENV_STARTED' in started.stdout

    for target in (tmp_path / 'missing', tmp_path / 'missing' / 'child', invalid_file):
        failed = launch(target)
        assert failed.returncode != 0, str(target)
        assert 'ENV_STARTED' not in failed.stdout

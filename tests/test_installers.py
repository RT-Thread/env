import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest


REPOSITORY = Path(__file__).resolve().parents[1]
SHELL_INSTALLERS = (
    'install_ubuntu.sh',
    'install_suse.sh',
    'install_arch.sh',
    'install_macos.sh',
)
INSTALLERS = SHELL_INSTALLERS + ('install_windows.ps1',)
HOST_PYTHON_PACKAGES = frozenset((
    'pip', 'pip3', 'python-pip', 'python3-pip', 'scons',
    'requests', 'psutil', 'tqdm', 'kconfiglib', 'pyyaml',
    'python-requests', 'python-tqdm', 'python-kconfiglib',
))
FORBIDDEN_COMMANDS = frozenset(('pip', 'pip3', 'yay', 'pyocd', 'openocd'))


# Intercept package managers and downloads without changing the host system.
COMMAND_STUB = '''import json
import os
from pathlib import Path
import sys

name = Path(sys.argv[0]).name
arguments = sys.argv[1:]
with open(os.environ['ENV_TEST_COMMAND_LOG'], 'a', encoding='utf-8') as output:
    output.write(json.dumps({'command': name, 'arguments': arguments}) + '\\n')

if name == 'wget' and 'https://ipinfo.io/country' in arguments:
    country = os.environ['ENV_TEST_COUNTRY']
    print(country)
    sys.exit(0 if country else 1)
elif name in ('wget', 'curl'):
    option = '-O' if name == 'wget' else '-o'
    destination = Path(arguments[arguments.index(option) + 1])
    destination.write_text(
        '#!/usr/bin/env bash\\nprintf "%s\\\\n" "$PWD" > "$ENV_TEST_BOOTSTRAP_MARKER"\\n',
        encoding='utf-8',
    )
elif name in ('python', 'python3'):
    if arguments[0] != '--version':
        sys.exit('Unexpected host Python operation: %s' % arguments)
    print('Python 3.12.0')
elif name in ('pip', 'pip3', 'yay', 'pyocd', 'openocd'):
    sys.exit('Unexpected host package or debugger command: %s' % name)
'''


@pytest.mark.parametrize('filename', INSTALLERS)
def test_installers_do_not_manage_host_python_packages(filename):
    source = (REPOSITORY / filename).read_text(encoding='utf-8')
    assert not re.search(r'\b(?:pip3?|ensurepip)\b', source)
    assert not re.search(r'\bpython-(?:requests|tqdm|kconfiglib)\b', source)


@pytest.mark.parametrize('filename', INSTALLERS)
def test_installers_do_not_bundle_debuggers(filename):
    source = (REPOSITORY / filename).read_text(encoding='utf-8')
    assert not re.search(r'\b(?:pyocd|openocd)\b', source, re.IGNORECASE)


def test_arch_installer_does_not_use_an_aur_meta_package():
    source = (REPOSITORY / 'install_arch.sh').read_text(encoding='utf-8')
    assert 'yay' not in source
    assert 'rt-thread-env-meta' not in source


def test_windows_installer_keeps_the_repository_bootstrap():
    source = (REPOSITORY / 'install_windows.ps1').read_text(encoding='utf-8')
    assert './touch_env.ps1' in source
    assert 'https://raw.githubusercontent.com/RT-Thread/env/master/touch_env.ps1' in source
    assert 'https://gitee.com/RT-Thread-Mirror/env/raw/master/touch_env.ps1' in source


@pytest.mark.skipif(os.name == 'nt', reason='POSIX shell test')
@pytest.mark.parametrize('filename', SHELL_INSTALLERS)
@pytest.mark.parametrize('country', ('US', 'CN', ''))
def test_shell_installers_prepare_system_tools_and_delegate_python_dependencies(tmp_path, filename, country):
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    stub = binaries / 'command_stub.py'
    stub.write_text('#!%s\n%s' % (sys.executable, COMMAND_STUB), encoding='utf-8')
    stub.chmod(0o755)
    for name in ('sudo', 'wget', 'curl', 'brew', 'python', 'python3') + tuple(FORBIDDEN_COMMANDS):
        (binaries / name).symlink_to(stub)

    workspace = tmp_path / 'installer workspace'
    workspace.mkdir()
    log = tmp_path / 'commands.jsonl'
    marker = tmp_path / 'bootstrap.txt'
    environment = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ.get('PATH', ''),
                       HOME=str(tmp_path), ENV_TEST_COMMAND_LOG=str(log),
                       ENV_TEST_BOOTSTRAP_MARKER=str(marker), ENV_TEST_COUNTRY=country)
    result = subprocess.run(
        ['bash', str(REPOSITORY / filename)], cwd=workspace, env=environment,
        input='', stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert marker.read_text(encoding='utf-8').strip() == str(workspace)
    assert not (workspace / 'touch_env.sh').exists()
    commands = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
    for command in commands:
        assert command['command'] not in FORBIDDEN_COMMANDS
        assert HOST_PYTHON_PACKAGES.isdisjoint(command['arguments'])

    if filename == 'install_macos.sh':
        downloader = next(command for command in commands if command['command'] == 'curl')
    else:
        downloader = next(command for command in commands
                          if command['command'] == 'wget' and '-O' in command['arguments'])
        if filename == 'install_arch.sh':
            system = next(command for command in commands if command['command'] == 'sudo')
        else:
            system = next(command for command in commands
                          if command['command'] == 'sudo' and 'install' in command['arguments'])
        assert 'git' in system['arguments']
        if filename == 'install_arch.sh':
            assert 'python' in system['arguments']
        else:
            assert 'python3' in system['arguments']
            assert 'python3-venv' in system['arguments']

    use_gitee = filename != 'install_macos.sh' and country == 'CN'
    expected_url = (
        'https://gitee.com/RT-Thread-Mirror/env/raw/master/touch_env.sh' if use_gitee
        else 'https://raw.githubusercontent.com/RT-Thread/env/master/touch_env.sh'
    )
    assert expected_url in downloader['arguments']

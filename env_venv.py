#!/usr/bin/env python3
"""Create and update the Python virtual environment used by Env."""

from __future__ import print_function

import argparse
import filecmp
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen


ALIYUN_INDEX_URL = 'https://mirrors.aliyun.com/pypi/simple/'
COUNTRY_URL = 'https://ipinfo.io/country'
STATE_FILENAME = '.rt-thread-env-state.json'
STATE_SCHEMA = 1

ROOT_RUNTIME_FILES = (
    'MANIFEST.in',
    'env.json',
    'env.ps1',
    'env.sh',
    'pyproject.toml',
    'setup.py',
)
ROOT_RUNTIME_SUFFIXES = ('.py',)
RUNTIME_DIRECTORIES = ('cmds', 'plugins')
EXCLUDED_DIRECTORY_NAMES = (
    '.git',
    '__pycache__',
    'build',
    'dist',
    'node_modules',
    'playwright-report',
    'test-results',
)
EXCLUDED_RUNTIME_PREFIXES = (
    ('plugins', 'examples'),
    ('plugins', 'tests'),
    ('plugins', 'webui', 'frontend'),
)
EXCLUDED_RUNTIME_SUFFIXES = ('.md', '.rst')


class BootstrapError(Exception):
    """Raised when the Env venv cannot be prepared safely."""


def _normalized(path):
    return Path(path).expanduser().resolve()


def _is_excluded(relative):
    parts = relative.parts
    if any(part in EXCLUDED_DIRECTORY_NAMES for part in parts):
        return True
    return any(parts[: len(prefix)] == prefix for prefix in EXCLUDED_RUNTIME_PREFIXES)


def iter_runtime_files(source_root):
    source_root = _normalized(source_root)
    files = set()

    for name in ROOT_RUNTIME_FILES:
        candidate = source_root / name
        if candidate.is_file():
            files.add(candidate)

    for candidate in source_root.iterdir():
        if candidate.is_file() and candidate.suffix in ROOT_RUNTIME_SUFFIXES:
            files.add(candidate)

    for directory_name in RUNTIME_DIRECTORIES:
        directory = source_root / directory_name
        if not directory.is_dir():
            continue
        for candidate in directory.rglob('*'):
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(source_root)
            if _is_excluded(relative) or candidate.suffix in EXCLUDED_RUNTIME_SUFFIXES + ('.pyc', '.pyo'):
                continue
            files.add(candidate)

    return sorted(files, key=lambda path: path.relative_to(source_root).as_posix())


def source_fingerprint(source_root):
    source_root = _normalized(source_root)
    files = iter_runtime_files(source_root)
    if not files:
        raise BootstrapError('no Env runtime source files were found in %s' % source_root)

    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(source_root).as_posix().encode('utf-8')
        digest.update(relative)
        digest.update(b'\0')
        with path.open('rb') as source:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        digest.update(b'\0')
    return digest.hexdigest()


def read_env_version(source_root):
    path = _normalized(source_root) / 'env.json'
    try:
        with path.open('r', encoding='utf-8') as source:
            value = json.load(source).get('version')
            return value or 'unknown'
    except (OSError, ValueError, TypeError):
        return 'unknown'


def venv_layout(venv_root, platform_name=None):
    venv_root = _normalized(venv_root)
    platform_name = platform_name or os.name
    if platform_name == 'nt':
        scripts = venv_root / 'Scripts'
        return {
            'python': scripts / 'python.exe',
            'activate': scripts / 'Activate.ps1',
            'rt_env': scripts / 'rt-env.exe',
        }
    scripts = venv_root / 'bin'
    return {
        'python': scripts / 'python',
        'activate': scripts / 'activate',
        'rt_env': scripts / 'rt-env',
    }


def venv_is_usable(layout):
    return layout['python'].is_file() and layout['activate'].is_file()


def env_is_installed(layout):
    return layout['rt_env'].is_file()


def read_state(venv_root):
    path = _normalized(venv_root) / STATE_FILENAME
    try:
        with path.open('r', encoding='utf-8') as source:
            value = json.load(source)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def write_state(venv_root, value):
    venv_root = _normalized(venv_root)
    descriptor, temporary_name = tempfile.mkstemp(prefix=STATE_FILENAME + '.', dir=str(venv_root))
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump(value, output, indent=2, sort_keys=True)
            output.write('\n')
        os.replace(str(temporary_path), str(venv_root / STATE_FILENAME))
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def default_activation_script(venv_root, platform_name=None):
    platform_name = platform_name or os.name
    filename = 'env.ps1' if platform_name == 'nt' else 'env.sh'
    return _normalized(venv_root).parent / filename


def activation_source(source_root, activation_target):
    return _normalized(source_root) / _normalized(activation_target).name


def activation_is_current(source_root, activation_target):
    source = activation_source(source_root, activation_target)
    target = _normalized(activation_target)
    if not source.is_file() or not target.is_file():
        return False
    try:
        if source.samefile(target):
            return True
    except OSError:
        pass
    return filecmp.cmp(str(source), str(target), shallow=False)


def sync_activation_script(source_root, activation_target):
    source = activation_source(source_root, activation_target)
    target = _normalized(activation_target)
    if not source.is_file():
        raise BootstrapError('activation source does not exist: %s' % source)
    try:
        if target.exists() and source.samefile(target):
            return
    except OSError:
        pass

    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=target.name + '.', dir=str(target.parent))
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        shutil.copy2(str(source), str(temporary_path))
        os.replace(str(temporary_path), str(target))
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def detect_country(timeout=3):
    request = Request(COUNTRY_URL, headers={'User-Agent': 'RT-Thread-Env/2'})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read(16).decode('ascii', 'ignore').strip().upper() or None
    except Exception:
        return None


def select_index_url(country_detector=None, environ=None):
    environ = environ if environ is not None else os.environ
    configured = environ.get('ENV_PYPI_INDEX_URL', '').strip()
    if configured:
        print('Using the configured Python package index.')
        return configured

    country_detector = country_detector or detect_country
    if country_detector() == 'CN':
        print('Detected a China Mainland IP; using the Alibaba Cloud PyPI mirror.')
        return ALIYUN_INDEX_URL
    return None


def confirm_upgrade(stdin=None):
    stdin = stdin or sys.stdin
    if not stdin.isatty():
        print('Env scripts changed, but this shell is not interactive; keeping the current venv installation.')
        print('Set ENV_VENV_AUTO_UPGRADE=1 to accept the upgrade non-interactively.')
        return False
    try:
        answer = input('Env scripts have changed. Upgrade the Python venv now? [y/N] ')
    except (EOFError, KeyboardInterrupt):
        print('')
        return False
    return answer.strip().lower() in ('y', 'yes')


def run_command(command):
    subprocess.check_call([str(value) for value in command])


def _index_arguments(index_url):
    return ['--index-url', index_url] if index_url else []


def _index_label(index_url):
    if not index_url:
        return 'default'
    if index_url == ALIYUN_INDEX_URL:
        return 'aliyun'
    return 'custom'


def install_env(layout, source_root, initial_install, index_url, command_runner=None):
    command_runner = command_runner or run_command
    python = str(layout['python'])
    command_runner([python, '-m', 'ensurepip', '--upgrade'])
    if initial_install:
        command_runner(
            [python, '-m', 'pip', 'install', '--disable-pip-version-check', '--upgrade']
            + _index_arguments(index_url)
            + ['pip']
        )
    command_runner(
        [
            python,
            '-m',
            'pip',
            'install',
            '--disable-pip-version-check',
            '--upgrade',
            '--upgrade-strategy',
            'only-if-needed',
        ]
        + _index_arguments(index_url)
        + [str(_normalized(source_root))]
    )


def _state_matches(state, source_root, fingerprint):
    if not state or state.get('schema') != STATE_SCHEMA:
        return False
    return state.get('source') == str(_normalized(source_root)) and state.get('fingerprint') == fingerprint


def mark_environment_current(venv_root, source_root, activation_target):
    venv_root = _normalized(venv_root)
    source_root = _normalized(source_root)
    activation_target = _normalized(activation_target)
    layout = venv_layout(venv_root)
    if not venv_is_usable(layout):
        raise BootstrapError('cannot mark an unusable Python venv as current: %s' % venv_root)
    if not env_is_installed(layout):
        raise BootstrapError('cannot mark the Python venv as current before Env is installed')

    fingerprint = source_fingerprint(source_root)
    sync_activation_script(source_root, activation_target)
    write_state(
        venv_root,
        {
            'schema': STATE_SCHEMA,
            'source': str(source_root),
            'fingerprint': fingerprint,
            'version': read_env_version(source_root),
            'index': 'existing',
        },
    )


def ensure_environment(
    venv_root,
    source_root,
    activation_target,
    assume_yes=False,
    command_runner=None,
    country_detector=None,
    confirmation=None,
):
    venv_root = _normalized(venv_root)
    source_root = _normalized(source_root)
    activation_target = _normalized(activation_target)
    layout = venv_layout(venv_root)
    initial_install = not venv_is_usable(layout)
    command_runner = command_runner or run_command

    if initial_install:
        print('Create Python venv for RT-Thread...')
        host_python = getattr(sys, '_base_executable', sys.executable)
        command_runner([host_python, '-m', 'venv', str(venv_root)])
        layout = venv_layout(venv_root)
        if not venv_is_usable(layout):
            raise BootstrapError('Python venv was created without a usable interpreter or activation script')

    fingerprint = source_fingerprint(source_root)
    state = read_state(venv_root)
    source_changed = not _state_matches(state, source_root, fingerprint)
    activation_changed = not activation_is_current(source_root, activation_target)
    package_missing = not env_is_installed(layout)
    upgrade_required = source_changed or activation_changed

    if not initial_install and not package_missing and upgrade_required and not assume_yes:
        confirmation = confirmation or confirm_upgrade
        if not confirmation():
            return 'declined'

    if not initial_install and not package_missing and not upgrade_required:
        return 'current'

    index_url = select_index_url(country_detector=country_detector)
    install_env(layout, source_root, initial_install, index_url, command_runner=command_runner)
    if not env_is_installed(layout):
        raise BootstrapError('local Env package installation did not create the rt-env command')
    sync_activation_script(source_root, activation_target)
    write_state(
        venv_root,
        {
            'schema': STATE_SCHEMA,
            'source': str(source_root),
            'fingerprint': fingerprint,
            'version': read_env_version(source_root),
            'index': _index_label(index_url),
        },
    )

    if initial_install:
        return 'created'
    if package_missing:
        return 'repaired'
    return 'upgraded'


def _env_flag(name):
    return os.environ.get(name, '').strip().lower() in ('1', 'true', 'yes', 'on')


def create_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--venv', required=True, help='Env Python virtual-environment directory')
    parser.add_argument(
        '--source',
        help='local Env tools/scripts source directory (default: directory containing this helper)',
    )
    parser.add_argument(
        '--activation-script',
        help='activation-script copy used by the shell (default: env.sh or env.ps1 beside the venv)',
    )
    parser.add_argument('--yes', action='store_true', help='accept a pending local-source upgrade')
    parser.add_argument(
        '--mark-current',
        action='store_true',
        help='record an installation completed by a legacy activation script',
    )
    return parser


def main(argv=None):
    args = create_parser().parse_args(argv)
    source_root = args.source or Path(__file__).resolve().parent
    activation_target = args.activation_script or default_activation_script(args.venv)
    try:
        if args.mark_current:
            mark_environment_current(args.venv, source_root, activation_target)
            return 0
        status = ensure_environment(
            args.venv,
            source_root,
            activation_target,
            assume_yes=args.yes or _env_flag('ENV_VENV_AUTO_UPGRADE'),
        )
        if status == 'upgraded':
            print('Env Python venv upgraded from the current local scripts.')
        elif status == 'repaired':
            print('Env package installation repaired in the existing Python venv.')
        return 0
    except (BootstrapError, OSError, subprocess.CalledProcessError) as exc:
        print('Failed to prepare the Env Python venv: %s' % exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

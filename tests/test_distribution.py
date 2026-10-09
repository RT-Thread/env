from email.parser import Parser
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile

import pytest


REPOSITORY = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def distribution(tmp_path_factory):
    pytest.importorskip('setuptools')
    pytest.importorskip('wheel')
    root = tmp_path_factory.mktemp('distribution')
    source = root / 'source'
    shutil.copytree(
        REPOSITORY, source,
        ignore=shutil.ignore_patterns(
            '.git', 'build', '*.egg-info', '__pycache__', 'node_modules', '.pytest_cache',
            'playwright-report', 'test-results', 'packages', '.venv',
        ),
    )
    for filename in ('sdk_cfg.json', 'sdk_list.json', 'unexpected.json'):
        (source / filename).write_text('{}\n', encoding='ascii')
    (source / 'kconfig-mconf.zip').write_bytes(b'obsolete resource')
    wheels = root / 'wheels'
    environment = dict(os.environ, PIP_DISABLE_PIP_VERSION_CHECK='1')
    result = subprocess.run(
        [sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
         '--wheel-dir', str(wheels), str(source)],
        cwd=root, env=environment, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheel = next(wheels.glob('*.whl'))
    return root, source, wheel, environment


def test_wheel_contains_runtime_resources_but_no_local_state_or_examples(distribution):
    _, _, wheel, _ = distribution
    with zipfile.ZipFile(wheel) as package:
        names = set(package.namelist())
        metadata_path = next(name for name in names if name.endswith('.dist-info/METADATA'))
        metadata = Parser().parsestr(package.read(metadata_path).decode('utf-8'))
    for name in ('env.json', 'Kconfig', 'cmds/Kconfig', 'config_file.py', 'env_paths.py', 'pkgsdb.py', 'statistics.py'):
        assert 'env/' + name in names
    for name in ('sdk_cfg.json', 'sdk_list.json', 'unexpected.json', 'kconfig-mconf.zip', 'touch_env.py'):
        assert 'env/' + name not in names
    assert not any(name.startswith('env/plugins/examples/') for name in names)
    assert any(name.startswith('env/plugins/bundled/epack/dist/') and name.endswith('.epack') for name in names)
    assert 'env/plugins/webui/static/index.html' in names
    assert 'env/plugins/spec/manifest-v1.schema.json' in names
    assert not any(value.startswith('psutil') for value in metadata.get_all('Requires-Dist', []))


def test_installed_wheel_supports_direct_imports_and_cli_without_source_tree(distribution):
    root, _, wheel, environment = distribution
    installed = root / 'installed'
    result = subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '--no-deps', '--no-compile', '--target', str(installed), str(wheel)],
        cwd=root, env=environment, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    environment = dict(environment, PYTHONPATH=str(installed), ENV_ROOT=str(root / 'env-root'))
    result = subprocess.run(
        [sys.executable, '-c', 'import env.sdk_manager, env.info, env.plugins.webui.server; '
         'from env.env import main; raise SystemExit(main(["pkg"]))'],
        cwd=root, env=environment, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'usage: rt-env pkg' in result.stdout


def test_source_distribution_retains_development_examples(distribution):
    root, source, _, environment = distribution
    result = subprocess.run(
        [sys.executable, 'setup.py', 'sdist', '--dist-dir', str(root / 'sdist')],
        cwd=source, env=environment, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    filename = next((root / 'sdist').glob('*.tar.gz'))
    with tarfile.open(filename) as package:
        names = package.getnames()
    assert any('/plugins/examples/hello-1.0.0/manifest.json' in name for name in names)

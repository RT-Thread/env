import hashlib
import io
import os
import sqlite3
import tarfile
import zipfile

import pytest

import archive
import vars


FILES = {'original/README.txt': b'package contents\n', 'original/nested/config.txt': b'feature=true\n'}


@pytest.fixture(params=('zip', 'tar.gz', 'tar.bz2', 'tar.xz'))
def package_archive(tmp_path, request):
    filename = tmp_path / ('demo.' + request.param)
    if request.param == 'zip':
        with zipfile.ZipFile(filename, 'w') as output:
            for name, content in FILES.items():
                output.writestr(name, content)
    else:
        with tarfile.open(filename, 'w:' + request.param.split('.')[-1]) as output:
            for name, content in FILES.items():
                member = tarfile.TarInfo(name)
                member.size = len(content)
                output.addfile(member, io.BytesIO(content))
    return filename


@pytest.fixture
def package_database(tmp_path, monkeypatch):
    packages = tmp_path / 'packages'
    packages.mkdir()
    database = packages / 'packages.dbsqlite'
    with sqlite3.connect(str(database)) as connection:
        connection.execute('CREATE TABLE packagefile (pathname TEXT, package TEXT, md5 TEXT)')
    monkeypatch.setitem(vars.env_vars, 'dbsqlite_pathname', str(database))
    monkeypatch.setitem(vars.env_vars, 'bsp_root', str(tmp_path))
    return packages, database


def test_archive_installation_keeps_per_file_database_records(package_archive, package_database):
    packages, database = package_database
    assert archive.package_integrity_test(str(package_archive))
    assert archive.unpack(str(package_archive), str(packages), {'ver': '1.0'}, 'demo')
    expected_records = []
    for name, content in FILES.items():
        relative = os.path.normpath(name.replace('original', 'demo-1.0', 1))
        assert (packages / relative).read_bytes() == content
        expected_records.append((relative, package_archive.name, hashlib.md5(content).hexdigest()))
    with sqlite3.connect(str(database)) as connection:
        records = connection.execute('SELECT pathname, package, md5 FROM packagefile ORDER BY pathname').fetchall()
    assert records == sorted(expected_records)
    assert not (packages / 'package_temp').exists()
    assert package_archive.exists()


def test_archive_failure_closes_handle_and_cleans_temporary_files(
    package_archive, package_database, monkeypatch,
):
    packages, _ = package_database
    opened = []
    is_zip = package_archive.suffix == '.zip'
    opener = archive.zipfile.ZipFile if is_zip else archive.tarfile.open

    def tracked_opener(*args, **kwargs):
        result = opener(*args, **kwargs)
        opened.append(result)
        return result

    def failed_record(*args):
        raise OSError('database failure')

    monkeypatch.setattr(archive.pkgsdb, 'save_to_database', failed_record)
    result = archive._handle_package(
        str(package_archive), str(packages), 'demo', {'ver': '1.0'}, tracked_opener,
    )
    assert result is False
    assert len(opened) == 1
    assert opened[0].fp is None if is_zip else opened[0].closed
    assert not (packages / 'package_temp').exists()
    assert not (packages / 'demo-1.0').exists()
    assert not package_archive.exists()


def test_existing_installation_is_not_overwritten(package_archive, package_database):
    packages, _ = package_database
    destination = packages / 'demo-1.0'
    destination.mkdir()
    (destination / 'README.txt').write_text('user modifications\n', encoding='ascii')
    assert archive.unpack(str(package_archive), str(packages), {'ver': '1.0'}, 'demo')
    assert (destination / 'README.txt').read_text(encoding='ascii') == 'user modifications\n'
    assert not (packages / 'package_temp').exists()


@pytest.mark.parametrize('suffix', ('.zip', '.tar.gz', '.tar.bz2', '.tar.xz'))
def test_invalid_archive_is_rejected_without_an_unbound_handle(tmp_path, suffix):
    filename = tmp_path / ('invalid' + suffix)
    filename.write_bytes(b'not an archive')
    assert archive.package_integrity_test(str(filename)) is False


def test_integrity_test_handles_zip_open_failure(tmp_path, monkeypatch):
    filename = tmp_path / 'demo.zip'
    filename.touch()
    monkeypatch.setattr(archive.zipfile, 'is_zipfile', lambda path: True)

    def failed_open(*args):
        raise OSError('open failed')

    monkeypatch.setattr(archive.zipfile, 'ZipFile', failed_open)
    assert archive.package_integrity_test(str(filename)) is False

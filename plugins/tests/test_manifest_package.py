import io
import json
import os
import tempfile
import unittest
import warnings
import zipfile

from plugins.compatibility import compare_versions, compatibility_issues, python_abi, version_satisfies
from plugins.errors import IntegrityError, ManifestError, PackageError
from plugins.manifest import parse_manifest, validate_manifest
from plugins.package import EpackArchive, canonical_json, write_integrity
from plugins.tests.helpers import EXAMPLES, build_example, rewrite_zip


class ManifestTest(unittest.TestCase):
    def setUp(self):
        path = os.path.join(EXAMPLES, 'hello-1.0.0', 'manifest.json')
        with open(path, 'rb') as source:
            self.content = source.read()

    def test_valid_manifest(self):
        manifest = parse_manifest(self.content)
        self.assertEqual(manifest.plugin_id, 'org.rt-thread.examples.hello')
        self.assertEqual(manifest.commands[0]['name'], 'env-plugin-hello')

    def test_duplicate_json_key_is_rejected(self):
        content = self.content.replace(b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1')
        with self.assertRaisesRegex(ManifestError, 'duplicate JSON key'):
            parse_manifest(content)

    def test_unknown_field_is_rejected(self):
        data = json.loads(self.content.decode('utf-8'))
        data['future'] = True
        with self.assertRaisesRegex(ManifestError, 'unknown fields'):
            validate_manifest(data)

    def test_pyc_wheel_requires_matching_filename_tag(self):
        data = json.loads(self.content.decode('utf-8'))
        data['backend']['artifacts'][0]['format'] = 'pyc-wheel'
        data['compatibility']['abis'] = [python_abi()]
        with self.assertRaisesRegex(ManifestError, 'filename'):
            validate_manifest(data)

    def test_version_constraints(self):
        self.assertTrue(version_satisfies('v2.0.2', '>=2.0.0,<3.0.0'))
        self.assertFalse(version_satisfies('3.0.0', '>=2.0.0,<3.0.0'))
        self.assertLess(compare_versions('1.1.0-beta.2', '1.1.0'), 0)
        self.assertGreater(compare_versions('1.1.0-beta.2', '1.1.0-beta.1'), 0)
        self.assertEqual(compare_versions('1.1.0+build.1', '1.1.0+build.2'), 0)

    def test_compatibility_reports_abi_and_platform(self):
        data = json.loads(self.content.decode('utf-8'))
        data['compatibility']['platforms'] = ['linux']
        data['compatibility']['architectures'] = ['x86_64']
        manifest = validate_manifest(data)
        issues = compatibility_issues(manifest, system='windows', architecture='mips', abi='cp27')
        self.assertIn('platform windows is not supported', issues)
        self.assertIn('architecture mips is not supported', issues)
        self.assertEqual(len(issues), 2, 'py3 source wheels should accept the current Python 3 ABI')


class PackageTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.package = build_example('1.0.0', self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_built_package_has_verified_inventory(self):
        archive = EpackArchive(self.package).inspect()
        self.assertEqual(archive.summary()['integrity'], 'verified')
        self.assertEqual(archive.summary()['signing_status'], 'unsigned')

    def test_tampered_file_is_rejected(self):
        target = os.path.join(self.temporary.name, 'tampered.epack')

        def tamper(files):
            wheel = next(name for name in files if name.endswith('.whl'))
            files[wheel] += b'tampered'
            return files

        rewrite_zip(self.package, target, tamper)
        with self.assertRaisesRegex(IntegrityError, 'SHA-256 mismatch'):
            EpackArchive(target).inspect()

    def test_unlisted_file_is_rejected(self):
        target = os.path.join(self.temporary.name, 'extra.epack')

        def add_file(files):
            files['unexpected.txt'] = b'not listed'
            return files

        rewrite_zip(self.package, target, add_file)
        with self.assertRaisesRegex(IntegrityError, 'not listed'):
            EpackArchive(target).inspect()

    def test_path_traversal_is_rejected(self):
        target = os.path.join(self.temporary.name, 'traversal.epack')
        with zipfile.ZipFile(target, 'w') as archive:
            archive.writestr('../outside', b'bad')
        with self.assertRaisesRegex(PackageError, 'unsafe'):
            EpackArchive(target).inspect()

    def test_duplicate_member_is_rejected(self):
        target = os.path.join(self.temporary.name, 'duplicate.epack')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(target, 'w') as archive:
                archive.writestr('manifest.json', b'{}')
                archive.writestr('manifest.json', b'{}')
        with self.assertRaisesRegex(PackageError, 'duplicate'):
            EpackArchive(target).inspect()

    def test_case_colliding_member_is_rejected(self):
        target = os.path.join(self.temporary.name, 'case-collision.epack')
        with zipfile.ZipFile(target, 'w') as archive:
            archive.writestr('Manifest.json', b'{}')
            archive.writestr('manifest.json', b'{}')
        with self.assertRaisesRegex(PackageError, 'duplicate'):
            EpackArchive(target).inspect()

    def test_windows_device_member_is_rejected(self):
        target = os.path.join(self.temporary.name, 'device.epack')
        with zipfile.ZipFile(target, 'w') as archive:
            archive.writestr('backend/NUL.txt', b'bad')
        with self.assertRaisesRegex(PackageError, 'unsafe'):
            EpackArchive(target).inspect()

    def test_symbolic_link_is_rejected(self):
        target = os.path.join(self.temporary.name, 'link.epack')
        info = zipfile.ZipInfo('manifest.json')
        info.create_system = 3
        info.external_attr = (0o120777 & 0xFFFF) << 16
        with zipfile.ZipFile(target, 'w') as archive:
            archive.writestr(info, b'target')
        with self.assertRaisesRegex(PackageError, 'Symbolic|symbolic'):
            EpackArchive(target).inspect()

    def test_pyc_wheel_contains_no_author_source(self):
        package = build_example('1.1.0', self.temporary.name, backend_format='pyc-wheel')
        with zipfile.ZipFile(package, 'r') as archive:
            wheel_name = next(name for name in archive.namelist() if name.endswith('.whl'))
            wheel_content = archive.read(wheel_name)
        with zipfile.ZipFile(io.BytesIO(wheel_content), 'r') as wheel:
            author_sources = [name for name in wheel.namelist() if name.endswith('.py') and '.dist-info/' not in name]
            bytecode = [name for name in wheel.namelist() if name.endswith('.pyc')]
        self.assertEqual(author_sources, [])
        self.assertTrue(bytecode)

    def test_unverifiable_signature_material_is_rejected(self):
        target = os.path.join(self.temporary.name, 'signed.epack')

        def add_signature(files):
            files['security/signature.json'] = b'{}'
            payload = dict((name, content) for name, content in files.items() if name != 'integrity.json')
            files['integrity.json'] = canonical_json(write_integrity(payload))
            return files

        rewrite_zip(self.package, target, add_signature)
        with self.assertRaisesRegex(PackageError, 'does not support verifiable signatures'):
            EpackArchive(target).inspect()


if __name__ == '__main__':
    unittest.main()

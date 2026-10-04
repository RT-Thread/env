import os
import tempfile
import unittest
from unittest import mock

from plugins.errors import UsageError
from plugins.webui.documents import DocumentNotFound, WorkspaceDocuments


class WorkspaceDocumentsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = self.temporary.name
        self.documents = WorkspaceDocuments(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, relative, content):
        path = os.path.join(self.root, *relative.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as output:
            output.write(content)
        return path

    def test_home_document_prefers_index_and_falls_back_to_readme(self):
        self.assertIsNone(self.documents.home_path())
        self.assertIsNone(self.documents.read())
        self.write('README.md', b'# Readme')
        self.assertEqual(self.documents.read()['path'], 'README.md')
        self.write('index.md', b'# Index')
        self.assertEqual(self.documents.read(), {'path': 'index.md', 'content': '# Index'})

    def test_nested_documents_allow_utf8_bom_and_refresh(self):
        self.write('docs/guide.md', b'\xef\xbb\xbf# Guide')
        self.assertEqual(self.documents.read('docs/guide.md')['content'], '# Guide')
        self.write('docs/guide.md', b'# Updated')
        self.assertEqual(self.documents.read('docs/guide.md')['content'], '# Updated')

    def test_images_preserve_bytes_and_use_expected_mime_types(self):
        for extension, mime in (('svg', 'image/svg+xml'), ('png', 'image/png'), ('jpeg', 'image/jpeg')):
            with self.subTest(extension=extension):
                relative = 'images/diagram.' + extension
                self.write(relative, b'asset')
                self.assertEqual(self.documents.image(relative), (b'asset', mime))

    def test_missing_document_has_a_distinct_error(self):
        with self.assertRaises(DocumentNotFound):
            self.documents.read('missing.md')

    def test_unsafe_or_unsupported_resources_are_rejected(self):
        for relative in ('../outside.md', '/README.md', 'docs//guide.md', 'docs/./guide.md',
                         '.private/notes.md', 'docs\\guide.md', 'C:guide.md', 'index.md\x00', 'env.py'):
            with self.subTest(relative=relative), self.assertRaises(UsageError):
                self.documents.read(relative)
        self.write('index.html', b'<script>alert(1)</script>')
        with self.assertRaises(UsageError):
            self.documents.image('index.html')

    def test_symlinks_cannot_escape_or_disguise_hidden_or_unsupported_files(self):
        if not hasattr(os, 'symlink'):
            self.skipTest('symlinks are unavailable')
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        for name, target in (
            ('outside.md', os.path.join(outside.name, 'notes.md')),
            ('hidden.md', self.write('.private/notes.md', b'secret')),
            ('source.md', self.write('env.py', b'code')),
        ):
            try:
                os.symlink(target, os.path.join(self.root, name))
            except OSError:
                self.skipTest('symlink creation is unavailable')
            with self.subTest(name=name), self.assertRaises(UsageError):
                self.documents.read(name)

    def test_unsafe_home_candidate_does_not_hide_safe_readme(self):
        self.write('README.md', b'# Safe')
        os.makedirs(os.path.join(self.root, 'index.md'))
        self.assertEqual(self.documents.home_path(), 'README.md')

    def test_invalid_encoding_and_size_limits_are_reported(self):
        self.write('invalid.md', b'\xff')
        with self.assertRaisesRegex(UsageError, 'UTF-8'):
            self.documents.read('invalid.md')
        self.write('large.md', b'12345')
        self.write('large.svg', b'12345')
        with mock.patch('plugins.webui.documents.DOCUMENT_LIMIT', 4), self.assertRaisesRegex(UsageError, 'size limit'):
            self.documents.read('large.md')
        with mock.patch('plugins.webui.documents.IMAGE_LIMIT', 4), self.assertRaisesRegex(UsageError, 'size limit'):
            self.documents.image('large.svg')


if __name__ == '__main__':
    unittest.main()

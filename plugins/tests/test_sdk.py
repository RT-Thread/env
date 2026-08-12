import os
import tempfile
import unittest

from plugins.errors import PermissionDenied, WorkspaceBoundaryError
from plugins.sdk import Workspace


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = self.temporary.name
        with open(os.path.join(self.root, 'input.txt'), 'w', encoding='utf-8') as output:
            output.write('input')

    def tearDown(self):
        self.temporary.cleanup()

    def test_read_and_atomic_write(self):
        workspace = Workspace(self.root, ['workspace.write'])
        self.assertEqual(workspace.read_text('input.txt'), 'input')
        workspace.write_text('output.txt', 'output')
        with open(os.path.join(self.root, 'output.txt'), 'r', encoding='utf-8') as source:
            self.assertEqual(source.read(), 'output')

    def test_missing_permission_is_rejected(self):
        workspace = Workspace(self.root, [])
        with self.assertRaises(PermissionDenied):
            workspace.read_text('input.txt')
        with self.assertRaises(PermissionDenied):
            workspace.write_text('output.txt', 'output')

    def test_parent_traversal_is_rejected(self):
        workspace = Workspace(self.root, ['workspace.read'])
        with self.assertRaises(WorkspaceBoundaryError):
            workspace.read_text('../outside.txt')

    def test_symlink_escape_is_rejected(self):
        if not hasattr(os, 'symlink'):
            self.skipTest('symbolic links are unavailable')
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        target = os.path.join(outside.name, 'secret.txt')
        with open(target, 'w', encoding='utf-8') as output:
            output.write('secret')
        try:
            os.symlink(outside.name, os.path.join(self.root, 'link'))
        except OSError as exc:
            self.skipTest('cannot create symbolic link: %s' % exc)
        workspace = Workspace(self.root, ['workspace.read'])
        with self.assertRaises(WorkspaceBoundaryError):
            workspace.read_text('link/secret.txt')

    def test_sensitive_files_are_rejected(self):
        workspace = Workspace(self.root, ['workspace.write'])
        with self.assertRaises(PermissionDenied):
            workspace.write_text('.env', 'TOKEN=secret')
        with self.assertRaises(PermissionDenied):
            workspace.write_text('private.key', 'secret')


if __name__ == '__main__':
    unittest.main()

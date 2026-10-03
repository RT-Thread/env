"""Read project documentation and images without exposing the whole workspace."""

import os

from ..errors import UsageError
from ..paths import path_is_within


DOCUMENT_LIMIT = 4 * 1024 * 1024
IMAGE_LIMIT = 16 * 1024 * 1024
HOME_DOCUMENTS = ('index.md', 'README.md', 'readme.md')
IMAGE_TYPES = {
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.avif': 'image/avif',
    '.bmp': 'image/bmp',
    '.ico': 'image/x-icon',
}


class DocumentNotFound(UsageError):
    pass


class WorkspaceDocuments(object):
    def __init__(self, workspace):
        self.root = os.path.realpath(workspace)

    def home_path(self):
        for relative in HOME_DOCUMENTS:
            try:
                self._resolve(relative, ('.md',))
                return relative
            except (UsageError, OSError):
                continue
        return None

    def read(self, relative=None):
        relative = self.home_path() if relative is None else relative
        if relative is None:
            return None
        target = self._resolve(relative, ('.md',))
        content = self._read(target, DOCUMENT_LIMIT)
        try:
            text = content.decode('utf-8-sig')
        except UnicodeError:
            raise UsageError('project Markdown must use UTF-8 encoding')
        return {'path': relative, 'content': text}

    def image(self, relative):
        target = self._resolve(relative, IMAGE_TYPES)
        content = self._read(target, IMAGE_LIMIT)
        return content, IMAGE_TYPES[os.path.splitext(target)[1].lower()]

    def _resolve(self, relative, extensions):
        if not isinstance(relative, str) or not relative or any(value in relative for value in ('\\', ':', '\x00')):
            raise UsageError('invalid project resource path')
        parts = relative.split('/')
        if any(not part or part.startswith('.') for part in parts):
            raise UsageError('project resource path cannot be absolute, hidden, or contain traversal')
        if os.path.splitext(relative)[1].lower() not in extensions:
            raise UsageError('unsupported project resource type')
        target = os.path.realpath(os.path.join(self.root, *parts))
        if not path_is_within(self.root, target):
            raise UsageError('project resource resolves outside the workspace')
        resolved_parts = os.path.relpath(target, self.root).split(os.sep)
        if any(part.startswith('.') for part in resolved_parts):
            raise UsageError('hidden project resources are not accessible')
        if os.path.splitext(target)[1].lower() not in extensions:
            raise UsageError('unsupported project resource target type')
        if not os.path.isfile(target):
            raise DocumentNotFound('project resource was not found')
        return target

    @staticmethod
    def _read(target, limit):
        with open(target, 'rb') as source:
            content = source.read(limit + 1)
        if len(content) > limit:
            raise UsageError('project resource exceeds size limit')
        return content

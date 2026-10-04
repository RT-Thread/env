import os
import tempfile
import unittest

from plugins.errors import ManifestError
from plugins.manifest import validate_manifest
from plugins.webui.requirements import evaluate_launch_requirements


class LaunchRequirementsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = self.temporary.name

    def tearDown(self):
        self.temporary.cleanup()

    def touch(self, relative):
        path = os.path.join(self.workspace, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as output:
            output.write('test\n')

    def base_manifest(self):
        return {
            'schema_version': 1,
            'id': 'org.example.requirements',
            'name': 'Requirements',
            'version': '1.0.0',
            'description': 'Requirements test plugin',
            'author': {'name': 'Env'},
            'license': {'spdx': 'Apache-2.0', 'file': 'licenses/LICENSE'},
            'compatibility': {
                'env': '>=2.0.2,<3.0.0',
                'python': '>=3.6.0,<4.0.0',
                'implementations': ['cpython'],
                'abis': ['py3'],
                'platforms': ['any'],
                'architectures': ['any'],
            },
            'permissions': [],
            'commands': [],
            'backend': {'artifacts': []},
            'webui': {
                'entry': 'frontend/index.html',
                'icon': 'puzzle',
                'frontend_sdk': '>=1.0.0,<2.0.0',
            },
        }

    def test_file_directory_glob_and_boolean_operators(self):
        os.makedirs(os.path.join(self.workspace, 'test_unit'))
        self.touch('test-report.md')
        self.touch('rtconfig.py')

        requirements = {
            'all': [
                {'type': 'file', 'pattern': 'rtconfig.py'},
                {
                    'any': [
                        {'type': 'directory', 'pattern': 'test_*'},
                        {'type': 'file', 'pattern': 'test_*.md'},
                    ]
                },
                {'not': {'type': 'file', 'pattern': 'missing.txt'}},
            ]
        }
        result = evaluate_launch_requirements(self.workspace, requirements)

        self.assertTrue(result['satisfied'])
        self.assertEqual(result['tree']['operator'], 'all')
        self.assertEqual(result['tree']['children'][0]['matches'], ['rtconfig.py'])
        self.assertEqual(result['tree']['children'][1]['operator'], 'any')

    def test_unsatisfied_requirement_reports_relative_matches(self):
        self.touch('docs/test-result.md')
        result = evaluate_launch_requirements(
            self.workspace,
            {'type': 'directory', 'pattern': 'test_*'},
        )

        self.assertFalse(result['satisfied'])
        self.assertEqual(result['tree']['matches'], [])
        self.assertIn('not found', result['message'])

    def test_manifest_accepts_nested_requirements(self):
        data = self.base_manifest()
        data['webui']['launch_requirements'] = {
            'all': [
                {'type': 'file', 'pattern': 'rtconfig.py'},
                {'any': [
                    {'type': 'directory', 'pattern': 'test_*'},
                    {'type': 'file', 'pattern': 'test_*.md'},
                ]},
            ]
        }

        manifest = validate_manifest(data)
        self.assertEqual(manifest.webui['launch_requirements']['all'][0]['type'], 'file')

    def test_manifest_rejects_unsafe_requirement_pattern(self):
        data = self.base_manifest()
        data['webui']['launch_requirements'] = {'type': 'file', 'pattern': '../rtconfig.py'}

        with self.assertRaisesRegex(ManifestError, 'pattern'):
            validate_manifest(data)


if __name__ == '__main__':
    unittest.main()

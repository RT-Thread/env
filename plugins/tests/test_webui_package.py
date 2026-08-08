import os
import tempfile
import unittest

from plugins.epack.builder import build_project
from plugins.errors import PackageError, StateError
from plugins.service import PluginService
from plugins.tests.helpers import EXAMPLES, copy_project, update_manifest


class WebUIPackageTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.packages = os.path.join(self.temporary.name, 'packages')
        self.env_root = os.path.join(self.temporary.name, 'env')
        self.launchers = os.path.join(self.temporary.name, 'launchers')
        os.makedirs(self.packages)

    def tearDown(self):
        self.temporary.cleanup()

    def test_webui_resources_are_built_installed_and_permission_guarded(self):
        package = build_project(os.path.join(EXAMPLES, 'build-insight-1.0.0'), self.packages)
        service = PluginService(env_root=self.env_root, launcher_dir=self.launchers)
        installed = service.install(package, allow_unsigned=True)
        self.assertEqual(installed['webui']['entry'], 'frontend/index.html')
        entry = service.resolve_webui_asset('org.rt-thread.build-insight')
        with open(entry, 'r', encoding='utf-8') as source:
            self.assertIn('Build Insight', source.read())
        service.set_permissions('org.rt-thread.build-insight', ['process.execute'])
        with self.assertRaisesRegex(StateError, 'required permissions'):
            service.resolve_webui_asset('org.rt-thread.build-insight')
        diagnosis = service.doctor('org.rt-thread.build-insight')
        self.assertEqual(diagnosis['status'], 'error')
        service.set_permissions('org.rt-thread.build-insight', ['workspace.read'])
        self.assertTrue(os.path.isfile(service.resolve_webui_asset('org.rt-thread.build-insight', 'styles.css')))

    def test_webui_only_plugin_needs_no_backend(self):
        project = copy_project(
            os.path.join(EXAMPLES, 'quality-gate-1.0.0'),
            os.path.join(self.temporary.name, 'quality'),
        )
        update_manifest(
            project,
            lambda data: data['compatibility'].update({'platforms': ['any'], 'architectures': ['any']}),
        )
        package = build_project(project, self.packages)
        service = PluginService(env_root=self.env_root, launcher_dir=self.launchers)
        result = service.install(package, allow_unsigned=True)
        self.assertEqual(result['commands'], [])
        self.assertIsNotNone(result['webui'])
        self.assertEqual(service.doctor(result['id'])['status'], 'ok')

    def test_frontend_source_map_is_rejected(self):
        project = copy_project(
            os.path.join(EXAMPLES, 'build-insight-1.0.0'),
            os.path.join(self.temporary.name, 'with-map'),
        )
        with open(os.path.join(project, 'frontend', 'plugin.js.map'), 'w', encoding='utf-8') as output:
            output.write('{}')
        with self.assertRaisesRegex(PackageError, 'debug files'):
            build_project(project, self.packages)

    def test_webui_asset_traversal_is_rejected(self):
        package = build_project(os.path.join(EXAMPLES, 'build-insight-1.0.0'), self.packages)
        service = PluginService(env_root=self.env_root, launcher_dir=self.launchers)
        service.install(package, allow_unsigned=True)
        with self.assertRaisesRegex(Exception, 'invalid WebUI asset path'):
            service.resolve_webui_asset('org.rt-thread.build-insight', '../manifest.json')


if __name__ == '__main__':
    unittest.main()

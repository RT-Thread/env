import json
import os
import subprocess
import sys
import tempfile
import unittest

from plugins.tests.helpers import build_example


REPOSITORY = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_SCRIPT = os.path.join(REPOSITORY, 'env.py')


class EnvPluginCliTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.env_root = os.path.join(self.temporary.name, 'env')
        self.launchers = os.path.join(self.temporary.name, 'launchers')
        self.packages = os.path.join(self.temporary.name, 'packages')
        os.makedirs(self.packages)
        self.v1 = build_example('1.0.0', self.packages)
        self.v2 = build_example('1.1.0', self.packages)
        self.environment = dict(os.environ)
        self.environment['ENV_PLUGIN_LAUNCHER_DIR'] = self.launchers
        self.environment.pop('ENV_PLUGIN_MARKET_URL', None)

    def tearDown(self):
        self.temporary.cleanup()

    def cli(self, *arguments):
        return subprocess.run(
            [sys.executable, ENV_SCRIPT, 'plugin', '--env-root', self.env_root] + list(arguments),
            cwd=REPOSITORY,
            env=self.environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

    def test_noninteractive_unsigned_install_requires_yes(self):
        result = self.cli('install', self.v1)
        self.assertEqual(result.returncode, 2)
        self.assertIn('interactive terminal or --yes', result.stderr)

    def test_cli_lifecycle_and_json_output(self):
        installed = self.cli('install', self.v1, '--yes', '--json')
        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertEqual(json.loads(installed.stdout)['version'], '1.0.0')
        upgraded = self.cli('update', self.v2, '--yes', '--json')
        self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
        self.assertEqual(json.loads(upgraded.stdout)['version'], '1.1.0')
        listed = self.cli('list', '--json')
        self.assertEqual(len(json.loads(listed.stdout)), 1)
        info = self.cli('info', 'org.rt-thread.examples.hello', '--json')
        self.assertEqual(json.loads(info.stdout)['version'], '1.1.0')
        doctor = self.cli('doctor', '--json')
        self.assertEqual(json.loads(doctor.stdout)['status'], 'ok')
        removed = self.cli('uninstall', 'org.rt-thread.examples.hello', '--yes', '--json')
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertTrue(json.loads(removed.stdout)['uninstalled'])

    def test_market_url_can_be_configured_and_cleared(self):
        missing = self.cli('market', '--json')
        self.assertEqual(missing.returncode, 0, missing.stderr)
        self.assertEqual(json.loads(missing.stdout)['enabled'], False)
        configured = self.cli('market', 'set', 'http://127.0.0.1:8800/', '--json')
        self.assertEqual(configured.returncode, 0, configured.stderr)
        payload = json.loads(configured.stdout)
        self.assertEqual(payload['url'], 'http://127.0.0.1:8800')
        self.assertEqual(payload['source'], 'file')
        shown = self.cli('market')
        self.assertIn('http://127.0.0.1:8800', shown.stdout)
        invalid = self.cli('market', 'set', 'ftp://example.invalid')
        self.assertEqual(invalid.returncode, 2)
        cleared = self.cli('market', 'clear', '--json')
        self.assertFalse(json.loads(cleared.stdout)['enabled'])


if __name__ == '__main__':
    unittest.main()

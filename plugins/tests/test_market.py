import os
import tempfile
import unittest

from plugins.errors import UsageError
from plugins.market import diagnose_market_plugin, load_market_config, normalize_market_url, save_market_url
from plugins.paths import PluginPaths


class MarketConfigTest(unittest.TestCase):
    def test_normalize_rejects_invalid_urls(self):
        self.assertEqual(normalize_market_url('http://127.0.0.1:8800/'), 'http://127.0.0.1:8800')
        self.assertEqual(
            normalize_market_url('https://market.example/plugins/'),
            'https://market.example/plugins',
        )
        for value in ('', 'ftp://example', 'http://user:pass@host', 'http://host?x=1', 'not-a-url'):
            with self.subTest(value=value):
                with self.assertRaises(UsageError):
                    normalize_market_url(value)

    def test_environment_overrides_file(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        paths = PluginPaths(env_root=temporary.name)
        save_market_url(paths, 'http://127.0.0.1:8800')
        from_file = load_market_config(paths, environ={})
        self.assertEqual(from_file['source'], 'file')
        from_env = load_market_config(paths, environ={'ENV_PLUGIN_MARKET_URL': 'https://market.example'})
        self.assertEqual(from_env['url'], 'https://market.example')
        self.assertEqual(from_env['source'], 'env')
        invalid = load_market_config(paths, environ={'ENV_PLUGIN_MARKET_URL': 'ftp://bad'})
        self.assertFalse(invalid['enabled'])
        missing = load_market_config(PluginPaths(env_root=os.path.join(temporary.name, 'empty')), environ={})
        self.assertFalse(missing['enabled'])


class MarketDiagnosisTest(unittest.TestCase):
    def test_explains_platform_mismatch(self):
        detail = {
            'id': 'org.example.windows',
            'status': 'published',
            'versions': [
                {
                    'version': '1.0.0',
                    'status': 'published',
                    'artifacts': [
                        {
                            'version': '1.0.0',
                            'filename': 'windows.epack',
                            'compatibility': {
                                'env': '>=2.0.2,<3.0.0',
                                'python': '>=3.6.0,<4.0.0',
                                'implementations': ['cpython'],
                                'abis': ['py3'],
                                'platforms': ['windows'],
                                'architectures': ['any'],
                            },
                        }
                    ],
                }
            ],
        }
        diagnosis = diagnose_market_plugin(
            detail,
            runtime={
                'env': '2.0.2',
                'python': '3.12.3',
                'implementation': 'cpython',
                'abi': 'py3',
                'platform': 'linux',
                'architecture': 'x86_64',
            },
        )
        self.assertEqual(diagnosis['reason_code'], 'incompatible')
        self.assertEqual(diagnosis['compatible_count'], 0)
        self.assertIn('platform linux is not in windows', diagnosis['artifacts'][0]['summary'])

    def test_explains_yanked_plugin(self):
        diagnosis = diagnose_market_plugin(
            {
                'id': 'org.example.hello',
                'status': 'yanked',
                'versions': [{'version': '1.0.0', 'status': 'yanked', 'artifacts': [{}]}],
            },
            runtime={
                'env': '2.0.2',
                'python': '3.12.3',
                'implementation': 'cpython',
                'abi': 'py3',
                'platform': 'linux',
                'architecture': 'x86_64',
            },
        )
        self.assertEqual(diagnosis['reason_code'], 'yanked')
        self.assertFalse(diagnosis['artifacts'][0]['compatible'])


if __name__ == '__main__':
    unittest.main()

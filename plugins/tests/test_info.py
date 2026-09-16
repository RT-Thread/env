import json
import os
import unittest
from unittest import mock

import info


def load_shipped_env_json():
    path = os.path.join(os.path.dirname(info.__file__), 'env.json')
    with open(path, 'r') as source:
        return json.load(source)


class DefaultsDriftTest(unittest.TestCase):
    """Pin info.DEFAULTS to the shipped env.json.

    DEFAULTS intentionally has no mirror entries; every leaf it does define
    must exist in the shipped env.json with the same value, otherwise the
    fallback silently diverges from the real configuration.
    """

    def _assert_leaves_match(self, defaults, shipped, path):
        for key, value in defaults.items():
            location = '.'.join(path + [str(key)])
            self.assertIn(key, shipped, 'shipped env.json is missing %s' % location)
            if isinstance(value, dict):
                self.assertIsInstance(shipped[key], dict, '%s should be an object' % location)
                self._assert_leaves_match(value, shipped[key], path + [str(key)])
            else:
                self.assertEqual(shipped[key], value, 'DEFAULTS drifted from env.json at %s' % location)

    def test_defaults_leaves_match_shipped_env_json(self):
        self._assert_leaves_match(info.DEFAULTS, load_shipped_env_json(), [])


class InfoAccessorTest(unittest.TestCase):
    def test_metadata_from_shipped_config(self):
        config = load_shipped_env_json()
        with mock.patch.object(info, 'load_env_json', return_value=config):
            self.assertEqual(info.get_name(), config['name'])
            self.assertEqual(info.get_version(), config['version'])
            self.assertEqual(info.get_description(), config['description'])

    def test_metadata_falls_back_to_defaults_without_config(self):
        with mock.patch.object(info, 'load_env_json', return_value=None):
            self.assertEqual(info.get_name(), info.DEFAULTS['name'])
            self.assertEqual(info.get_version(), info.DEFAULTS['version'])
            self.assertEqual(info.get_description(), info.DEFAULTS['description'])

    def test_get_source_primary_and_mirror(self):
        config = load_shipped_env_json()
        with mock.patch.object(info, 'load_env_json', return_value=config):
            primary = info.get_source('env')
            mirror = info.get_source('env', use_mirror=True)
        self.assertEqual(primary.url, config['repositories']['env']['url'])
        self.assertEqual(primary.branch, config['repositories']['env']['branch'])
        self.assertEqual(mirror.url, config['repositories']['env']['mirror']['url'])
        self.assertEqual(mirror.branch, config['repositories']['env']['mirror']['branch'])

    def test_get_source_falls_back_to_defaults(self):
        with mock.patch.object(info, 'load_env_json', return_value=None):
            source = info.get_source('packages')
            self.assertEqual(source.url, info.DEFAULTS['repositories']['packages']['url'])
            self.assertEqual(source.branch, info.DEFAULTS['repositories']['packages']['branch'])

    def test_mirror_is_optional_and_falls_back_to_primary(self):
        config = {'repositories': {'env': {'url': 'https://example.com/env.git', 'branch': 'dev'}}}
        with mock.patch.object(info, 'load_env_json', return_value=config):
            source = info.get_source('env', use_mirror=True)
        self.assertEqual(source.url, 'https://example.com/env.git')
        self.assertEqual(source.branch, 'dev')

    def test_mirror_branch_inherits_primary_branch(self):
        config = {'repositories': {'env': {'url': 'u1', 'branch': 'v2', 'mirror': {'url': 'm1'}}}}
        with mock.patch.object(info, 'load_env_json', return_value=config):
            source = info.get_source('env', use_mirror=True)
        self.assertEqual(source.url, 'm1')
        self.assertEqual(source.branch, 'v2')

    def test_explicit_branch_overrides_configuration(self):
        config = load_shipped_env_json()
        with mock.patch.object(info, 'load_env_json', return_value=config):
            source = info.get_source('env', branch='release-2.0')
        self.assertEqual(source.branch, 'release-2.0')

    def test_unknown_repository_raises(self):
        with mock.patch.object(info, 'load_env_json', return_value={}):
            self.assertRaises(KeyError, info.get_source, 'no-such-repo')

    def test_unknown_api_raises(self):
        with mock.patch.object(info, 'load_env_json', return_value={}):
            self.assertRaises(KeyError, info.get_api_url, 'no-such-api')

    def test_custom_repo_from_config(self):
        config = {'repositories': {'mine': {'url': 'git@example.com:me/env.git', 'branch': 'dev'}}}
        with mock.patch.object(info, 'load_env_json', return_value=config):
            source = info.get_source('mine')
        self.assertEqual(source.url, 'git@example.com:me/env.git')
        self.assertEqual(source.branch, 'dev')

    def test_custom_repo_without_url_raises(self):
        config = {'repositories': {'mine': {'branch': 'dev'}}}
        with mock.patch.object(info, 'load_env_json', return_value=config):
            self.assertRaises(KeyError, info.get_source, 'mine')

    def test_submodule_mirror_template(self):
        with mock.patch.object(info, 'load_env_json', return_value={}):
            url = info.get_submodule_mirror_url('rt-thread', 'lwip')
        self.assertEqual(url, 'https://gitee.com/RT-Thread-Mirror/submod_lwip.git')

    def test_api_url_from_config_or_defaults(self):
        with mock.patch.object(info, 'load_env_json', return_value={}):
            self.assertEqual(info.get_api_url('statistics'), info.DEFAULTS['apis']['statistics'])
        config = {'apis': {'statistics': 'https://example.com/stats'}}
        with mock.patch.object(info, 'load_env_json', return_value=config):
            self.assertEqual(info.get_api_url('statistics'), 'https://example.com/stats')


if __name__ == '__main__':
    unittest.main()

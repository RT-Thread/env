# -*- coding:utf-8 -*-
#
# File      : info.py
# This file is part of RT-Thread RTOS
# COPYRIGHT (C) 2006 - 2018, RT-Thread Development Team
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Change Logs:
# Date           Author          Notes
# 2025-06-23     Dongly      Add get_rt_env_version function
# 2026-09-10     Dongly      Add get_rt_env_description function, Extract load_env_json common helper
# 2026-09-12     Dongly      Rename version.py to info.py; single access layer for env.json (metadata, repositories, submodule mirrors, service endpoints)

import json
import os
import platform

from collections import namedtuple

# Fallback snapshot of the shipped env.json, WITHOUT mirror entries: the
# defaults only guarantee the primary source of each repository. A mirror is
# an optional accelerator that comes from env.json alone — with no mirror
# configured, the primary source is used.
DEFAULTS = {
    'name': 'RT-Thread Env Tool',
    'version': 'v2.0.2',
    'description': 'A command-line toolkit for RT-Thread development.',
    'repositories': {
        'env': {
            'url': 'https://github.com/RT-Thread/env.git',
            'branch': 'master',
        },
        'sdk': {
            'url': 'https://github.com/RT-Thread/sdk.git',
            'branch': 'main',
        },
        'packages': {
            'url': 'https://github.com/RT-Thread/packages.git',
            'branch': 'master',
        },
    },
    'submodule_mirrors': {
        'rt-thread': 'https://gitee.com/RT-Thread-Mirror/submod_{name}.git',
        'esp': 'https://gitee.com/esp-submodules/{name}.git',
    },
    'apis': {
        'mirror_query': 'https://api.rt-thread.org/packages/queries',
        'statistics': 'https://www.rt-thread.org/studio/statistics/api/envuse',
    },
}

# A repository source is an atomic (url, branch) pair: selecting a mirror
# switches the whole pair, so a primary URL can never be paired with a
# mirror branch.
Source = namedtuple('Source', ['url', 'branch'])


def load_env_json():
    # try to read env.json to get information
    try:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        env_json_path = os.path.join(script_dir, 'env.json')

        # If not found in script directory, try ENV_ROOT
        if not os.path.exists(env_json_path):
            env_root = os.getenv("ENV_ROOT")
            if env_root is None:
                if platform.system() != 'Windows':
                    env_root = os.path.join(os.getenv('HOME'), '.env')
                else:
                    env_root = os.path.join(os.getenv('USERPROFILE'), '.env')
            env_json_path = os.path.join(env_root, 'tools', 'scripts', 'env.json')

        with open(env_json_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        # Only print error if running interactively (not imported)
        if __name__ == '__main__':
            print("Failed to read env.json: %s" % str(e))

    return None


def _config_section(section):
    # return the raw config section ({} when absent or malformed)
    config = load_env_json() or {}
    value = config.get(section)
    return value if isinstance(value, dict) else {}


def get_name():
    name = (load_env_json() or {}).get('name')
    if not isinstance(name, str):
        name = DEFAULTS['name']
    return name


def get_version():
    version = (load_env_json() or {}).get('version')
    if not isinstance(version, str):
        version = DEFAULTS['version']
    return version


def get_description():
    description = (load_env_json() or {}).get('description')
    if not isinstance(description, str):
        description = DEFAULTS['description']
    return description


def get_source(repo, use_mirror=False, branch=None):
    # Resolve a repository source as Source(url, branch).
    # Priority: explicit branch argument > configured branch of that source
    # (a mirror without 'branch' inherits the primary branch) > DEFAULTS
    # branch. DEFAULTS never supplies a mirror: with no mirror url in
    # env.json, the primary source is used. Unknown repository names and
    # entries without a url raise KeyError — config problems fail loudly.
    raw_entry = _config_section('repositories').get(repo)
    if not isinstance(raw_entry, dict):
        raw_entry = {}
    if repo not in DEFAULTS['repositories'] and not raw_entry:
        raise KeyError('unknown repository: %r' % (repo,))

    default_entry = DEFAULTS['repositories'].get(repo, {})
    url = raw_entry.get('url') or default_entry.get('url')
    resolved_branch = raw_entry.get('branch') or default_entry.get('branch')

    if use_mirror:
        mirror = raw_entry.get('mirror') if isinstance(raw_entry.get('mirror'), dict) else {}
        if mirror.get('url'):
            url = mirror['url']
            resolved_branch = mirror.get('branch') or resolved_branch

    if url is None:
        raise KeyError("repository %r is configured without a 'url'" % (repo,))
    if branch is not None:
        resolved_branch = branch
    return Source(url=url, branch=resolved_branch)


def get_submodule_mirror_url(kind, name):
    # Instantiate a submodule mirror template ('{name}' placeholder) for the
    # given submodule name. kind: 'rt-thread' or 'esp'. ESP name case mapping
    # (unity -> Unity) is caller-side logic, not configuration.
    template = _config_section('submodule_mirrors').get(kind) or DEFAULTS['submodule_mirrors'].get(kind)
    if not isinstance(template, str):
        raise KeyError('unknown submodule mirror kind: %r' % (kind,))
    return template.replace('{name}', name)


def get_api_url(name):
    # Service endpoints. name: 'mirror_query' or 'statistics'.
    url = _config_section('apis').get(name) or DEFAULTS['apis'].get(name)
    if not isinstance(url, str):
        raise KeyError('unknown api name: %r' % (name,))
    return url

"""Shared Env and RT-Thread path resolution without command imports."""

import os
import platform
import shlex


def get_env_root():
    configured = os.environ.get('ENV_ROOT')
    if configured:
        return os.path.abspath(os.path.expanduser(configured))
    home_variable = 'USERPROFILE' if platform.system() == 'Windows' else 'HOME'
    home = os.environ.get(home_variable) or os.path.expanduser('~')
    return os.path.abspath(os.path.join(home, '.env'))


def get_package_root():
    configured = os.environ.get('PKGS_ROOT')
    return os.path.abspath(configured) if configured else os.path.join(get_env_root(), 'packages')


def _resolve_project_path(root, value):
    value = os.path.expandvars(value)
    return os.path.normpath(value if os.path.isabs(value) else os.path.join(root, value))


def _kconfig_rtt_root(bsp_root):
    filename = os.path.join(bsp_root, 'Kconfig')
    if not os.path.isfile(filename):
        return None
    in_rtt_dir = False
    with open(filename, 'r', encoding='utf-8') as source:
        for line in source:
            try:
                tokens = shlex.split(line, comments=True)
            except ValueError:
                continue
            if not tokens:
                continue
            if tokens[0] in ('config', 'menuconfig'):
                in_rtt_dir = len(tokens) > 1 and tokens[1] == 'RTT_DIR'
            elif in_rtt_dir and tokens[0] == 'default' and len(tokens) > 1:
                return _resolve_project_path(bsp_root, tokens[1])
            elif len(tokens) > 2 and tokens[:2] == ['RTT_DIR', ':=']:
                return _resolve_project_path(bsp_root, tokens[2])
    return None


def get_rtt_root(bsp_root=None):
    bsp_root = os.path.abspath(bsp_root or os.getcwd())
    configured = os.environ.get('RTT_ROOT')
    if configured:
        return _resolve_project_path(bsp_root, configured)
    root = _kconfig_rtt_root(bsp_root)
    if root:
        return root
    embedded = os.path.join(bsp_root, 'rt-thread')
    if os.path.isfile(os.path.join(embedded, 'include', 'rtdef.h')):
        return embedded
    current = bsp_root
    while os.path.dirname(current) != current:
        parent = os.path.dirname(current)
        if os.path.basename(current) == 'bsp' and os.path.isfile(os.path.join(parent, 'include', 'rtdef.h')):
            return parent
        current = parent
    return None

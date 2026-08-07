"""Host compatibility evaluation for plugin manifests."""

import platform
import re
import sys

from .errors import CompatibilityError, ManifestError


_CLAUSE_RE = re.compile(r'^(==|!=|<=|>=|<|>)?\s*v?([0-9]+(?:\.[0-9]+){0,3})$')
_VERSION_RE = re.compile(
    r'^v?([0-9]+(?:\.[0-9]+){0,3})(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z.-]+)?$'
)


def _version_parts(value):
    value = str(value).strip()
    match = _VERSION_RE.match(value)
    if not match:
        raise ManifestError("invalid version value: %s" % value)
    parts = [int(part) for part in match.group(1).split('.')]
    while len(parts) < 4:
        parts.append(0)
    prerelease = match.group(2)
    identifiers = None if prerelease is None else tuple(prerelease.split('.'))
    return tuple(parts), identifiers


def compare_versions(left, right):
    left_core, left_prerelease = _version_parts(left)
    right_core, right_prerelease = _version_parts(right)
    if left_core != right_core:
        return -1 if left_core < right_core else 1
    if left_prerelease is None or right_prerelease is None:
        if left_prerelease is right_prerelease:
            return 0
        return 1 if left_prerelease is None else -1
    for left_item, right_item in zip(left_prerelease, right_prerelease):
        if left_item == right_item:
            continue
        left_numeric = left_item.isdigit()
        right_numeric = right_item.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left_item) < int(right_item) else 1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return -1 if left_item < right_item else 1
    if len(left_prerelease) == len(right_prerelease):
        return 0
    return -1 if len(left_prerelease) < len(right_prerelease) else 1


def version_satisfies(version, expression):
    for raw_clause in expression.split(','):
        clause = raw_clause.strip()
        match = _CLAUSE_RE.match(clause)
        if not match:
            raise ManifestError("invalid version constraint: %s" % clause)
        operator = match.group(1) or '=='
        comparison = compare_versions(version, match.group(2))
        matches = {
            '==': comparison == 0,
            '!=': comparison != 0,
            '<': comparison < 0,
            '<=': comparison <= 0,
            '>': comparison > 0,
            '>=': comparison >= 0,
        }[operator]
        if not matches:
            return False
    return True


def normalize_platform(value=None):
    value = (value or platform.system()).lower()
    return {'linux': 'linux', 'windows': 'windows', 'darwin': 'darwin'}.get(value, value)


def normalize_architecture(value=None):
    value = (value or platform.machine()).lower().replace('-', '_')
    aliases = {
        'amd64': 'x86_64',
        'x64': 'x86_64',
        'i386': 'x86',
        'i486': 'x86',
        'i586': 'x86',
        'i686': 'x86',
        'arm64': 'aarch64',
        'armv7l': 'arm',
        'armv8l': 'arm',
    }
    return aliases.get(value, value)


def python_abi():
    implementation = platform.python_implementation().lower()
    if implementation != 'cpython':
        return implementation
    return 'cp%d%d' % (sys.version_info[0], sys.version_info[1])


def current_env_version():
    try:
        from version import get_rt_env_version
    except ImportError:
        from env.version import get_rt_env_version
    return get_rt_env_version()[1]


def compatibility_issues(manifest, env_version=None, system=None, architecture=None, implementation=None, abi=None):
    compatibility = manifest.compatibility
    issues = []
    env_version = env_version or current_env_version()
    python_version = '%d.%d.%d' % sys.version_info[:3]
    system = normalize_platform(system)
    architecture = normalize_architecture(architecture)
    implementation = (implementation or platform.python_implementation()).lower()
    abi = abi or python_abi()

    if not version_satisfies(env_version, compatibility['env']):
        issues.append("Env %s does not satisfy %s" % (env_version, compatibility['env']))
    if not version_satisfies(python_version, compatibility['python']):
        issues.append("Python %s does not satisfy %s" % (python_version, compatibility['python']))
    if implementation not in compatibility['implementations']:
        issues.append("Python implementation %s is not supported" % implementation)
    if 'any' not in compatibility['platforms'] and system not in compatibility['platforms']:
        issues.append("platform %s is not supported" % system)
    if 'any' not in compatibility['architectures'] and architecture not in compatibility['architectures']:
        issues.append("architecture %s is not supported" % architecture)
    if abi not in compatibility['abis'] and 'py3' not in compatibility['abis']:
        issues.append("Python ABI %s is not supported" % abi)
    if manifest.webui and not version_satisfies('1.0.0', manifest.webui['frontend_sdk']):
        issues.append("WebUI frontend SDK 1.0.0 does not satisfy %s" % manifest.webui['frontend_sdk'])
    return issues


def ensure_compatible(manifest, **overrides):
    issues = compatibility_issues(manifest, **overrides)
    if issues:
        raise CompatibilityError('; '.join(issues))

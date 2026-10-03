"""Persistent, process-local networking policy shared by Env entry points."""

import ipaddress
import json
import os
import tempfile
from urllib.parse import urlparse
from urllib.request import ProxyHandler, build_opener, getproxies, proxy_bypass_environment


ALIYUN_INDEX_URL = 'https://mirrors.aliyun.com/pypi/simple/'
DEFAULT_SETTINGS = {
    'proxy_mode': 'system',
    'proxy_url': '',
    'no_proxy': 'localhost,127.0.0.1,::1',
    'download_server': 'auto',
    'pypi_mode': 'auto',
    'pypi_url': '',
    'timeout': 60,
}
PROXY_KEYS = frozenset(('http_proxy', 'https_proxy', 'all_proxy', 'ftp_proxy', 'pip_proxy', 'no_proxy'))


class NetworkConfigError(ValueError):
    """A saved or submitted network configuration is invalid."""


def _http_url(value, field, proxy=False):
    if not isinstance(value, str) or any(character.isspace() for character in value):
        raise NetworkConfigError('%s must be an HTTP(S) URL without whitespace' % field)
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        raise NetworkConfigError('%s contains an invalid host or port' % field)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or (port is not None and not 1 <= port <= 65535)):
        raise NetworkConfigError('%s must be an HTTP(S) URL without credentials, query or fragment' % field)
    if proxy and parsed.path not in ('', '/'):
        raise NetworkConfigError('proxy_url must not contain a path')
    return value.rstrip('/') if proxy else value


def validate_settings(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT_SETTINGS):
        raise NetworkConfigError('network settings contain unknown fields')
    settings = dict(DEFAULT_SETTINGS)
    settings.update(value)
    for field, choices in (
        ('proxy_mode', ('system', 'direct', 'custom')),
        ('download_server', ('auto', 'github', 'gitee')),
        ('pypi_mode', ('auto', 'default', 'aliyun', 'custom')),
    ):
        if settings[field] not in choices:
            raise NetworkConfigError('invalid %s' % field)
    for field in ('proxy_url', 'no_proxy', 'pypi_url'):
        if not isinstance(settings[field], str) or len(settings[field]) > 2048:
            raise NetworkConfigError('%s must be a string of at most 2048 characters' % field)
        settings[field] = settings[field].strip()
    if any(character.isspace() and character != ' ' for character in settings['no_proxy']):
        raise NetworkConfigError('no_proxy must be a comma-separated list on one line')
    if settings['proxy_url']:
        settings['proxy_url'] = _http_url(settings['proxy_url'], 'proxy_url', proxy=True)
    if settings['proxy_mode'] == 'custom' and not settings['proxy_url']:
        raise NetworkConfigError('custom proxy requires proxy_url')
    if settings['pypi_url']:
        settings['pypi_url'] = _http_url(settings['pypi_url'], 'pypi_url')
    if settings['pypi_mode'] == 'custom' and not settings['pypi_url']:
        raise NetworkConfigError('custom Python package index requires pypi_url')
    timeout = settings['timeout']
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 300:
        raise NetworkConfigError('timeout must be an integer between 1 and 300 seconds')
    return settings


class NetworkSettings(object):
    def __init__(self, env_root=None):
        home = os.environ.get('HOME') or os.environ.get('USERPROFILE') or os.path.expanduser('~')
        self.env_root = os.path.abspath(env_root or os.environ.get('ENV_ROOT') or os.path.join(home, '.env'))
        self.config_path = os.path.join(self.env_root, 'var', 'network.json')

    def configured(self):
        return os.path.isfile(self.config_path)

    def revision(self):
        try:
            stat = os.stat(self.config_path)
            return '%d:%d' % (stat.st_mtime_ns, stat.st_size)
        except FileNotFoundError:
            return 'missing'

    def load(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as source:
                value = json.load(source)
        except FileNotFoundError:
            return dict(DEFAULT_SETTINGS)
        except (OSError, ValueError):
            raise NetworkConfigError('cannot read network settings: %s' % self.config_path)
        return validate_settings(value)

    def snapshot(self):
        return {
            'settings': self.load(),
            'config_path': self.config_path,
            'configured': self.configured(),
            'pypi_overridden': bool(os.environ.get('ENV_PYPI_INDEX_URL', '').strip()),
        }

    def save(self, value):
        settings = validate_settings(value)
        directory = os.path.dirname(self.config_path)
        os.makedirs(directory, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='.network-', dir=directory, text=True)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
                json.dump(settings, output, indent=2, sort_keys=True)
                output.write('\n')
            os.replace(temporary, self.config_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return self.snapshot()

    def timeout(self, default):
        return self.load()['timeout'] if self.configured() else default


def _bypass(url, settings):
    host = urlparse(url).hostname or ''
    if host.lower() == 'localhost' or host.lower().endswith('.localhost'):
        return True
    try:
        if ipaddress.ip_address(host).is_loopback:
            return True
    except ValueError:
        pass
    return proxy_bypass_environment(host, {'no': settings['no_proxy']})


def request(method, url, env_root=None, **kwargs):
    """Keep TLS verification enabled and never route loopback through a proxy."""
    import requests

    policy = NetworkSettings(env_root)
    settings = policy.load()
    kwargs['timeout'] = policy.timeout(kwargs.get('timeout', 60))

    class PolicySession(requests.Session):
        def rebuild_proxies(self, prepared_request, proxies):
            # Redirects can change hosts, including a redirect to loopback.
            bypass = _bypass(prepared_request.url, settings)
            self.trust_env = settings['proxy_mode'] == 'system' and not bypass
            if bypass or settings['proxy_mode'] == 'direct':
                proxies = {}
            elif settings['proxy_mode'] == 'custom':
                proxies = {'http': settings['proxy_url'], 'https': settings['proxy_url']}
            return super(PolicySession, self).rebuild_proxies(prepared_request, proxies)

    with PolicySession() as session:
        if settings['proxy_mode'] != 'system' or _bypass(url, settings):
            session.trust_env = False
        if settings['proxy_mode'] == 'custom' and not _bypass(url, settings):
            session.proxies = {'http': settings['proxy_url'], 'https': settings['proxy_url']}
        if not session.trust_env:
            certificate = os.environ.get('REQUESTS_CA_BUNDLE') or os.environ.get('CURL_CA_BUNDLE')
            if certificate:
                kwargs.setdefault('verify', certificate)
        return session.request(method, url, **kwargs)


class _PolicyProxyHandler(ProxyHandler):
    def __init__(self, settings):
        self.settings = settings
        if settings['proxy_mode'] == 'custom':
            proxies = {'http': settings['proxy_url'], 'https': settings['proxy_url']}
        elif settings['proxy_mode'] == 'direct':
            proxies = {}
        else:
            proxies = getproxies()
        super(_PolicyProxyHandler, self).__init__(proxies)

    def proxy_open(self, req, proxy, type):
        if _bypass(req.full_url, self.settings):
            return None
        return super(_PolicyProxyHandler, self).proxy_open(req, proxy, type)


def urllib_opener(*handlers, **kwargs):
    settings = NetworkSettings(kwargs.get('env_root')).load()
    return build_opener(_PolicyProxyHandler(settings), *handlers)


def subprocess_environment(environ=None, env_root=None, bootstrap=False):
    environment = dict(os.environ if environ is None else environ)
    if env_root:
        environment['ENV_ROOT'] = os.path.abspath(env_root)
    else:
        env_root = environment.get('ENV_ROOT')
    policy = NetworkSettings(env_root)
    settings = policy.load()
    mode = 'direct' if bootstrap and not policy.configured() else settings['proxy_mode']
    if mode != 'system':
        for key in list(environment):
            if key.lower() in PROXY_KEYS:
                environment.pop(key)
        if mode == 'custom':
            for scheme in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'):
                environment[scheme] = settings['proxy_url']
        # Per-command overrides also defeat proxy values in Git/pip config files.
        index = int(environment.get('GIT_CONFIG_COUNT', '0'))
        environment['GIT_CONFIG_COUNT'] = str(index + 1)
        environment['GIT_CONFIG_KEY_%d' % index] = 'http.proxy'
        environment['GIT_CONFIG_VALUE_%d' % index] = settings['proxy_url'] if mode == 'custom' else ''
        if policy.configured():
            environment['PIP_PROXY'] = settings['proxy_url'] if mode == 'custom' else ''
    inherited_bypass = environment.get('NO_PROXY') or environment.get('no_proxy') or ''
    bypass = ','.join(filter(None, ('localhost,127.0.0.1,::1', settings['no_proxy'], inherited_bypass)))
    environment['NO_PROXY'] = environment['no_proxy'] = bypass
    if policy.configured():
        environment['PIP_DEFAULT_TIMEOUT'] = str(settings['timeout'])
    return environment


def pypi_index_url(env_root=None, environ=None):
    environment = os.environ if environ is None else environ
    override = environment.get('ENV_PYPI_INDEX_URL', '').strip()
    if override:
        return override
    settings = NetworkSettings(env_root).load()
    if settings['pypi_mode'] == 'aliyun':
        return ALIYUN_INDEX_URL
    if settings['pypi_mode'] == 'custom':
        return settings['pypi_url']
    return None

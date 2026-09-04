"""Local Host API for the Env WebUI."""

from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import http.client
import ipaddress
import json
import mimetypes
import os
import secrets
import socket
import threading
import time
from urllib.parse import parse_qs, quote, unquote, urlparse

from ..errors import PluginError, StateError, UsageError
from ..backend import BackendUnavailableError
from ..market import (
    MarketClient,
    MarketError,
    annotate_catalog_item,
    diagnose_market_plugin,
    load_market_config,
    public_artifact,
    runtime_profile,
    strip_download_urls,
)
from ..service import PluginService
from . import FRONTEND_SDK_VERSION, WEBUI_API_VERSION

# The command-line compatibility entry point imports ``plugins`` as a
# top-level package, while installed consumers import ``env.plugins``.
# Select the matching manager imports explicitly instead of probing with a
# relative import whose exception type differs between Python versions.
if (__package__ or '').split('.', 1)[0] == 'env':
    from ...sdk_manager import SdkManager, SdkUsageError
    from ...toolchain_manager import ToolchainManager
    from ...file_context_menu import FileContextMenuManager
else:
    from sdk_manager import SdkManager, SdkUsageError
    from toolchain_manager import ToolchainManager
    from file_context_menu import FileContextMenuManager


SESSION_COOKIE = 'env_webui_session'
UPLOAD_TTL = 15 * 60
JSON_LIMIT = 256 * 1024
PACKAGE_LIMIT = 256 * 1024 * 1024


class MarketNotConfigured(UsageError):
    pass


class WebUIApplication(object):
    def __init__(
        self,
        env_root=None,
        workspace=None,
        static_root=None,
        launcher_dir=None,
        allow_remote_hosts=False,
        initial_plugin=None,
    ):
        self.service = PluginService(env_root=env_root, launcher_dir=launcher_dir)
        self.service.paths.ensure()
        self.sdk = SdkManager(env_root=env_root)
        self.toolchains = ToolchainManager(env_root=env_root)
        self.context_menu = FileContextMenuManager(env_root=env_root)
        self.workspace = os.path.abspath(workspace or os.getcwd())
        if not os.path.isdir(self.workspace):
            raise UsageError("WebUI workspace is not a directory: %s" % self.workspace)
        self.static_root = os.path.abspath(static_root or os.path.join(os.path.dirname(__file__), 'static'))
        self.launch_token = secrets.token_urlsafe(32)
        self.session_token = secrets.token_urlsafe(32)
        self.csrf_token = secrets.token_urlsafe(32)
        self.initial_plugin = initial_plugin.strip() if isinstance(initial_plugin, str) else None
        self.allow_remote_hosts = bool(allow_remote_hosts)
        self.uploads = {}
        self.upload_lock = threading.Lock()
        self.asset_tokens = {}
        self.asset_token_lock = threading.Lock()
        self.market = load_market_config(self.service.paths)
        self.market_client = MarketClient(self.market['url']) if self.market['enabled'] else None

    def consume_launch(self, token):
        if not self.launch_token or not hmac.compare_digest(token, self.launch_token):
            return False
        self.launch_token = None
        return True

    def authenticated(self, cookie_header):
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_header or '')
        except Exception:
            return False
        value = cookie.get(SESSION_COOKIE)
        return bool(value and hmac.compare_digest(value.value, self.session_token))

    def installed(self):
        return [self._public_plugin(self.service.info(item['id'])) for item in self.service.list()]

    def plugin_asset_context(self):
        result = {}
        for item in self.installed():
            if not item.get('enabled') or not item.get('webui'):
                continue
            if item.get('missing_required_permissions'):
                continue
            base = '/plugin-assets/%s/%s/' % (self.asset_token_for(item['id']), quote(item['id'], safe=''))
            backend = None
            if item.get('service'):
                backend = {
                    'http_base': base + 'backend/',
                    'websocket_base': base + 'backend/',
                }
            result[item['id']] = {'base': base, 'backend': backend}
        return result

    def asset_token_for(self, plugin_id):
        with self.asset_token_lock:
            token = self.asset_tokens.get(plugin_id)
            if token is None:
                token = secrets.token_urlsafe(32)
                self.asset_tokens[plugin_id] = token
            return token

    def plugin_for_asset_token(self, token):
        if not isinstance(token, str) or not token:
            return None
        with self.asset_token_lock:
            for plugin_id, candidate in self.asset_tokens.items():
                if hmac.compare_digest(token, candidate):
                    return plugin_id
        return None

    def _public_plugin(self, item):
        result = dict(item)
        source = result.pop('source', '')
        result['source_type'] = 'local'
        result['source_name'] = os.path.basename(source) if source else ''
        required = set(permission['name'] for permission in result.get('permissions', []) if permission['required'])
        result['missing_required_permissions'] = sorted(required - set(result.get('granted_permissions', [])))
        return result

    def save_upload(self, content, filename):
        if not filename.lower().endswith('.epack'):
            raise UsageError("local plugin package must use the .epack extension")
        self.cleanup_uploads()
        token = secrets.token_urlsafe(24)
        target = os.path.join(self.service.paths.staging, 'webui-upload-%s.epack' % token)
        with open(target, 'wb') as output:
            output.write(content)
        try:
            return self._register_upload(target, filename, token)
        except Exception:
            try:
                os.unlink(target)
            except OSError:
                pass
            raise

    def register_package(self, package_path, filename):
        self.cleanup_uploads()
        token = secrets.token_urlsafe(24)
        target = os.path.join(self.service.paths.staging, 'webui-upload-%s.epack' % token)
        os.replace(package_path, target)
        try:
            return self._register_upload(target, filename, token)
        except Exception:
            try:
                os.unlink(target)
            except OSError:
                pass
            raise

    def _register_upload(self, target, filename, token):
        summary = self.service.inspect_package(target)
        with self.upload_lock:
            self.uploads[token] = (target, time.monotonic() + UPLOAD_TTL)
        summary['path'] = os.path.basename(filename)
        summary['compatibility_issues'] = []
        summary['upload_id'] = token
        return summary

    def installed_index(self):
        return dict((item['id'], item) for item in self.service.list())

    def sdk_snapshot(self):
        try:
            snapshot = self.sdk.snapshot()
        except SdkUsageError as exc:
            return {
                'available': False,
                'platform': self.sdk.hostos,
                'packages_root': self.sdk.packages_root,
                'index_root': self.sdk.index_root,
                'config_path': self.sdk.config_path,
                'revision': self.sdk.revision(),
                'config_revision': self.sdk.revision(),
                'packages': [],
                'error': str(exc),
            }
        snapshot['available'] = True
        return snapshot

    def sdk_plan(self, body):
        return self.sdk.plan(body)

    def sdk_apply(self, body):
        if not isinstance(body, dict) or set(body) - set(['plan_id', 'confirm_remove']) or 'plan_id' not in body:
            raise UsageError('SDK apply request must contain plan_id and optional confirm_remove')
        confirm_remove = body.get('confirm_remove', [])
        return self.sdk.start_apply(body['plan_id'], confirm_remove)

    def sdk_task(self, task_id):
        return self.sdk.task(task_id)

    def sdk_cancel_task(self, task_id):
        return self.sdk.cancel_task(task_id)

    def toolchain_snapshot(self):
        return self.toolchains.snapshot()

    def add_toolchain(self, body):
        return self.toolchains.add(body)

    def update_toolchain(self, name, body):
        return self.toolchains.update(name, body)

    def remove_toolchain(self, name):
        return self.toolchains.remove(name)

    def context_menu_snapshot(self):
        return self.context_menu.snapshot()

    def install_context_menu(self):
        return self.context_menu.install()

    def remove_context_menu(self):
        return self.context_menu.remove()

    def market_status(self):
        self._require_market()
        try:
            reachable = self.market_client.health()
            message = ''
        except MarketError as exc:
            reachable = False
            message = str(exc)
        return {
            'enabled': True,
            'url': self.market['url'],
            'source': self.market['source'],
            'reachable': reachable,
            'message': message,
            'runtime': runtime_profile(),
        }

    def market_plugins(self, query):
        self._require_market()
        catalog = self.market_client.list_plugins(
            query=_first(query, 'q', ''),
            sort=_first(query, 'sort', 'updated'),
            page=_int_query(query, 'page', 1, 1, None),
            page_size=_int_query(query, 'page_size', 20, 1, 100),
        )
        installed = self.installed_index()
        items = [annotate_catalog_item(item, installed) for item in catalog.get('items') or []]
        result = dict(catalog)
        result['items'] = items
        return result

    def market_plugin(self, plugin_id):
        self._require_market()
        detail = strip_download_urls(self.market_client.plugin_detail(plugin_id))
        installed = self.installed_index()
        result = annotate_catalog_item(detail, installed)
        result['compatible'] = False
        result['compatibility_message'] = ''
        result['resolved'] = None
        diagnosis = diagnose_market_plugin(detail, installed.get(plugin_id))
        result['diagnosis'] = diagnosis
        try:
            resolved = self.market_client.resolve(plugin_id)
        except MarketError as exc:
            result['compatibility_message'] = diagnosis.get('summary') or str(exc)
            if exc.code in ('incompatible', 'yanked') or exc.status in (404, 410):
                result['action'] = 'incompatible'
            else:
                raise
        else:
            artifact = public_artifact(resolved.get('artifact'))
            result['compatible'] = True
            result['resolved'] = {
                'version': (artifact or {}).get('version'),
                'artifact': artifact,
            }
            result['compatibility_message'] = diagnosis.get('summary') or ''
        return result

    def prepare_market_plugin(self, plugin_id):
        self._require_market()
        try:
            resolved = self.market_client.resolve(plugin_id)
        except MarketError as exc:
            raise self._prepare_error(plugin_id, exc, 'resolve')
        artifact = resolved.get('artifact') or {}
        sha256 = artifact.get('sha256') or artifact.get('id')
        filename = artifact.get('filename') or ('%s.epack' % plugin_id)
        token_name = secrets.token_urlsafe(12)
        temporary = os.path.join(self.service.paths.staging, 'market-download-%s.epack' % token_name)
        try:
            try:
                self.market_client.download(sha256, temporary, filename=filename)
            except MarketError as exc:
                raise self._prepare_error(plugin_id, exc, 'download')
            try:
                summary = self.register_package(temporary, filename)
            except PluginError as exc:
                raise self._prepare_error(plugin_id, exc, 'inspect')
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        if summary['id'] != plugin_id:
            package_path = self.consume_upload(summary['upload_id'])
            try:
                os.unlink(package_path)
            except OSError:
                pass
            raise MarketError(
                'downloaded package id does not match the market plugin',
                code='invalid_package',
                status=400,
                details={'stage': 'inspect'},
            )
        return summary

    def _prepare_error(self, plugin_id, exc, stage):
        details = {'stage': stage}
        if isinstance(exc, MarketError) and exc.details:
            details.update(exc.details)
        if stage in ('resolve', 'download') and (
            isinstance(exc, MarketError) and (exc.code in ('incompatible', 'yanked') or exc.status in (404, 410))
        ):
            try:
                detail = strip_download_urls(self.market_client.plugin_detail(plugin_id))
                details['diagnosis'] = diagnose_market_plugin(detail, self.installed_index().get(plugin_id))
            except Exception:
                pass
        code = exc.code if isinstance(exc, MarketError) else exc.__class__.__name__.lower()
        status = exc.status if isinstance(exc, MarketError) else 422
        if isinstance(exc, UsageError) and not isinstance(exc, MarketError):
            status = 400
        return MarketError(str(exc), code=code, status=status, details=details)

    def _require_market(self):
        if self.market_client is None:
            raise MarketNotConfigured()

    def consume_upload(self, token):
        self.cleanup_uploads()
        with self.upload_lock:
            value = self.uploads.pop(token, None)
        if value is None:
            raise UsageError("upload token is invalid or expired")
        return value[0]

    def cleanup_uploads(self):
        expired = []
        now = time.monotonic()
        with self.upload_lock:
            for token, value in list(self.uploads.items()):
                if value[1] <= now:
                    expired.append(value[0])
                    del self.uploads[token]
        for path in expired:
            try:
                os.unlink(path)
            except OSError:
                pass

    def close(self):
        self.service.stop_backends()
        with self.upload_lock:
            paths = [value[0] for value in self.uploads.values()]
            self.uploads.clear()
        for path in paths:
            try:
                os.unlink(path)
            except OSError:
                pass


class EnvWebUIHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, application):
        self.application = application
        super(EnvWebUIHTTPServer, self).__init__(address, EnvWebUIRequestHandler)


class EnvWebUIRequestHandler(BaseHTTPRequestHandler):
    server_version = 'EnvWebUI/1.0'

    def log_message(self, format_string, *args):
        return

    @property
    def application(self):
        return self.server.application

    def do_GET(self):
        self._dispatch('GET')

    def do_POST(self):
        self._dispatch('POST')

    def do_PUT(self):
        self._dispatch('PUT')

    def do_PATCH(self):
        self._dispatch('PATCH')

    def do_DELETE(self):
        self._dispatch('DELETE')

    def do_OPTIONS(self):
        if self._valid_host() and self._is_backend_request(urlparse(self.path).path):
            self._plugin_options()
            return
        self._error(HTTPStatus.FORBIDDEN, 'cross_origin_denied', 'cross-origin requests are not allowed')

    def _dispatch(self, method):
        try:
            if not self._valid_host():
                self._error(HTTPStatus.BAD_REQUEST, 'invalid_host', 'request Host is not allowed')
                return
            parsed = urlparse(self.path)
            if parsed.path.startswith('/_launch/'):
                self._launch(parsed)
                return
            if method == 'GET' and parsed.path.startswith('/plugin-assets/') and not self._is_tokenized_backend_request(parsed.path):
                self._tokenized_plugin_asset(parsed.path)
                return
            authenticated = self.application.authenticated(self.headers.get('Cookie'))
            # The tokenized asset URL is a plugin-scoped bearer capability.
            # Sandboxed plugin frames cannot send Env's SameSite=Strict cookie,
            # so allow their tokenized backend requests to reach the normal
            # plugin and origin checks below.
            if not authenticated and not self._is_tokenized_backend_request(parsed.path):
                self._error(HTTPStatus.UNAUTHORIZED, 'authentication_required', 'open the URL printed by env webui')
                return
            if method == 'GET' and self._is_backend_path(parsed.path) and self._is_websocket_request():
                if not self._valid_plugin_origin():
                    self._error(HTTPStatus.FORBIDDEN, 'origin_denied', 'WebSocket Origin is not allowed')
                    return
                self._plugin_websocket_proxy(parsed)
                return
            if self._is_backend_path(parsed.path) and self._is_backend_request(parsed.path):
                if not self._valid_plugin_origin():
                    self._error(HTTPStatus.FORBIDDEN, 'origin_denied', 'plugin request Origin is not allowed')
                    return
                self._plugin_http_proxy(method, parsed)
                return
            if parsed.path.startswith('/api/'):
                if method != 'GET' and not self._valid_write_request():
                    return
                self._api(method, parsed)
                return
            if method != 'GET':
                self._error(HTTPStatus.METHOD_NOT_ALLOWED, 'method_not_allowed', 'method is not allowed')
                return
            if parsed.path.startswith('/plugins/'):
                self._plugin_asset(parsed.path)
            else:
                self._host_asset(parsed.path)
        except MarketNotConfigured:
            self._error(HTTPStatus.NOT_FOUND, 'not_found', 'API endpoint was not found')
        except MarketError as exc:
            try:
                status = HTTPStatus(exc.status)
            except ValueError:
                status = HTTPStatus.BAD_GATEWAY
            self._error(status, exc.code, str(exc), details=exc.details)
        except PluginError as exc:
            status = HTTPStatus.CONFLICT if isinstance(exc, StateError) else HTTPStatus.UNPROCESSABLE_ENTITY
            if isinstance(exc, UsageError):
                status = HTTPStatus.BAD_REQUEST
            self._error(status, exc.__class__.__name__.lower(), str(exc))
        except (ValueError, OSError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, 'invalid_request', str(exc))
        except BackendUnavailableError as exc:
            self._error(HTTPStatus.BAD_GATEWAY, 'backend_unavailable', str(exc))
        except Exception:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, 'internal_error', 'the WebUI request could not be completed')

    def _launch(self, parsed):
        path = parsed.path
        token = unquote(path[len('/_launch/'):])
        if not self.application.consume_launch(token):
            self._error(
                HTTPStatus.UNAUTHORIZED,
                'invalid_launch_token',
                'launch URL is invalid or has already been used',
            )
            return
        self.send_response(HTTPStatus.SEE_OTHER)
        location = '/'
        if self.application.initial_plugin:
            location += '?plugin=' + quote(self.application.initial_plugin, safe='')
        self.send_header('Location', location)
        cookie = '%s=%s; HttpOnly; SameSite=Strict; Path=/' % (
            SESSION_COOKIE,
            self.application.session_token,
        )
        self.send_header('Set-Cookie', cookie)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()

    def _api(self, method, parsed):
        path = parsed.path
        query = parse_qs(parsed.query)
        if method == 'GET' and path == '/api/v1/session':
            self._json(
                {
                    'api_version': WEBUI_API_VERSION,
                    'frontend_sdk': FRONTEND_SDK_VERSION,
                    'workspace': self.application.workspace,
                    'csrf_token': self.application.csrf_token,
                    'plugin_assets': self.application.plugin_asset_context(),
                    'market': {
                        'enabled': bool(self.application.market['enabled']),
                        'url': self.application.market.get('url') or '',
                        'source': self.application.market.get('source'),
                    },
                }
            )
            return
        if method == 'POST' and path == '/api/v1/shutdown':
            self._json({'status': 'shutting_down'})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if method == 'GET' and path == '/api/v1/market/status':
            self._json(self.application.market_status())
            return
        if method == 'GET' and path == '/api/v1/market/plugins':
            self._json(self.application.market_plugins(query))
            return
        if method == 'GET' and path == '/api/v1/plugins':
            self._json(self.application.installed())
            return
        if method == 'GET' and path == '/api/v1/sdk':
            self._json(self.application.sdk_snapshot())
            return
        if method == 'GET' and path == '/api/v1/settings/toolchains':
            self._json(self.application.toolchain_snapshot())
            return
        if method == 'GET' and path == '/api/v1/settings/file-context-menu':
            self._json(self.application.context_menu_snapshot())
            return
        if method == 'POST' and path == '/api/v1/sdk/plan':
            self._json(self.application.sdk_plan(self._read_json()))
            return
        if method == 'POST' and path == '/api/v1/sdk/apply':
            self._json(self.application.sdk_apply(self._read_json()), status=HTTPStatus.ACCEPTED)
            return
        if method == 'POST' and path == '/api/v1/settings/toolchains':
            self._json(self.application.add_toolchain(self._read_json()), status=HTTPStatus.CREATED)
            return
        if method == 'POST' and path == '/api/v1/settings/file-context-menu/install':
            self._json(self.application.install_context_menu(), status=HTTPStatus.CREATED)
            return
        if method == 'POST' and path == '/api/v1/settings/file-context-menu/remove':
            self._json(self.application.remove_context_menu())
            return
        if method == 'POST' and path == '/api/v1/packages':
            content = self._read_body(PACKAGE_LIMIT)
            filename = unquote(self.headers.get('X-Filename', 'local.epack'))
            self._json(self.application.save_upload(content, filename), status=HTTPStatus.CREATED)
            return
        if method == 'POST' and path == '/api/v1/plugins/install':
            body = self._read_json()
            result = self._install(body, upgrade=False)
            self._json(self.application._public_plugin(result), status=HTTPStatus.CREATED)
            return
        segments = [unquote(item) for item in path.split('/') if item]
        if len(segments) >= 4 and segments[:3] == ['api', 'v1', 'market']:
            if segments[3] == 'plugins' and len(segments) >= 5:
                plugin_id = segments[4]
                if method == 'GET' and len(segments) == 5:
                    self._json(self.application.market_plugin(plugin_id))
                    return
                if method == 'POST' and len(segments) == 6 and segments[5] == 'prepare':
                    self._json(self.application.prepare_market_plugin(plugin_id), status=HTTPStatus.CREATED)
                    return
        if len(segments) >= 4 and segments[:3] == ['api', 'v1', 'plugins']:
            plugin_id = segments[3]
            if method == 'GET' and len(segments) == 4:
                self._json(self.application._public_plugin(self.application.service.info(plugin_id)))
                return
            if method == 'GET' and len(segments) == 5 and segments[4] == 'doctor':
                self._json(self.application.service.doctor(plugin_id))
                return
            if method == 'POST' and len(segments) == 5 and segments[4] == 'upgrade':
                body = self._read_json()
                result = self._install(body, upgrade=True, expected_plugin_id=plugin_id)
                self._json(self.application._public_plugin(result))
                return
            if method == 'PUT' and len(segments) == 5 and segments[4] == 'enabled':
                body = self._read_json()
                if set(body) != set(['enabled']) or not isinstance(body['enabled'], bool):
                    raise UsageError("enabled request must contain one boolean field")
                if not body['enabled']:
                    self.application.service.stop_backend(plugin_id)
                operation = self.application.service.enable if body['enabled'] else self.application.service.disable
                result = operation(plugin_id)
                self._json(self.application._public_plugin(self.application.service.info(result['id'])))
                return
            if method == 'PUT' and len(segments) == 5 and segments[4] == 'permissions':
                body = self._read_json()
                if set(body) != set(['permissions']):
                    raise UsageError("permissions request must contain one permissions field")
                result = self.application.service.set_permissions(plugin_id, body['permissions'])
                self._json(self.application._public_plugin(result))
                return
            if method == 'DELETE' and len(segments) == 4:
                purge = _first(query, 'purge_data', 'false').lower()
                if purge not in ('true', 'false'):
                    raise UsageError("purge_data must be true or false")
                self.application.service.stop_backend(plugin_id)
                self._json(self.application.service.uninstall(plugin_id, purge_data=(purge == 'true')))
                return
        if len(segments) >= 5 and segments[:4] == ['api', 'v1', 'sdk', 'tasks']:
            if len(segments) == 5 and method == 'GET':
                self._json(self.application.sdk_task(segments[4]))
                return
            if len(segments) == 6 and segments[5] == 'cancel' and method == 'POST':
                self._json(self.application.sdk_cancel_task(segments[4]), status=HTTPStatus.ACCEPTED)
                return
        if len(segments) == 5 and segments[:4] == ['api', 'v1', 'settings', 'toolchains'] and method == 'DELETE':
            self._json(self.application.remove_toolchain(segments[4]))
            return
        if len(segments) == 5 and segments[:4] == ['api', 'v1', 'settings', 'toolchains'] and method == 'PUT':
            self._json(self.application.update_toolchain(segments[4], self._read_json()))
            return
        self._error(HTTPStatus.NOT_FOUND, 'not_found', 'API endpoint was not found')

    def _install(self, body, upgrade, expected_plugin_id=None):
        allowed = set(['upload_id', 'allow_unsigned'])
        if not isinstance(body, dict) or set(body) - allowed or 'upload_id' not in body:
            raise UsageError("install request must contain upload_id and optional allow_unsigned")
        if not isinstance(body['upload_id'], str) or not body['upload_id']:
            raise UsageError("upload_id must be a non-empty string")
        allow_unsigned = body.get('allow_unsigned', False)
        if not isinstance(allow_unsigned, bool):
            raise UsageError("allow_unsigned must be a boolean")
        package_path = self.application.consume_upload(body['upload_id'])
        try:
            summary = self.application.service.inspect_package(package_path)
            if expected_plugin_id and summary['id'] != expected_plugin_id:
                raise UsageError("upgrade package id does not match the installed plugin")
            operation = self.application.service.upgrade if upgrade else self.application.service.install
            return operation(package_path, allow_unsigned=allow_unsigned)
        finally:
            try:
                os.unlink(package_path)
            except OSError:
                pass

    def _plugin_asset(self, path):
        segments = [unquote(item) for item in path.split('/') if item]
        if len(segments) < 2:
            raise UsageError("invalid plugin resource path")
        plugin_id = segments[1]
        asset = '/'.join(segments[2:]) or None
        target = self.application.service.resolve_webui_asset(plugin_id, asset)
        self._file(target, plugin=True)

    def _is_backend_request(self, path):
        segments = [item for item in path.split('/') if item]
        return (
            (len(segments) >= 3 and segments[0] == 'plugins' and segments[2] == 'backend')
            or (len(segments) >= 5 and segments[0] == 'plugin-assets' and segments[3] == 'backend')
        )

    def _is_backend_path(self, path):
        return path.startswith('/plugins/') or path.startswith('/plugin-assets/')

    def _is_tokenized_backend_request(self, path):
        segments = [unquote(item) for item in path.split('/') if item]
        return (
            len(segments) >= 5
            and segments[0] == 'plugin-assets'
            and segments[3] == 'backend'
            and self.application.plugin_for_asset_token(segments[1]) == segments[2]
            and self._is_backend_request(path)
        )

    def _backend_target(self, parsed):
        segments = [unquote(item) for item in parsed.path.split('/') if item]
        if len(segments) >= 3 and segments[0] == 'plugins' and segments[2] == 'backend':
            plugin_id = segments[1]
            target_parts = segments[3:]
        elif len(segments) >= 5 and segments[0] == 'plugin-assets' and segments[3] == 'backend':
            if self.application.plugin_for_asset_token(segments[1]) != segments[2]:
                raise UsageError('invalid plugin backend path')
            plugin_id = segments[2]
            target_parts = segments[4:]
        else:
            raise UsageError('invalid plugin backend path')
        if not target_parts:
            raise UsageError('invalid plugin backend path')
        target = '/' + '/'.join(target_parts)
        if parsed.query:
            target += '?' + parsed.query
        port = self.application.service.backend_port(plugin_id, self.application.workspace)
        return plugin_id, port, target

    def _plugin_http_proxy(self, method, parsed):
        _plugin_id, port, target = self._backend_target(parsed)
        body = b''
        if method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            body = self._read_body(256 * 1024 * 1024) if self.headers.get('Content-Length') else b''
        headers = {
            'Host': '127.0.0.1:%d' % port,
            'Accept': self.headers.get('Accept', '*/*'),
            'User-Agent': self.headers.get('User-Agent', 'EnvWebUI/1.0'),
        }
        for name in ('Content-Type', 'Content-Length'):
            value = self.headers.get(name)
            if value:
                headers[name] = value
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=30)
        try:
            connection.request(method, target, body=body, headers=headers)
            response = connection.getresponse()
            content = response.read(256 * 1024 * 1024 + 1)
        finally:
            connection.close()
        if len(content) > 256 * 1024 * 1024:
            raise UsageError('backend response exceeds size limit')
        self.send_response(response.status, response.reason)
        for name, value in response.getheaders():
            if name.lower() in ('connection', 'keep-alive', 'transfer-encoding', 'server', 'date'):
                continue
            self.send_header(name, value)
        self.send_header('Content-Length', str(len(content)))
        # Sandboxed plugin iframes have an opaque origin. Chromium can omit the
        # Origin header for a same-URL request from that iframe, while still
        # requiring the response to opt into the serialized `null` origin.
        origin = self.headers.get('Origin')
        if not origin:
            origin = 'null'
        if origin in ('null', 'http://%s' % self.headers.get('Host')):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Credentials', 'true')
            self.send_header('Vary', 'Origin')
        self.end_headers()
        self.wfile.write(content)

    def _plugin_options(self):
        if not self._valid_plugin_origin():
            self._error(HTTPStatus.FORBIDDEN, 'origin_denied', 'plugin request Origin is not allowed')
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header('Access-Control-Allow-Origin', self.headers.get('Origin', 'null'))
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', self.headers.get('Access-Control-Request-Headers', 'content-type'))
        self.send_header('Access-Control-Max-Age', '300')
        self.send_header('Vary', 'Origin')
        self.end_headers()

    def _is_websocket_request(self):
        return self.headers.get('Upgrade', '').lower() == 'websocket'

    def _valid_plugin_origin(self):
        origin = self.headers.get('Origin', '')
        expected = 'http://%s' % self.headers.get('Host')
        return not origin or origin == 'null' or hmac.compare_digest(origin, expected)

    def _plugin_websocket_proxy(self, parsed):
        _plugin_id, port, target = self._backend_target(parsed)
        upstream = socket.create_connection(('127.0.0.1', port), timeout=10)
        upstream.settimeout(None)
        key = self.headers.get('Sec-WebSocket-Key', '')
        if not key:
            upstream.close()
            raise UsageError('WebSocket key is missing')
        request = [
            'GET %s HTTP/1.1' % target,
            'Host: 127.0.0.1:%d' % port,
            'Upgrade: websocket',
            'Connection: Upgrade',
            'Sec-WebSocket-Key: %s' % key,
            'Sec-WebSocket-Version: %s' % self.headers.get('Sec-WebSocket-Version', '13'),
        ]
        for name in ('Sec-WebSocket-Protocol', 'Sec-WebSocket-Extensions'):
            value = self.headers.get(name)
            if value:
                if '\r' in value or '\n' in value:
                    upstream.close()
                    raise UsageError('invalid WebSocket header')
                request.append('%s: %s' % (name, value))
        request.extend(['', ''])
        upstream.sendall('\r\n'.join(request).encode('ascii'))
        response = _read_http_headers(upstream)
        if not response.startswith(b'HTTP/1.1 101') and not response.startswith(b'HTTP/1.0 101'):
            upstream.close()
            raise UsageError('backend WebSocket upgrade failed')
        self.connection.sendall(response)
        self.close_connection = True
        client_to_backend = threading.Thread(target=_relay_stream, args=(self.connection, upstream), daemon=True)
        backend_to_client = threading.Thread(target=_relay_stream, args=(upstream, self.connection), daemon=True)
        client_to_backend.start()
        backend_to_client.start()
        client_to_backend.join()
        try:
            upstream.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        backend_to_client.join(timeout=5)
        upstream.close()

    def _tokenized_plugin_asset(self, path):
        segments = [unquote(item) for item in path.split('/') if item]
        if len(segments) < 3 or self.application.plugin_for_asset_token(segments[1]) != segments[2]:
            self._error(HTTPStatus.NOT_FOUND, 'not_found', 'plugin resource was not found')
            return
        plugin_id = segments[2]
        asset = '/'.join(segments[3:]) or None
        target = self.application.service.resolve_webui_asset(plugin_id, asset)
        self._file(target, plugin=True)

    def _host_asset(self, path):
        relative = 'index.html' if path in ('', '/') else unquote(path.lstrip('/'))
        if '\\' in relative or ':' in relative:
            raise UsageError("invalid static resource path")
        parts = relative.split('/')
        if any(part in ('', '.', '..') for part in parts):
            raise UsageError("invalid static resource path")
        root = os.path.realpath(self.application.static_root)
        target = os.path.realpath(os.path.join(root, *parts))
        if os.path.commonpath([root, target]) != root or not os.path.isfile(target):
            if '.' not in os.path.basename(relative):
                target = os.path.join(root, 'index.html')
            if not os.path.isfile(target):
                self._error(HTTPStatus.NOT_FOUND, 'not_found', 'static resource was not found')
                return
        self._file(target, plugin=False)

    def _file(self, path, plugin=False):
        with open(path, 'rb') as source:
            content = source.read()
        mime = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        self.send_response(HTTPStatus.OK)
        charset = '; charset=utf-8' if mime.startswith(('text/', 'application/javascript')) else ''
        self.send_header('Content-Type', mime + charset)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', 'no-store' if path.endswith('index.html') else 'public, max-age=3600')
        if plugin:
            origin = 'http://%s' % self.headers.get('Host')
            websocket_origin = 'ws://%s' % self.headers.get('Host')
            secure_websocket_origin = 'wss://%s' % self.headers.get('Host')
            self.send_header(
                'Content-Security-Policy',
                "default-src 'none'; script-src %s; style-src %s 'unsafe-inline'; img-src %s data:; "
                "connect-src %s %s %s; frame-ancestors %s; base-uri 'none'; form-action 'none'"
                % (origin, origin, origin, origin, websocket_origin, secure_websocket_origin, origin),
            )
        else:
            self.send_header(
                'Content-Security-Policy',
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'",
            )
        self.end_headers()
        self.wfile.write(content)

    def _valid_host(self):
        value = self.headers.get('Host', '')
        hostname = value
        if value.startswith('['):
            hostname = value[1:].split(']', 1)[0]
        elif ':' in value:
            hostname = value.rsplit(':', 1)[0]
        if hostname.lower() in ('127.0.0.1', 'localhost', '::1'):
            return True
        if not self.application.allow_remote_hosts:
            return False
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            return False
        return True

    def _valid_write_request(self):
        origin = self.headers.get('Origin')
        expected = 'http://%s' % self.headers.get('Host')
        if not origin or not hmac.compare_digest(origin, expected):
            self._error(HTTPStatus.FORBIDDEN, 'origin_denied', 'write request Origin is not allowed')
            return False
        fetch_site = self.headers.get('Sec-Fetch-Site')
        if fetch_site and fetch_site != 'same-origin':
            self._error(HTTPStatus.FORBIDDEN, 'cross_site_denied', 'cross-site write requests are not allowed')
            return False
        csrf = self.headers.get('X-Env-CSRF', '')
        if not hmac.compare_digest(csrf, self.application.csrf_token):
            self._error(HTTPStatus.FORBIDDEN, 'csrf_denied', 'CSRF token is invalid')
            return False
        return True

    def _read_body(self, limit):
        value = self.headers.get('Content-Length')
        if value is None:
            raise UsageError("Content-Length is required")
        try:
            length = int(value)
        except ValueError:
            raise UsageError("Content-Length is invalid")
        if length < 0 or length > limit:
            raise UsageError("request body exceeds size limit")
        content = self.rfile.read(length)
        if len(content) != length:
            raise UsageError("request body is incomplete")
        return content

    def _read_json(self):
        content = self._read_body(JSON_LIMIT)
        try:
            value = json.loads(content.decode('utf-8'))
        except (UnicodeError, ValueError):
            raise UsageError("request body must be valid UTF-8 JSON")
        if not isinstance(value, dict):
            raise UsageError("request JSON must be an object")
        return value

    def _json(self, value, status=HTTPStatus.OK):
        content = json.dumps({'data': value}, ensure_ascii=True, sort_keys=True).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(content)

    def _error(self, status, code, message, details=None):
        error = {'code': code, 'message': message}
        if details:
            error['details'] = details
        content = json.dumps({'error': error}, ensure_ascii=True).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(content)


def _first(query, name, default):
    values = query.get(name)
    return values[0] if values else default


def _read_http_headers(connection):
    content = b''
    while b'\r\n\r\n' not in content and len(content) <= 64 * 1024:
        chunk = connection.recv(4096)
        if not chunk:
            break
        content += chunk
    if b'\r\n\r\n' not in content:
        raise UsageError('backend WebSocket response headers are invalid')
    return content


def _relay_stream(source, destination):
    try:
        while True:
            chunk = source.read(65536) if hasattr(source, 'read') else source.recv(65536)
            if not chunk:
                break
            if hasattr(destination, 'sendall'):
                destination.sendall(chunk)
            else:
                destination.write(chunk)
                destination.flush()
    except (OSError, ValueError):
        pass


def _int_query(query, name, default, minimum, maximum):
    raw = _first(query, name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise UsageError('%s must be an integer' % name)
    if value < minimum or (maximum is not None and value > maximum):
        raise UsageError('%s is out of range' % name)
    return value


class WebUIServer(object):
    def __init__(
        self,
        env_root=None,
        workspace=None,
        host='127.0.0.1',
        port=0,
        static_root=None,
        launcher_dir=None,
        plugin_id=None,
        initial_plugin=None,
    ):
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if host.lower() != 'localhost':
                raise UsageError("WebUI host must be a loopback address or 0.0.0.0")
            allow_remote_hosts = False
        else:
            allow_remote_hosts = address == ipaddress.ip_address('0.0.0.0')
            if not address.is_loopback and not allow_remote_hosts:
                raise UsageError("WebUI host must be a loopback address or 0.0.0.0")
        if int(port) < 0 or int(port) > 65535:
            raise UsageError("WebUI port must be between 0 and 65535")
        if plugin_id is None:
            plugin_id = initial_plugin
        self.application = WebUIApplication(
            env_root=env_root,
            workspace=workspace,
            static_root=static_root,
            launcher_dir=launcher_dir,
            allow_remote_hosts=allow_remote_hosts,
            initial_plugin=plugin_id,
        )
        self.httpd = EnvWebUIHTTPServer((host, int(port)), self.application)
        bound_host, bound_port = self.httpd.server_address[:2]
        if allow_remote_hosts:
            bound_host = _primary_ipv4_address()
        display_host = '[%s]' % bound_host if ':' in bound_host else bound_host
        self.url = 'http://%s:%d/' % (display_host, bound_port)
        self.launch_url = self.url + '_launch/' + self.application.launch_token
        if self.application.initial_plugin:
            self.launch_url += '?plugin=' + quote(self.application.initial_plugin, safe='')
        self.remote_access = allow_remote_hosts
        self._serving = False

    def serve_forever(self):
        self._serving = True
        try:
            self.httpd.serve_forever(poll_interval=0.1)
        finally:
            self._serving = False

    def shutdown(self):
        if self._serving:
            self.httpd.shutdown()
        self.httpd.server_close()
        self.application.close()


def _primary_ipv4_address():
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(('192.0.2.1', 9))
        return probe.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        probe.close()

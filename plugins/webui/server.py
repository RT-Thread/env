"""Local Host API for the Env WebUI."""

from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import ipaddress
import json
import mimetypes
import os
import secrets
import socket
import threading
import time
from urllib.parse import parse_qs, unquote, urlparse

from ..errors import PluginError, StateError, UsageError
from ..service import PluginService
from . import FRONTEND_SDK_VERSION, WEBUI_API_VERSION


SESSION_COOKIE = 'env_webui_session'
UPLOAD_TTL = 15 * 60
JSON_LIMIT = 256 * 1024
PACKAGE_LIMIT = 256 * 1024 * 1024


class WebUIApplication(object):
    def __init__(
        self,
        env_root=None,
        workspace=None,
        static_root=None,
        launcher_dir=None,
        allow_remote_hosts=False,
    ):
        self.service = PluginService(env_root=env_root, launcher_dir=launcher_dir)
        self.service.paths.ensure()
        self.workspace = os.path.abspath(workspace or os.getcwd())
        if not os.path.isdir(self.workspace):
            raise UsageError("WebUI workspace is not a directory: %s" % self.workspace)
        self.static_root = os.path.abspath(static_root or os.path.join(os.path.dirname(__file__), 'static'))
        self.launch_token = secrets.token_urlsafe(32)
        self.session_token = secrets.token_urlsafe(32)
        self.csrf_token = secrets.token_urlsafe(32)
        self.asset_token = secrets.token_urlsafe(32)
        self.allow_remote_hosts = bool(allow_remote_hosts)
        self.uploads = {}
        self.upload_lock = threading.Lock()

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
            summary = self.service.inspect_package(target)
        except Exception:
            os.unlink(target)
            raise
        with self.upload_lock:
            self.uploads[token] = (target, time.monotonic() + UPLOAD_TTL)
        summary['path'] = os.path.basename(filename)
        summary['compatibility_issues'] = []
        summary['upload_id'] = token
        return summary

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

    def do_DELETE(self):
        self._dispatch('DELETE')

    def do_OPTIONS(self):
        self._error(HTTPStatus.FORBIDDEN, 'cross_origin_denied', 'cross-origin requests are not allowed')

    def _dispatch(self, method):
        try:
            if not self._valid_host():
                self._error(HTTPStatus.BAD_REQUEST, 'invalid_host', 'request Host is not allowed')
                return
            parsed = urlparse(self.path)
            if parsed.path.startswith('/_launch/'):
                self._launch(parsed.path)
                return
            if method == 'GET' and parsed.path.startswith('/plugin-assets/'):
                self._tokenized_plugin_asset(parsed.path)
                return
            if not self.application.authenticated(self.headers.get('Cookie')):
                self._error(HTTPStatus.UNAUTHORIZED, 'authentication_required', 'open the URL printed by env webui')
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
        except PluginError as exc:
            status = HTTPStatus.CONFLICT if isinstance(exc, StateError) else HTTPStatus.UNPROCESSABLE_ENTITY
            if isinstance(exc, UsageError):
                status = HTTPStatus.BAD_REQUEST
            self._error(status, exc.__class__.__name__.lower(), str(exc))
        except (ValueError, OSError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, 'invalid_request', str(exc))
        except Exception:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, 'internal_error', 'the WebUI request could not be completed')

    def _launch(self, path):
        token = unquote(path[len('/_launch/'):])
        if not self.application.consume_launch(token):
            self._error(
                HTTPStatus.UNAUTHORIZED,
                'invalid_launch_token',
                'launch URL is invalid or has already been used',
            )
            return
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header('Location', '/')
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
                    'plugin_asset_base': '/plugin-assets/%s/' % self.application.asset_token,
                }
            )
            return
        if method == 'GET' and path == '/api/v1/plugins':
            self._json(self.application.installed())
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
                self._json(self.application.service.uninstall(plugin_id, purge_data=(purge == 'true')))
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

    def _tokenized_plugin_asset(self, path):
        segments = [unquote(item) for item in path.split('/') if item]
        if len(segments) < 3 or not hmac.compare_digest(segments[1], self.application.asset_token):
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
            self.send_header(
                'Content-Security-Policy',
                "default-src 'none'; script-src %s; style-src %s 'unsafe-inline'; img-src %s data:; "
                "connect-src 'none'; frame-ancestors %s; base-uri 'none'; form-action 'none'"
                % (origin, origin, origin, origin),
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

    def _error(self, status, code, message):
        content = json.dumps({'error': {'code': code, 'message': message}}, ensure_ascii=True).encode('utf-8')
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


class WebUIServer(object):
    def __init__(
        self,
        env_root=None,
        workspace=None,
        host='127.0.0.1',
        port=0,
        static_root=None,
        launcher_dir=None,
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
        self.application = WebUIApplication(
            env_root=env_root,
            workspace=workspace,
            static_root=static_root,
            launcher_dir=launcher_dir,
            allow_remote_hosts=allow_remote_hosts,
        )
        self.httpd = EnvWebUIHTTPServer((host, int(port)), self.application)
        bound_host, bound_port = self.httpd.server_address[:2]
        if allow_remote_hosts:
            bound_host = _primary_ipv4_address()
        display_host = '[%s]' % bound_host if ':' in bound_host else bound_host
        self.url = 'http://%s:%d/' % (display_host, bound_port)
        self.launch_url = self.url + '_launch/' + self.application.launch_token
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

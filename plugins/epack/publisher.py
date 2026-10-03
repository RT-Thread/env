"""Publish validated plugin packages to an Env plugin market."""

import http.client
import json
import os
import uuid
from urllib.parse import quote, urlparse

from ..errors import UsageError
from ..market import MarketClient, MarketError, normalize_market_url
from ..package import EpackArchive

if (__package__ or '').startswith('env.'):
    from env import network
else:
    import network


UPLOAD_TIMEOUT = 120
RESPONSE_LIMIT = 1024 * 1024


def _target(client, plugin_id, version):
    try:
        detail = client.plugin_detail(plugin_id)
    except MarketError as exc:
        if exc.status == 404:
            return '/api/v1/admin/plugins', 'plugin'
        raise
    if not isinstance(detail, dict):
        raise MarketError('plugin market returned an invalid plugin detail', status=502)
    root = '/api/v1/admin/plugins/%s' % quote(plugin_id, safe='')
    versions = detail.get('versions') or []
    if any(isinstance(item, dict) and item.get('version') == version for item in versions):
        return '%s/versions/%s/artifacts' % (root, quote(version, safe='')), 'artifact'
    return root + '/versions', 'version'


def _response_error(payload, status):
    message = (payload.get('detail') or payload.get('error')) if isinstance(payload, dict) else None
    if isinstance(message, dict):
        message = message.get('message') or message.get('code')
    if isinstance(message, list):
        message = '; '.join(item.get('msg', '') for item in message if isinstance(item, dict)) or None
    if not isinstance(message, str) or not message:
        message = 'HTTP %d' % status
    return MarketError('plugin market rejected publication: %s' % message, status=status)


def _upload(base_url, target, package_path, changelog, token):
    parsed = urlparse(base_url)
    boundary = 'epack-' + uuid.uuid4().hex
    fields = []
    if changelog is not None:
        fields.append(
            ('--%s\r\nContent-Disposition: form-data; name="changelog"\r\n\r\n%s\r\n' % (boundary, changelog)).encode('utf-8')
        )
    head = (
        '--%s\r\nContent-Disposition: form-data; name="package"; filename="package.epack"\r\n'
        'Content-Type: application/octet-stream\r\n\r\n' % boundary
    ).encode('ascii')
    tail = ('\r\n--%s--\r\n' % boundary).encode('ascii')
    size = os.path.getsize(package_path) + sum(len(field) for field in fields) + len(head) + len(tail)
    path = (parsed.path.rstrip('/') if parsed.path else '') + target

    class MultipartBody(object):
        def __len__(self):
            return size

        def __iter__(self):
            for field in fields:
                yield field
            yield head
            with open(package_path, 'rb') as source:
                while True:
                    chunk = source.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            yield tail

    response = None
    try:
        headers = {'Content-Type': 'multipart/form-data; boundary=%s' % boundary, 'Accept': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        response = network.request(
            'POST', '%s://%s%s' % (parsed.scheme, parsed.netloc, path),
            headers=headers, data=MultipartBody(), timeout=UPLOAD_TIMEOUT, stream=True, allow_redirects=False,
        )
        content = response.raw.read(RESPONSE_LIMIT + 1, decode_content=True)
        if len(content) > RESPONSE_LIMIT:
            raise MarketError('plugin market returned an oversized response', status=502)
        try:
            payload = json.loads(content.decode('utf-8')) if content else {}
        except (UnicodeError, ValueError):
            raise MarketError('plugin market returned invalid JSON', status=502)
        if not 200 <= response.status_code < 300:
            raise _response_error(payload, response.status_code)
        if not isinstance(payload, dict):
            raise MarketError('plugin market returned an invalid response', status=502)
        return payload
    except (OSError, http.client.HTTPException) as exc:
        raise MarketError('plugin market upload failed (%s)' % type(exc).__name__, status=502)
    finally:
        if response is not None:
            response.close()


def push_package(package_path, market_url, changelog=None, token=None):
    _validate_token(token)
    base_url = normalize_market_url(market_url)
    summary = EpackArchive(package_path).inspect().summary()
    target, action = _target(MarketClient(base_url), summary['id'], summary['version'])
    if action == 'artifact' and changelog is not None:
        raise UsageError('changelog cannot be changed when adding an artifact to an existing version')
    response = _upload(base_url, target, package_path, changelog, token)
    return {
        'status': 'ok',
        'action': action,
        'market': base_url,
        'id': summary['id'],
        'version': summary['version'],
        'package': package_path,
        'response': response,
    }


def _validate_token(token):
    if not token:
        return
    try:
        token.encode('ascii')
    except UnicodeEncodeError:
        raise UsageError('market token must contain only ASCII characters')
    if '\r' in token or '\n' in token:
        raise UsageError('market token must be a single line')

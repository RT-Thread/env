# `.epack` v1

An `.epack` v1 file is a ZIP container with UTF-8 POSIX relative member names.
It contains exactly one `manifest.json`, one `integrity.json`, a license file,
optional backend wheels, optional `frontend/` resources, and build metadata.

Every regular member except `integrity.json` is listed in
`integrity.json.files` by its SHA-256 digest. Unlisted, missing, duplicate,
case-colliding, encrypted, symbolic-link, unsafe Windows or path-traversing
members are rejected. V1 packages are unsigned; packages carrying signature
material are rejected until a verifiable signature profile is defined.

The manifest contract is defined by `manifest-v1.schema.json`. Runtime checks
add constraints not expressible in the schema:

- permission and command names must be unique;
- `workspace.write` and `workspace.read` cannot both be declared;
- commands, health checks and services require exactly one artifact with the `plugin` role;
- WebUI-only plugins can omit backend artifacts, and CLI-only plugins can omit `webui`;
- `source-wheel` uses a `py3` wheel tag;
- `pyc-wheel` uses an exact declared CPython tag and matching bytecode magic;
- command, health-check and service entry modules must load from the installed backend;
- `webui.entry` names an HTML file below `frontend/`, with no source maps or links;
- a plugin declares at least one command, WebUI page, health check, or service.

Plugin commands use this ABI:

```python
def main(argv, context):
    return 0
```

`argv` excludes the executable name. `context` is
`env.plugins.sdk.RuntimeContext`. Returning `None` means success; an integer is
used as the process exit status.

Plugin WebUI declarations use this shape:

```json
{
  "webui": {
    "entry": "frontend/index.html",
    "icon": "chart-no-axes-combined",
    "frontend_sdk": ">=1.0.0,<2.0.0",
    "keep_alive": false
  }
}
```

`keep_alive` is optional and defaults to `false`. When set to `true`, Env keeps
the plugin iframe mounted while navigating between WebUI pages, preserving
browser-local page state. It is released when the plugin is disabled, upgraded,
uninstalled, or the WebUI exits.

Plugins that provide a long-running local HTTP/WebSocket backend may declare a
supervised service:

```json
{
  "service": {
    "entry": "package.service:create_service",
    "health_path": "/health",
    "start_timeout": 15
  }
}
```

The entry is called as `entry(context, host, port)` in a child process. `context`
is an `env.plugins.sdk.RuntimeContext`, and the callable must return an ASGI
application (or an object with an `app` attribute):

```python
def create_service(context, host, port):
    return app
```

Env starts the service on the first backend request, checks `health_path`, binds
it to a random loopback port, and proxies requests from
`/plugins/<id>/backend/`. Plugin asset pages may use the tokenized
`/plugin-assets/<token>/<id>/backend/` equivalent returned by the WebUI session
API. The tokenized prefix is bound to the plugin ID. `health_path` must be an
absolute safe HTTP path, and `start_timeout` must
be an integer from 1 to 60 seconds. The service runner uses Uvicorn, so
`uvicorn` and its runtime dependencies must be available as backend dependency
wheels. The process is stopped when the plugin is disabled, upgraded,
uninstalled, or the WebUI exits.

Frontend files are prebuilt. Env installs them in the same version transaction
as backend wheels and serves only the active, enabled, authorized version.

The host context is versioned and may include `httpBase`, `websocketBase` and a
list of transport features. Env does not interpret plugin business messages;
future device, tool and debugger protocols are plugin-owned extensions.

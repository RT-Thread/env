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
- commands and health checks require exactly one artifact with the `plugin` role;
- WebUI-only plugins can omit backend artifacts, and CLI-only plugins can omit `webui`;
- `source-wheel` uses a `py3` wheel tag;
- `pyc-wheel` uses an exact declared CPython tag and matching bytecode magic;
- command and health-check modules must load from the installed backend.
- `webui.entry` names an HTML file below `frontend/`, with no source maps or links;
- a plugin declares at least one command, WebUI page, or health check.

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
    "frontend_sdk": ">=1.0.0,<2.0.0"
  }
}
```

Frontend files are prebuilt. Env installs them in the same version transaction
as backend wheels and serves only the active, enabled, authorized version.

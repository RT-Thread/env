# Env plugins

For the Chinese documentation, see [README.zh-CN.md](README.zh-CN.md).

RT-Thread Env is a command-line toolkit for RT-Thread development. This
directory contains its plugin lifecycle, command runtime and local WebUI.
Plugins are imported from local `.epack` files. Env validates, installs,
upgrades, enables, disables, diagnoses and uninstalls them. CLI and browser
operations share the same state and `PluginService` facade.

The local lifecycle still installs from `.epack` files. An optional plugin
market URL can be configured; when it is present, the WebUI shows an online
catalog and downloads a matching artifact through the local Host API. Env
never installs from a raw plugin id or URL.

## Layout

- `manifest.py`, `package.py`: strict `.epack` v1 manifest, archive and integrity checks.
- `installer.py`, `store.py`, `launchers.py`: transactional lifecycle state and command launchers.
- `dispatcher.py`, `sdk/`: mandatory command dispatch and plugin runtime context.
- `epack/`: plugin project initialization, validation, build and package inspection.
- `market.py`: optional plugin market URL and Host API client.
- `webui/`: local Host API, Vue source and prebuilt host assets.
- `bundled/epack/`: source project for the optional official `epack` developer tool.
- `examples/`: CLI-only, WebUI-only and combined example plugin projects.
- `spec/`: the `.epack` v1 package format and `manifest.json` contract.
- `tests/`: lifecycle, rollback, security and end-to-end coverage.

## Package format

An `.epack` is a ZIP archive with a fixed manifest and an integrity inventory.
A typical package contains:

```text
org.example.demo-1.0.0-py3-none-any.epack
|-- manifest.json
|-- integrity.json
|-- licenses/LICENSE
|-- build/build.json
`-- backend/org_example_demo-1.0.0-py3-none-any.whl
```

`manifest.json` declares the plugin ID, name, version and compatibility, plus
permissions and the applicable command, WebUI, health-check, service and
backend artifact entries. A command entry uses `module.path:callable` syntax
and implements:

```python
def main(argv, context):
    return 0
```

The builder creates the backend wheel, build metadata and `integrity.json`.
Env checks package integrity, Env/Python compatibility, command conflicts and
required permissions during installation and execution.

See [`spec/README.md`](spec/README.md) for the complete package contract.

## Installing a plugin

After activating Env, the installed command is normally `rt-env`:

```bash
source ~/.env/env.sh
rt-env plugin install /path/to/plugin.epack --yes
```

From an Env source checkout, use the equivalent command:

```bash
python env.py plugin install /path/to/plugin.epack --yes
```

V1 packages do not have a verifiable signature profile yet. Interactive
installation displays the package identity, permissions and unsigned warning
before asking for confirmation. Use `--yes` in automation or non-interactive
environments.

For every command declared in `manifest.json`, Env creates a launcher. For
example, a command named `env-build-insight` can be run directly:

```bash
env-build-insight
```

Common lifecycle operations are:

```bash
rt-env plugin list
rt-env plugin info org.example.demo
rt-env plugin doctor org.example.demo
rt-env plugin disable org.example.demo
rt-env plugin enable org.example.demo
rt-env plugin update /path/to/plugin-1.1.0.epack --yes
rt-env plugin uninstall org.example.demo --yes
rt-env plugin market
rt-env plugin market set http://127.0.0.1:8800
rt-env plugin market clear
```

`ENV_PLUGIN_MARKET_URL` overrides `${ENV_ROOT}/var/plugins/market.json`.
Without a configured URL, the WebUI hides the online plugin page.

Add `--purge-data` to uninstall a plugin and remove its private configuration,
data and cache. Workspace files are never removed by the uninstall workflow.

Plugin state is stored under `${ENV_ROOT}/var/plugins/` by default:

```text
var/plugins/
|-- state-v1.json
|-- installed/<plugin-id>/<version>/
|-- config/<plugin-id>/
|-- data/<plugin-id>/
|-- cache/<plugin-id>/
|-- runtime/
`-- staging/
```

## Installing and using `epack`

`epack` (RT-Thread Env Plugin Development Kit) is the official optional tool for developing and publishing
other Env plugins. It is not required to install or run an existing `.epack`
plugin; it is only needed for the developer workflow.

Build and install the official `epack` plugin from an Env source checkout:

```bash
python -m plugins.epack.cli build plugins/bundled/epack
python env.py plugin install \
    plugins/bundled/epack/dist/org.rt-thread.epack-1.1.0-py3-none-any.epack \
    --yes
```

For a shorter source-checkout command, use the helper under `plugins/epack/`:

```bash
python plugins/epack/build_epack.py
```

It builds the same package into `plugins/bundled/epack/dist/` by default. Use
`-o/--output` to select another directory, `--backend-format` to override the
wheel format, or `--json` for automation. The helper only builds the package;
installation remains an explicit Env operation.

The build command writes the package to `plugins/bundled/epack/dist/` by
default. After installation, the `epack` launcher is available:

```bash
epack --help
```

If `epack` has not been installed, run `python -m plugins.epack.cli` from the
source checkout. It exposes the same commands as the installed `epack`
launcher.

## Creating a plugin with `epack`

### Initialize a project

```bash
epack init demo \
    --id org.example.demo \
    --name Demo
```

This creates `manifest.json`, a license, a Python package under `src/` and a
minimal command entry point. The target directory must be empty. Plugin IDs
use lowercase reverse-domain notation, such as `org.example.demo`.

When `epack init <directory>` is run in a TTY without initialization metadata
options, it opens an interactive wizard. Press Enter to accept each default:

```text
Plugin ID       [org.example.demo]:
Plugin name     [Demo]:
Version         [0.1.0]:
Description     [Demo Env plugin]:
Author          [Plugin Author]:
Register a command? [Y/n]:
Create a WebUI page? [y/N]:
```

The wizard validates each value and asks again when the input is invalid. It is
not started for non-TTY calls or when any initialization option is provided. A
command is generated and registered by default; a WebUI page is not generated
by default. A project must provide at least one of these capabilities. This
makes scripted initialization deterministic:

```bash
epack init demo \
    --id org.example.demo \
    --name Demo \
    --version 0.1.0 \
    --description "Demo Env plugin" \
    --author "Plugin Author" \
    --with-command
```

Capability options can be used without the wizard. Use `--without-command` or
`--with-command` to control command generation, and `--without-webui` or
`--with-webui` to control the WebUI scaffold. For example, a WebUI-only
project is created with:

```bash
epack init demo-web --without-command --with-webui
```

The command capability creates `src/<module>/`, `cli.py` and a test skeleton,
and adds a plugin wheel and command entry to `manifest.json`. The WebUI
capability creates `frontend/index.html` and adds `manifest.webui`. Selecting
both creates a combined project.

### Implement the plugin and manifest

Implement the command in `src/org_example_demo/`. The entry function receives
the command arguments and a `RuntimeContext`. If the plugin needs workspace,
process, network or device access, declare the corresponding permission in
`manifest.json`. The SDK enforces workspace boundaries, but plugins still run
as the current user and are not a malicious-code sandbox.

A minimal CLI plugin project normally contains:

```text
demo/
|-- manifest.json
|-- LICENSE
`-- src/org_example_demo/
    |-- __init__.py
    `-- cli.py
```

### Validate, build and inspect

```bash
epack validate demo
epack build demo -o dist
epack inspect dist/org.example.demo-0.1.0-py3-none-any.epack
```

`epack build` creates a `source-wheel` package by default. To create a
bytecode package for the current CPython ABI, use:

```bash
epack build demo -o dist --backend-format pyc-wheel
```

### Test and publish

`epack test` builds a project and installs it into a temporary Env root. A
WebUI plugin opens in a foreground test server; stop it with Ctrl+C. A CLI-only
plugin runs its sole command. Choose a command explicitly when needed and put
its arguments after `--`:

```bash
epack test demo
epack test demo --command org-example-demo -- --help
epack test demo-web --no-browser
epack test demo-web -g
```

Use `-g` or `--global` to listen on all IPv4 interfaces when testing a WebUI,
as with `webui -g`.

The temporary installation is removed when testing exits. It does not replace
the installed plugin. Plugin code still runs as the current user in the chosen
workspace.

`epack push` (also `epack publish`) builds a project (or accepts an existing `.epack`), checks package
integrity, and uploads it to the market configured by `rt-env plugin market set`.
Use `--market` to override the URL. The market admin API requires a bearer token
when authentication is enabled; put it in a local file and use `--token-file`.
The configured market must support the admin publish endpoints.

```bash
rt-env plugin market set http://127.0.0.1:8800
epack push demo --token-file ./market-token.txt --changelog "Initial release"
epack push dist/org.example.demo-0.1.0-py3-none-any.epack --market http://127.0.0.1:8800
```

The first upload creates the plugin; later uploads create a version or add an
artifact to an existing version. `--changelog` applies only to a new plugin or
version. Publication is a remote operation and does not install the package.

Use `epack inspect` to check the manifest and integrity without executing code
from the package. Install the result through Env and run its registered
command:

```bash
rt-env plugin install \
    dist/org.example.demo-0.1.0-py3-none-any.epack \
    --yes
org-example-demo
```

### WebUI plugins

A WebUI page is declared by `manifest.webui` and provided as prebuilt static
files under `frontend/`:

```json
{
  "webui": {
    "entry": "frontend/index.html",
    "icon": "puzzle",
    "frontend_sdk": ">=1.0.0,<2.0.0",
    "keep_alive": false,
    "launch_requirements": {
      "all": [
        {"type": "file", "pattern": "rtconfig.py"},
        {"any": [
          {"type": "directory", "pattern": "test_*"},
          {"type": "file", "pattern": "test_*.md"}
        ]}
      ]
    }
  }
}
```

`keep_alive` is optional and defaults to `false`. Set it to `true` when the
plugin should keep its iframe mounted while navigating between WebUI pages,
preserving browser-local page state. The iframe is released when the plugin is
disabled, upgraded, uninstalled, or the WebUI exits.

The `icon` can also reference an image bundled below `frontend/`:

```json
{
  "icon": {"type": "svg", "path": "frontend/icon.svg"}
}
```

`type` supports `svg` and `png`; the declared file is included in the `.epack`
and is used consistently in the sidebar, plugin center and plugin dialogs.

`launch_requirements` is optional. It describes files or directories that must
exist below the current workspace for the plugin to appear in the left
navigation. `pattern` accepts a safe POSIX-relative path or glob, and `file` or
`directory` restricts the match type. Combine conditions with `all`, `any` and
`not`. A plugin whose conditions are not satisfied remains available from the
plugin center and can still be opened there.

A WebUI-only plugin may omit `src/` and backend wheels. A plugin that declares
commands, a health check, or a `service` must provide exactly one backend
artifact with the `plugin` role. After installation, start the local WebUI with:

```bash
webui start
```

`webui start` starts the local service in the background, opens the browser by
default for a local session, prints the launch URL and returns to the command
line. Use the lifecycle commands to inspect or stop that service:

```bash
webui status
webui stop
```

Starting an already running service prints its existing URL and does not start
a second server. The service state is kept under
`${ENV_ROOT}/var/plugins/runtime/`. The legacy `webui [workspace]` form remains
available when a foreground process is desired. Use `--no-browser` to suppress
browser launch, or `--browser` to force it in an SSH session. To enter an
installed and enabled WebUI plugin directly after startup, pass
`--plugin <plugin-id>` (also supported as `webui <plugin-id>` and with
`webui start`); without it, the project home is shown.

The WebUI Settings page includes Network. It stores the policy under
`${ENV_ROOT}/var/network.json` and supports system proxy, direct connection,
custom HTTP(S) proxy, bypass hosts, GitHub/Gitee download selection, PyPI
selection, and request timeout. Settings are process-local: Env does not
rewrite global Git, pip, or shell configuration. `ENV_PYPI_INDEX_URL` remains
the highest-priority PyPI override. In a VS Code terminal, Env first tries the
editor URL opener; if that is unavailable, it keeps the launch URL available
for manual opening instead of starting a browser on a remote SSH host.

This also applies to terminals opened through VS Code Remote SSH. Env uses
the VS Code Server browser helper or Remote CLI to hand the launch URL to
the connected VS Code client. It does not require `code` on PATH when the
helper is available, and a failed bridge does not start a remote system browser.
To prefer the integrated browser, enable `workbench.browser.openLocalhostLinks`
in VS Code. Remote access uses VS Code's URL and port-forwarding mechanism;
Env does not change editor settings or expose the service on additional interfaces.
`--no-browser` skips this attempt; `--browser` explicitly uses the system browser.

Plugin pages run in an iframe without `allow-same-origin`. The host passes theme,
language, plugin identity, protocol version and optional backend URLs through
versioned `postMessage` messages. Pages cannot read host cookies or sessions, or
call Env lifecycle APIs. See the complete
[`build-insight` example](examples/build-insight-1.0.0/README.md).

A plugin that needs a local HTTP or WebSocket backend may declare a `service`
entry in its manifest. Env invokes the entry as `entry(context, host, port)`;
`context` is a `RuntimeContext`, and the callable must return an ASGI
application or an object with an `app` attribute:

```python
def create_service(context, host, port):
    return app
```

The service starts on the first backend request. Env loads it in a supervised
child process, checks `health_path`, binds it to a random loopback port, and
proxies `/plugins/<id>/backend/` to it. Plugin asset pages may use the
tokenized `/plugin-assets/<token>/<id>/backend/` equivalent returned by the
WebUI session API. `health_path` must be an absolute safe HTTP path, and
`start_timeout` must be an integer from 1 to 60 seconds. The service runner
uses Uvicorn, so `uvicorn` and its runtime dependencies must be available as
backend dependency wheels. The process is stopped when the plugin is disabled,
upgraded, uninstalled, or the WebUI exits.

The session API returns a separate tokenized asset prefix for each enabled
plugin. A plugin with a backend receives HTTP and WebSocket paths below its own
prefix; a WebUI-only plugin receives `backend: null`:

```json
{
  "base": "/plugin-assets/<token>/<plugin-id>/",
  "backend": {
    "http_base": "/plugin-assets/<token>/<plugin-id>/backend/",
    "websocket_base": "/plugin-assets/<token>/<plugin-id>/backend/"
  }
}
```

Env provides transport and backend lifecycle only. Plugin authors may define
request, event, cancellation, progress and binary-frame protocols over
WebSocket; device and debugger semantics remain plugin-owned extensions rather
than Env Host API methods.

## Project Home Documents

When starting `webui` (including `webui -g`) in a project directory, the project
home prefers `index.md`, then `README.md` or `readme.md`. Documents use UTF-8,
with an optional BOM. The build panel appears above the document while a task
exists and disappears after acknowledging its result.
The home document renders directly, without a filename or refresh toolbar.

Put `[toc]` on its own paragraph to generate a nested table of contents with
clickable heading links. The marker is case-insensitive (`[TOC]` also works),
and is not expanded inside code. Directory colors follow the WebUI theme.

GitHub-style rendering supports heading anchors, tables, task lists, emoji,
HTML tables with `rowspan`/`colspan`, and syntax highlighting. Document styles,
code colors and diagrams follow the WebUI theme. SVG, PNG, JPEG, GIF and WebP
images resolve relative to the referring file. Project Markdown links render
in the same home view and support browser history. Local SVG links also work;
for example, `images/architecture.svg` can link to `../docs/guide.md#details`.
SVG scripts are removed and its styles cannot affect the host UI.

Use fenced `mermaid` blocks for local browser rendering and `plantuml`, `puml`
or `uml` blocks for online rendering through
`https://www.plantuml.com/plantuml/svg/`. **PlantUML sends diagram source to an
external service and needs network access. Use local Mermaid for sensitive
diagrams.** Failed diagrams retain their source without affecting the page.

Only project `.md` files and images are accessible. Hidden paths, traversal and
symlinks outside the workspace are rejected. Markdown is limited to 4 MiB and
individual images to 16 MiB.

## Build and publishing notes

- Command names in `manifest.json` must be unique and must not conflict with an existing system or plugin command.
- `workspace.write` already includes read access; do not declare `workspace.read` with it.
- If dependency wheels are declared, place them under the project `wheels/` directory at the paths listed in the manifest.
- Service backends require `uvicorn` and its runtime dependencies to be included as dependency wheels.
- Frontend resources must be prebuilt and must not contain source maps, symbolic links or path-traversal members.
- V1 packages are currently unsigned local artifacts. Do not make `--yes` the default policy for packages from untrusted sources.
- The WebUI shows the online catalog only when a market URL is configured. Installation still uses a one-time local upload id after the Host API downloads and inspects the artifact.

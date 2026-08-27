# Env plugins

For the Chinese documentation, see [README.zh-CN.md](README.zh-CN.md).

This directory contains the Env plugin lifecycle, command runtime and local
WebUI. Plugins are imported from local `.epack` files. Env validates, installs,
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

`epack` is the official optional developer tool for creating and publishing
other Env plugins. It is not required to install or run an existing `.epack`
plugin; it is only needed for the developer workflow.

Build and install the official `epack` plugin from an Env source checkout:

```bash
python -m plugins.epack.cli build plugins/bundled/epack
python env.py plugin install \
    plugins/bundled/epack/dist/org.rt-thread.epack-1.0.0-py3-none-any.epack \
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
    "frontend_sdk": ">=1.0.0,<2.0.0"
  }
}
```

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
browser launch, or `--browser` to force it in an SSH session.

Plugin pages run in an iframe without `allow-same-origin`. The host passes theme
and language through versioned `postMessage` messages. Pages cannot read host
cookies or sessions, or call Env lifecycle APIs. See the complete
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

## Build and publishing notes

- Command names in `manifest.json` must be unique and must not conflict with an existing system or plugin command.
- `workspace.write` already includes read access; do not declare `workspace.read` with it.
- If dependency wheels are declared, place them under the project `wheels/` directory at the paths listed in the manifest.
- Service backends require `uvicorn` and its runtime dependencies to be included as dependency wheels.
- Frontend resources must be prebuilt and must not contain source maps, symbolic links or path-traversal members.
- V1 packages are currently unsigned local artifacts. Do not make `--yes` the default policy for packages from untrusted sources.
- The WebUI shows the online catalog only when a market URL is configured. Installation still uses a one-time local upload id after the Host API downloads and inspects the artifact.

# Env plugins

This directory contains the Env plugin lifecycle and the local phase-two
WebUI. CLI and browser operations share the same service and state.

## Layout

- `manifest.py`, `package.py`: strict `.epack` v1 parsing and integrity checks.
- `installer.py`, `store.py`, `launchers.py`: transactional lifecycle state.
- `dispatcher.py`, `sdk/`: mandatory command dispatch and runtime SDK.
- `epack/`: project scaffolding, validation, build and static inspection.
- `webui/`: local Host API, Vue source and prebuilt host assets.
- `bundled/epack/`: source project for the optional official `epack` plugin.
- `examples/`: CLI-only, WebUI-only and combined example plugin projects.
- `spec/`: the frozen package and manifest contract.
- `tests/`: unit, security, rollback and end-to-end coverage.

## Bootstrap

Build and install the optional developer tool from an Env source checkout:

```text
python -m plugins.epack.cli build plugins/bundled/epack
python env.py plugin install plugins/bundled/epack/dist/org.rt-thread.epack-1.0.0-py3-none-any.epack
```

After confirmation, use the direct `epack` command. Removing `epack` does not
remove or disable Env's lifecycle installer.

## Local WebUI

Start the production WebUI from any workspace:

```text
webui
webui -g
webui -g --browser
webui /path/to/workspace --no-browser

# Source checkout equivalents
python env.py webui
python env.py webui /path/to/workspace --no-browser
python env.py webui -g --no-browser
```

The Env Python virtual environment installs `webui` as a direct command. The
default listener is loopback-only. Passing `-g` or `--global` listens on every
IPv4 interface, equivalent to `--host 0.0.0.0`, and prints a reachable
local-network URL. The launch token, session, CSRF, Origin and Host protections
remain enabled, but traffic is unencrypted HTTP and should only be exposed on
a trusted network.

Env opens the default browser automatically for local sessions. When
`SSH_CONNECTION`, `SSH_CLIENT`, or `SSH_TTY` indicates an SSH session, it keeps
the server running but skips browser launch. Use `--browser` to force browser
launch or `--no-browser` to disable it explicitly.

The server binds to an automatically selected loopback port, prints a one-time
launch URL, and stops on Ctrl+C. Runtime use does not require Node.js or a CDN.
Node.js is only needed to rebuild the checked-in host assets:

```text
cd plugins/webui/frontend
npm ci
npm test
npm run build
npm run test:e2e
```

The open source WebUI only installs or upgrades packages selected from the
local filesystem. It does not query a catalog, accept package URLs, or download
plugins. A future online marketplace is a separate private service and is not
implemented or specified in this repository.

## Plugin pages

A plugin page is declared by `manifest.webui` and built into `frontend/` in the
`.epack`. Installed pages run in an iframe without `allow-same-origin`. The host
passes theme and language through versioned `postMessage` messages; plugin
pages cannot call lifecycle APIs, read the host session, or use terminal and
task capabilities.

# Build Insight WebUI plugin example

Build Insight is a complete Env plugin example with both a sandboxed WebUI page
and the `env-build-insight` CLI command. It demonstrates the phase-two package
layout without requiring Node.js or external frontend dependencies.

## Project layout

- `manifest.json`: plugin identity, compatibility, permissions, CLI and WebUI declarations.
- `frontend/index.html`: WebUI entry served by the Env host.
- `frontend/plugin.js`: versioned `postMessage` handshake with the host.
- `frontend/styles.css`: responsive light and dark theme styles.
- `src/rt_env_build_insight/`: CLI entry and health check.
- `LICENSE`: license copied into the package.

The iframe sends `env.host.ready` after loading. Env replies with
`env.host.context`, which contains the plugin id, frontend SDK version, theme
and language. The example uses the theme value and does not access host cookies
or lifecycle APIs.

## Validate and build

Run these commands from the repository root:

```text
python -m plugins.epack.cli validate plugins/examples/build-insight-1.0.0
python -m plugins.epack.cli build plugins/examples/build-insight-1.0.0 -o plugins/examples/prebuilt
python -m plugins.epack.cli inspect plugins/examples/prebuilt/org.rt-thread.build-insight-1.0.0-py3-none-any.epack
```

The builder creates a deterministic `.epack` containing the generated backend
wheel, static frontend resources, manifest, license and integrity inventory.

## Install locally

```text
python env.py plugin install plugins/examples/prebuilt/org.rt-thread.build-insight-1.0.0-py3-none-any.epack --yes
python env.py plugin doctor org.rt-thread.build-insight
python env.py webui --plugin org.rt-thread.build-insight
```

The package is unsigned, so interactive installation asks for confirmation.
`--yes` is suitable for the documented local example only. After startup, open
the Build Insight WebUI directly. Running `python env.py webui` without a
plugin target opens the plugin center.

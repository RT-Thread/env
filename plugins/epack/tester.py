"""Run a plugin from a temporary Env installation."""

import os
import subprocess
import tempfile
import webbrowser

from ..errors import UsageError
from ..package import EpackArchive
from ..service import PluginService


def _select_command(summary, command, command_args):
    names = [entry['name'] for entry in summary['commands']]
    if command and command not in names:
        raise UsageError('plugin does not provide command: %s' % command)
    if not command and command_args:
        raise UsageError('command arguments require --command')
    if command or summary['webui']:
        return command
    if len(names) != 1:
        if not names:
            raise UsageError('plugin does not provide a command or WebUI')
        raise UsageError('select one of the plugin commands with --command: %s' % ', '.join(names))
    return names[0]


def test_package(package_path, workspace, command=None, command_args=(), no_browser=False, host='127.0.0.1', port=0):
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise UsageError('WebUI port must be an integer')
    if not 0 <= port <= 65535:
        raise UsageError('WebUI port must be between 0 and 65535')
    summary = EpackArchive(package_path).inspect().summary()
    command = _select_command(summary, command, command_args)

    with tempfile.TemporaryDirectory(prefix='epack-test-') as env_root:
        service = PluginService(env_root=env_root, check_host_path=False)
        service.install(package_path, allow_unsigned=True)
        if command:
            launcher = service.installer.launchers.path(command)
            environment = dict(os.environ)
            environment['ENV_ROOT'] = env_root
            process = subprocess.run([launcher] + list(command_args), cwd=workspace, env=environment)
            return process.returncode

        from ..webui.server import WebUIServer

        server = WebUIServer(env_root=env_root, workspace=workspace, plugin_id=summary['id'], host=host, port=port)
        try:
            print('Test WebUI: %s' % server.url, flush=True)
            print('Launch URL: %s' % server.launch_url, flush=True)
            if not no_browser:
                webbrowser.open(server.launch_url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
        finally:
            server.shutdown()
    return 0

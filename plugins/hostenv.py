"""Host process environment that plugin subprocesses may inherit."""

import os


HOST_ENVIRONMENT_NAMES = frozenset(
    [
        'ALLUSERSPROFILE',
        'APPDATA',
        'COMMONPROGRAMFILES',
        'COMMONPROGRAMFILES(X86)',
        'COMPUTERNAME',
        'COMSPEC',
        'ENV_ROOT',
        'HOME',
        'HOMEDRIVE',
        'HOMEPATH',
        'LANG',
        'LC_ALL',
        'LOCALAPPDATA',
        'LOGNAME',
        'NUMBER_OF_PROCESSORS',
        'OS',
        'PATH',
        'PATHEXT',
        'PROCESSOR_ARCHITECTURE',
        'PROCESSOR_IDENTIFIER',
        'PROGRAMDATA',
        'PROGRAMFILES',
        'PROGRAMFILES(X86)',
        'PUBLIC',
        'SYSTEMDRIVE',
        'SYSTEMROOT',
        'TEMP',
        'TERM',
        'TMP',
        'TMPDIR',
        'USER',
        'USERDOMAIN',
        'USERNAME',
        'USERPROFILE',
        'WINDIR',
    ]
)


def copy_host_environment(extra=None):
    allowed = set(name.upper() for name in HOST_ENVIRONMENT_NAMES)
    environment = {}
    for name, value in os.environ.items():
        if name.upper() in allowed:
            environment[name] = value
    if extra:
        environment.update(extra)
    return environment

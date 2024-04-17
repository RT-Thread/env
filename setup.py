import platform
from setuptools import setup, find_packages

if platform.system() == "Windows":
    need_windows_curses = ["windows-curses"]
else:
    need_windows_curses = []


setup(
    name='env',
    version='0.0.1',
    description='RT-Thread Env',
    url='https://github.com/RT-Thread/env',
    author='RT-Thread Development Team',
    author_email='rt-thread@rt-thread.org',
    license='Apache License 2.0',
    keywords='rt-thread',
    consoles=[{'env': 'env.py'}],
    install_requires=['SCons>=4.0.0', 'requests', 'psutil', 'kconfiglib'] + need_windows_curses,
    packages=find_packages(include=[], exclude=['cmds', 'sdk', 'test', '__pycache__']),
    data_files= [('Lib/site-packages/env', ['env.py',
                                            'package.py',
                                            'archive.py',
                                            'kconfig.py',
                                            'statistics.py',
                                            'vars.py',
                                            'pkgsdb.py',
                                            'LICENSE',
                                            'README.md']),
                 ('Lib/site-packages/env/cmds', ['cmds/__init__.py',
                                                 'cmds/cmd_menuconfig.py',
                                                 'cmds/cmd_sdk.py',
                                                 'cmds/cmd_system.py',
                                                 'cmds/Kconfig']),
                 ('Lib/site-packages/env/cmds/cmd_package', [
                     'cmds/cmd_package/__init__.py',
                     'cmds/cmd_package/cmd_package_list.py',
                     'cmds/cmd_package/cmd_package_printenv.py',
                     'cmds/cmd_package/cmd_package_update.py',
                     'cmds/cmd_package/cmd_package_upgrade.py',
                     'cmds/cmd_package/cmd_package_utils.py',
                     'cmds/cmd_package/cmd_package_wizard.py'])],
    python_requires='>=3.6',
    entry_points={
        'console_scripts': [
            'env=env.env:main',
            'menuconfig=env.env:menuconfig',
            'pkgs=env.env:pkgs',
            'sdk=env.env:sdk',
            'system=env.env:system',
        ]
    }
)

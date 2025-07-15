from setuptools import setup
from version import get_rt_env_version

env_name, env_ver = get_rt_env_version()
setup(
    name='env',
    version=env_ver,
    description=env_name,
    url='https://github.com/RT-Thread/env.git',
    author='RT-Thread Development Team',
    author_email='rt-thread@rt-thread.org',
    keywords='rt-thread',
    license='Apache License 2.0',
    project_urls={
        'Github repository': 'https:/github.com/rt-thread/env.git',
        'User guide': 'https:/github.com/rt-thread/env.git',
    },
    python_requires='>=3.6',
    install_requires=[
        'SCons>=4.0.0',
        'requests',
        'psutil',
        'tqdm',
        'kconfiglib',
        'windows-curses; platform_system=="Windows"',
    ],
    packages=[
        'env',
        'env.cmds',
        'env.cmds.cmd_package',
    ],
    package_dir={
        'env': '.',
        'env.cmds': 'cmds',
        'env.cmds.cmd_package': 'cmds/cmd_package',
    },
    package_data={'': ['*.*']},
    exclude_package_data={'': ['MANIFEST.in']},
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'rt-env=env.env:main',
            'menuconfig=env.env:menuconfig',
            'pkgs=env.env:pkgs',
            'sdk=env.env:sdk',
            'system=env.env:system',
        ]
    },
)

from setuptools import setup
import sys
import os

# Add current directory to path for version module discovery
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from version import get_rt_env_version
    env_name, env_ver = get_rt_env_version()
except Exception:
    env_name = 'RT-Thread Env Tool'
    env_ver = '2.0.2'

setup(
    version=env_ver,
    description=env_name,
)

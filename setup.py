from setuptools import setup
import sys
import os

# Add current directory to path for the info module discovery
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from info import get_version, get_description

setup(
    version=get_version(),
    description=get_description(),
)

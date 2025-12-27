# -*- coding: utf-8 -*-
"""Default config template for Windows MSVC (data only)."""

CROSS_TOOL = "msvc"
EXEC_PATH = ""
CC_PREFIX = ""

TOOLCHAIN_COMMANDS = {
    "CC": "cl",
    "CXX": "cl",
    "AS": "ml",
    "AR": "lib",
    "LINK": "link",
    "SIZE": "",
    "OBJDUMP": "dumpbin",
    "OBJCOPY": "",
}

ARFLAGS = None
USE_ASPPCOM = False

BASE_CFLAGS = []
BASE_CXXFLAGS = []
BASE_ASFLAGS = []
BASE_LINKFLAGS = []
BASE_DEFINES = ["msvc"]

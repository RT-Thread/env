# -*- coding: utf-8 -*-
"""Default config template for Keil MDK ARMCC (data only)."""

CROSS_TOOL = "armcc"
PLATFORM = "armcc"
EXEC_PATH = ""
CC_PREFIX = ""

TOOLCHAIN_COMMANDS = {
    "CC": "armcc",
    "CXX": "armcc",
    "AS": "armasm",
    "AR": "armar",
    "LINK": "armlink",
    "SIZE": "fromelf",
    "OBJDUMP": "fromelf",
    "OBJCOPY": "fromelf",
}

BASE_CFLAGS = ["--c99"]
BASE_CXXFLAGS = ["--cpp"]
BASE_ASFLAGS = []
BASE_LINKFLAGS = []
BASE_DEFINES = ["armcc"]

CPU_FLAG_FORMAT = "--cpu={cpu}"
THUMB_FLAG = "--thumb"
LINK_SCRIPT_FLAG = "--scatter"
SECTION_FLAGS = []

LINK_DEVICE_FLAGS = ["--cpu={cpu}"]

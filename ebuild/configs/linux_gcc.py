# -*- coding: utf-8 -*-
"""Default config template for Linux native GCC (data only)."""

CROSS_TOOL = "gcc"
EXEC_PATH = ""
CC_PREFIX = ""

TOOLCHAIN_COMMANDS = {
    "CC": "gcc",
    "CXX": "g++",
    "AS": "gcc",
    "AR": "ar",
    "LINK": "gcc",
    "SIZE": "size",
    "OBJDUMP": "objdump",
    "OBJCOPY": "objcopy",
}

BASE_CFLAGS = ["-std=c99"]
BASE_CXXFLAGS = ["-std=c99"]
BASE_ASFLAGS = ["-c", "-x", "assembler-with-cpp"]
BASE_LINKFLAGS = []
BASE_DEFINES = ["gcc"]

# -*- coding: utf-8 -*-
"""Default config template for Keil MDK ARMCLANG (data only)."""

CROSS_TOOL = "armclang"
PLATFORM = "armclang"
EXEC_PATH = ""
CC_PREFIX = ""

TOOLCHAIN_COMMANDS = {
    "CC": "armclang",
    "CXX": "armclang",
    "AS": "armasm",
    "AR": "armar",
    "LINK": "armlink",
    "SIZE": "fromelf",
    "OBJDUMP": "fromelf",
    "OBJCOPY": "fromelf",
}

BASE_CFLAGS = ["-std=c99"]
BASE_CXXFLAGS = ["-std=c++11"]
BASE_ASFLAGS = []
BASE_LINKFLAGS = []
BASE_DEFINES = ["armclang"]

DEVICE_FLAGS = ["-mcpu={cpu}", "-mthumb", "-ffunction-sections", "-fdata-sections"]
AS_DEVICE_FLAGS = ["--cpu={cpu}", "--thumb"]
LINK_DEVICE_FLAGS = ["--cpu={cpu}"]
LINK_SCRIPT_FLAG = "--scatter"

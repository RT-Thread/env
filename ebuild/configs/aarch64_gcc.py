# -*- coding: utf-8 -*-
"""Default config template for aarch64-none-eabi-gcc (data only)."""

CROSS_TOOL = "gcc"
EXEC_PATH = ""
CC_PREFIX = "aarch64-none-eabi-"

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
BASE_LINKFLAGS = ["--specs=nosys.specs"]
BASE_DEFINES = ["gcc"]

# Architecture profiles (march/mcpu).
CPU_PROFILES = {
    "armv8-a": ["-march=armv8-a"],
    "cortex-a53": ["-mcpu=cortex-a53"],
    "cortex-a55": ["-mcpu=cortex-a55"],
    "cortex-a57": ["-mcpu=cortex-a57"],
}

ABI_PROFILES = {
    "lp64": [],
    "ilp32": ["-mabi=ilp32"],
}

DEFAULT_CPU = "armv8-a"
DEFAULT_ABI = "lp64"

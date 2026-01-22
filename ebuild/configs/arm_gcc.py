# -*- coding: utf-8 -*-
"""Default config template for arm-none-eabi-gcc (data only)."""

CROSS_TOOL = "gcc"
EXEC_PATH = ""
CC_PREFIX = "arm-none-eabi-"

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
BASE_LINKFLAGS = ["--specs=nano.specs"]
BASE_DEFINES = ["gcc"]

# Core profiles (cpu + instruction set).
CPU_PROFILES = {
    "cortex-m0": ["-mcpu=cortex-m0", "-mthumb"],
    "cortex-m3": ["-mcpu=cortex-m3", "-mthumb"],
    "cortex-m4": ["-mcpu=cortex-m4", "-mthumb"],
    "cortex-m7": ["-mcpu=cortex-m7", "-mthumb"],
    "cortex-m33": ["-mcpu=cortex-m33", "-mthumb"],
    "cortex-m85": ["-mcpu=cortex-m85", "-mthumb"],
    "cortex-r5": ["-mcpu=cortex-r5", "-marm"],
    "cortex-r5f": ["-mcpu=cortex-r5", "-marm"],
    "cortex-r52": ["-mcpu=cortex-r52", "-marm"],
    "cortex-a5": ["-mcpu=cortex-a5", "-marm"],
    "cortex-a7": ["-mcpu=cortex-a7", "-marm"],
    "cortex-a9": ["-mcpu=cortex-a9", "-marm"],
}

FPU_PROFILES = {
    "none": [],
    "fpv4-sp-d16": ["-mfpu=fpv4-sp-d16"],
    "fpv4-d16": ["-mfpu=fpv4-d16"],
    "fpv5-sp-d16": ["-mfpu=fpv5-sp-d16"],
    "fpv5-d16": ["-mfpu=fpv5-d16"],
    "neon-vfpv4": ["-mfpu=neon-vfpv4"],
    "neon-fp-armv8": ["-mfpu=neon-fp-armv8"],
}

ABI_PROFILES = {
    "soft": ["-mfloat-abi=soft"],
    "softfp": ["-mfloat-abi=softfp"],
    "hard": ["-mfloat-abi=hard"],
}

DEFAULT_CPU = "cortex-m4"
DEFAULT_FPU = "none"
DEFAULT_ABI = "soft"

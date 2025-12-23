# -*- coding: utf-8 -*-
"""Default config template for riscv-none-eabi-gcc (data only)."""

CROSS_TOOL = "gcc"
EXEC_PATH = ""
CC_PREFIX = "riscv-none-eabi-"

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

CPU_PROFILES = {
    "rv32imac": ["-march=rv32imac"],
    "rv32imafc": ["-march=rv32imafc"],
    "rv64imac": ["-march=rv64imac"],
    "rv64gc": ["-march=rv64gc"],
}

ABI_PROFILES = {
    "ilp32": ["-mabi=ilp32"],
    "ilp32f": ["-mabi=ilp32f"],
    "ilp32d": ["-mabi=ilp32d"],
    "lp64": ["-mabi=lp64"],
    "lp64f": ["-mabi=lp64f"],
    "lp64d": ["-mabi=lp64d"],
}

DEFAULT_CPU = "rv32imac"
DEFAULT_ABI = "ilp32"
DEFAULT_CODE_MODEL = ["-mcmodel=medany"]

# -*- coding: utf-8 -*-
"""Toolchain helpers for SCons projects."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


DEFAULT_COMMANDS = {
    "CC": "gcc",
    "CXX": "g++",
    "AS": "gcc",
    "AR": "ar",
    "LINK": "gcc",
    "SIZE": "size",
    "OBJDUMP": "objdump",
    "OBJCOPY": "objcopy",
}


def _as_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return str(value).split()


def _get_config_dict(config_module: Optional[Any]) -> Optional[Dict[str, Any]]:
    if config_module is None:
        return None
    config_dict = getattr(config_module, "TOOLCHAIN_CONFIG", None)
    if isinstance(config_dict, dict):
        return config_dict
    return None


def _get_attr(config_module: Optional[Any], name: str, default: Any) -> Any:
    if config_module is None:
        return default
    config_dict = _get_config_dict(config_module)
    if config_dict and name in config_dict:
        return config_dict[name]
    if hasattr(config_module, name):
        return getattr(config_module, name)
    return default


def _log_debug(config_module: Optional[Any], message: str) -> None:
    level = _get_attr(config_module, "LOG_LEVEL", "")
    if isinstance(level, str) and level.lower() in ("debug", "trace"):
        print(f"[ebuild][debug] {message}")


def _is_verbose() -> bool:
    try:
        from SCons.Script import GetOption
    except Exception:
        return False
    try:
        return bool(GetOption("verbose"))
    except Exception:
        return False


def _log_verbose(message: str) -> None:
    if _is_verbose():
        print(f"\033[32m[ebuild]: {message}\033[0m")


def _toolchain_bins(config_module: Optional[Any]) -> Dict[str, str]:
    prefix = _get_attr(config_module, "CC_PREFIX", "")
    commands = _get_attr(config_module, "TOOLCHAIN_COMMANDS", DEFAULT_COMMANDS)
    if not isinstance(commands, dict):
        commands = DEFAULT_COMMANDS
    return {key: f"{prefix}{value}" for key, value in commands.items()}


def _cc_executable_name(config_module: Optional[Any]) -> str:
    prefix = _get_attr(config_module, "CC_PREFIX", "")
    commands = _get_attr(config_module, "TOOLCHAIN_COMMANDS", DEFAULT_COMMANDS)
    if not isinstance(commands, dict):
        commands = DEFAULT_COMMANDS
    cc = commands.get("CC", DEFAULT_COMMANDS["CC"])
    return f"{prefix}{cc}"


def _is_exec_path_valid(exec_path: str, cc_bin: str) -> bool:
    if not exec_path:
        return False
    cc_path = os.path.join(exec_path, cc_bin)
    if os.path.isfile(cc_path):
        return True
    if os.name == "nt" and os.path.isfile(cc_path + ".exe"):
        return True
    return False


def _load_json(path: str) -> Optional[Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def _env_root() -> str:
    return os.path.expanduser("~/.env")


def _detect_sdk_path_from_env(cc_bin: str) -> Optional[str]:
    env_root = _env_root()
    sdk_root = os.path.join(env_root, "tools", "scripts")
    sdk_pkgs = os.path.join(sdk_root, "packages")
    if not os.path.isdir(sdk_pkgs):
        return None

    sdk_cfg_path = os.path.join(sdk_root, "sdk_cfg.json")
    sdk_cfg = _load_json(sdk_cfg_path)
    if isinstance(sdk_cfg, list):
        for item in sdk_cfg:
            if item.get("name") != cc_bin:
                continue
            candidate = os.path.join(sdk_pkgs, item.get("path", ""))
            if _is_exec_path_valid(candidate, cc_bin):
                return candidate
            if "gcc" in cc_bin:
                candidate_bin = os.path.join(candidate, "bin")
                if _is_exec_path_valid(candidate_bin, cc_bin):
                    return candidate_bin

    pkgs_path = os.path.join(sdk_pkgs, "pkgs.json")
    pkgs = _load_json(pkgs_path)
    if not isinstance(pkgs, list):
        return None

    for item in pkgs:
        package_path = os.path.join(env_root, "packages", item.get("path", ""), "package.json")
        package = _load_json(package_path)
        if not isinstance(package, dict):
            continue
        if package.get("name") != cc_bin:
            continue
        version = item.get("ver", "")
        if not version:
            continue
        candidate = os.path.join(sdk_pkgs, f"{package['name']}-{version}")
        if _is_exec_path_valid(candidate, cc_bin):
            return candidate
        if "gcc" in cc_bin:
            candidate_bin = os.path.join(candidate, "bin")
            if _is_exec_path_valid(candidate_bin, cc_bin):
                return candidate_bin

    return None


def _resolve_exec_path(config_module: Optional[Any]) -> str:
    exec_path = _get_attr(config_module, "EXEC_PATH", "")
    cc_bin = _cc_executable_name(config_module)
    prefix = _get_attr(config_module, "CC_PREFIX", "")

    if _is_exec_path_valid(exec_path, cc_bin):
        return exec_path

    if not exec_path and not prefix:
        return exec_path

    _log_debug(
        config_module,
        f"toolchain path invalid, start env detect (EXEC_PATH={exec_path or '<empty>'}, CC={cc_bin})",
    )
    candidate = _detect_sdk_path_from_env(cc_bin)
    if candidate:
        _log_verbose(f"CC={cc_bin}, EXEC_PATH={candidate}")
        _log_debug(config_module, f"toolchain detected at {candidate}")
        config_dict = _get_config_dict(config_module)
        if config_dict is not None:
            config_dict["EXEC_PATH"] = candidate
        return candidate

    _log_debug(config_module, "toolchain detect failed in ~/.env")
    env_root = _env_root()
    raise SystemExit(
        "Toolchain not found.\n"
        f"  EXEC_PATH: {exec_path or '<empty>'}\n"
        f"  CC: {cc_bin}\n"
        f"  env root: {env_root}\n"
        "  hint: install toolchain into ~/.env or update proj_config.py"
    )


def apply_toolchain(env, config_module: Optional[Any] = None) -> None:
    cross_tool = _get_attr(config_module, "CROSS_TOOL", "gcc")
    if cross_tool != "gcc":
        raise SystemExit("Only gcc toolchain is supported.")

    exec_path = _resolve_exec_path(config_module)
    if exec_path:
        env.PrependENVPath("PATH", exec_path)

    env.Replace(**_toolchain_bins(config_module))
    env["ARFLAGS"] = "-rc"
    env["ASCOM"] = env["ASPPCOM"]
    env.AppendUnique(CPPDEFINES=_as_list(_get_attr(config_module, "BASE_DEFINES", [])))


def _resolve_mcu(env, mcu_series: Dict[str, Dict[str, str]]) -> tuple:
    for macro, entry in mcu_series.items():
        if env.GetDepend(macro):
            return (entry.get("cpu"), entry.get("link_script"))
    raise SystemExit("MCU series not configured, run: scons --menuconfig")


def apply_device_flags(env, project_root: str, config_module: Optional[Any] = None) -> None:
    mcu_series = _get_attr(config_module, "MCU_SERIES", {})
    cpu, link_script = _resolve_mcu(env, mcu_series)
    if not cpu or not link_script:
        raise SystemExit("MCU series not configured, run: scons --menuconfig")

    device_flags = [
        f"-mcpu={cpu}",
        "-mthumb",
        "-ffunction-sections",
        "-fdata-sections",
    ]

    cflags = device_flags + _as_list(_get_attr(config_module, "BASE_CFLAGS", []))
    cxxflags = device_flags + _as_list(_get_attr(config_module, "BASE_CXXFLAGS", []))
    asflags = _as_list(_get_attr(config_module, "BASE_ASFLAGS", [])) + device_flags
    linkflags = device_flags + _as_list(_get_attr(config_module, "BASE_LINKFLAGS", [])) + ["-T", link_script]

    build = _get_attr(config_module, "BUILD", "release")
    if build == "debug":
        cflags += ["-O0", "-gdwarf-2", "-g"]
        cxxflags += ["-O0", "-gdwarf-2", "-g"]
        asflags += ["-gdwarf-2"]
    else:
        cflags += ["-Os"]
        cxxflags += ["-Os"]

    env.AppendUnique(CFLAGS=cflags, CXXFLAGS=cxxflags, ASFLAGS=asflags, LINKFLAGS=linkflags)
    env.AppendUnique(CPPPATH=[project_root])


def setup_project(env, project_root: str, config_module: Optional[Any] = None) -> None:
    apply_toolchain(env, config_module)
    apply_device_flags(env, project_root, config_module)


__all__ = ["apply_toolchain", "apply_device_flags", "setup_project"]

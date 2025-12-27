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

_TOOLCHAIN_DEFAULTS = {
    "gcc": {
        "cpu_flag_format": "-mcpu={cpu}",
        "thumb_flag": "-mthumb",
        "section_flags": ["-ffunction-sections", "-fdata-sections"],
        "link_script_flag": "-T",
        "debug_flags": ["-O0", "-gdwarf-2", "-g"],
        "release_flags": ["-Os"],
        "as_debug_flags": ["-gdwarf-2"],
    },
    "clang": {
        "cpu_flag_format": "-mcpu={cpu}",
        "thumb_flag": "-mthumb",
        "section_flags": ["-ffunction-sections", "-fdata-sections"],
        "link_script_flag": "-T",
        "debug_flags": ["-O0", "-gdwarf-2", "-g"],
        "release_flags": ["-Os"],
        "as_debug_flags": ["-gdwarf-2"],
    },
    "armclang": {
        "cpu_flag_format": "-mcpu={cpu}",
        "thumb_flag": "-mthumb",
        "section_flags": ["-ffunction-sections", "-fdata-sections"],
        "link_script_flag": "--scatter",
        "debug_flags": ["-O0", "-g"],
        "release_flags": ["-Os"],
        "as_debug_flags": [],
    },
    "armcc": {
        "cpu_flag_format": "--cpu={cpu}",
        "thumb_flag": "--thumb",
        "section_flags": [],
        "link_script_flag": "--scatter",
        "debug_flags": [],
        "release_flags": [],
        "as_debug_flags": [],
    },
}


def _as_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return str(value).split()


def _normalize_toolchain(value: Any) -> str:
    if not value:
        return "gcc"
    return str(value).strip().lower()


def _format_flag(flag: Any, **kwargs: Any) -> str:
    if flag is None:
        return ""
    text = str(flag)
    try:
        return text.format(**kwargs)
    except (KeyError, ValueError):
        return text


def _format_flags(values: Any, **kwargs: Any) -> List[str]:
    result: List[str] = []
    for flag in _as_list(values):
        formatted = _format_flag(flag, **kwargs)
        if formatted:
            result.append(formatted)
    return result


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


def _get_configured_flags(config_module: Optional[Any], name: str, **kwargs: Any) -> Optional[List[str]]:
    value = _get_attr(config_module, name, None)
    if value is None:
        return None
    return _format_flags(value, **kwargs)


def _toolchain_defaults(config_module: Optional[Any]) -> Dict[str, Any]:
    cross_tool = _normalize_toolchain(_get_attr(config_module, "CROSS_TOOL", "gcc"))
    return _TOOLCHAIN_DEFAULTS.get(cross_tool, {})


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
    exec_path = _resolve_exec_path(config_module)
    if exec_path:
        env.PrependENVPath("PATH", exec_path)

    env.Replace(**_toolchain_bins(config_module))
    arflags = _get_attr(config_module, "ARFLAGS", "-rc")
    if arflags is not None:
        env["ARFLAGS"] = arflags
    if _get_attr(config_module, "USE_ASPPCOM", True):
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

    defaults = _toolchain_defaults(config_module)
    cpu_flag_format = _get_attr(config_module, "CPU_FLAG_FORMAT", None)
    if cpu_flag_format is None:
        cpu_flag_format = defaults.get("cpu_flag_format")
    thumb_flag = _get_attr(config_module, "THUMB_FLAG", None)
    if thumb_flag is None:
        thumb_flag = defaults.get("thumb_flag")
    section_flags = _get_attr(config_module, "SECTION_FLAGS", None)
    if section_flags is None:
        section_flags = defaults.get("section_flags", [])

    device_flags = _get_configured_flags(config_module, "DEVICE_FLAGS", cpu=cpu)
    if device_flags is None:
        device_flags = []
        if cpu_flag_format:
            cpu_flag = _format_flag(cpu_flag_format, cpu=cpu)
            if cpu_flag:
                device_flags.append(cpu_flag)
        if thumb_flag:
            device_flags.append(str(thumb_flag))
        device_flags.extend(_as_list(section_flags))

    link_device_flags = _get_configured_flags(config_module, "LINK_DEVICE_FLAGS", cpu=cpu)
    if link_device_flags is None:
        link_device_flags = list(device_flags)

    link_script_flag = _get_attr(config_module, "LINK_SCRIPT_FLAG", None)
    if link_script_flag is None:
        link_script_flag = defaults.get("link_script_flag")

    as_device_flags = _get_configured_flags(config_module, "AS_DEVICE_FLAGS", cpu=cpu)
    if as_device_flags is None:
        as_device_flags = list(device_flags)

    cflags = device_flags + _as_list(_get_attr(config_module, "BASE_CFLAGS", []))
    cxxflags = device_flags + _as_list(_get_attr(config_module, "BASE_CXXFLAGS", []))
    asflags = _as_list(_get_attr(config_module, "BASE_ASFLAGS", [])) + as_device_flags
    linkflags = link_device_flags + _as_list(_get_attr(config_module, "BASE_LINKFLAGS", []))
    if link_script_flag is None:
        raise SystemExit(
            "Linker script flag is not configured.\n"
            "  hint: set LINK_SCRIPT_FLAG or provide LINK_DEVICE_FLAGS/BASE_LINKFLAGS"
        )
    if link_script_flag:
        linkflags += [link_script_flag, link_script]

    build = _get_attr(config_module, "BUILD", "release")
    if build == "debug":
        debug_flags = _get_attr(config_module, "DEBUG_FLAGS", None)
        if debug_flags is None:
            debug_flags = defaults.get("debug_flags", [])
        as_debug_flags = _get_attr(config_module, "AS_DEBUG_FLAGS", None)
        if as_debug_flags is None:
            as_debug_flags = defaults.get("as_debug_flags", [])
        cflags += _as_list(debug_flags)
        cxxflags += _as_list(debug_flags)
        asflags += _as_list(as_debug_flags)
    else:
        release_flags = _get_attr(config_module, "RELEASE_FLAGS", None)
        if release_flags is None:
            release_flags = defaults.get("release_flags", [])
        cflags += _as_list(release_flags)
        cxxflags += _as_list(release_flags)

    env.AppendUnique(CFLAGS=cflags, CXXFLAGS=cxxflags, ASFLAGS=asflags, LINKFLAGS=linkflags)
    env.AppendUnique(CPPPATH=[project_root])


def setup_project(env, project_root: str, config_module: Optional[Any] = None) -> None:
    apply_toolchain(env, config_module)
    apply_device_flags(env, project_root, config_module)


__all__ = ["apply_toolchain", "apply_device_flags", "setup_project"]

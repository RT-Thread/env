"""Manage the local ``sdk_cfg.json`` toolchain registry.

The registry is deliberately small and user-editable.  The WebUI only owns
the in-process lock; writes are atomic so a browser refresh cannot observe a
partially written JSON document.
"""

from __future__ import annotations

import glob
import json
import os
import platform
import re
import tempfile
import threading

if __package__ and __package__.startswith("env"):
    from env.plugins.errors import StateError, UsageError
else:
    from plugins.errors import StateError, UsageError


class ToolchainConfigError(UsageError):
    """The local toolchain registry is invalid or cannot be edited."""


class ToolchainConfigBusy(StateError):
    """A local toolchain registry write is already in progress."""


_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+:-]*$")


class ToolchainManager(object):
    """Read and atomically update the local toolchain registry."""

    def __init__(self, env_root=None, platform_name=None):
        configured = env_root or os.environ.get("ENV_ROOT")
        if configured:
            self.env_root = os.path.abspath(configured)
        else:
            home = os.environ.get("HOME") or os.environ.get("USERPROFILE") or os.path.expanduser("~")
            self.env_root = os.path.abspath(os.path.join(home, ".env"))
        self.config_root = os.path.join(self.env_root, "tools", "scripts")
        self.config_path = os.path.join(self.config_root, "sdk_cfg.json")
        self.hostos = platform_name or platform.system()
        if self.hostos not in ("Linux", "Windows"):
            raise ToolchainConfigError("本地工具链配置仅支持 Linux 和 Windows")
        self._lock = threading.RLock()

    def revision(self):
        try:
            stat = os.stat(self.config_path)
        except OSError:
            return "missing"
        return "%d:%d" % (stat.st_mtime_ns, stat.st_size)

    def snapshot(self):
        with self._lock:
            entries = self._load()
            return {
                "available": True,
                "platform": self.hostos,
                "config_path": self.config_path,
                "revision": self.revision(),
                "entries": entries,
                "detected": self._detect_windows(entries) if self.hostos == "Windows" else [],
            }

    def add(self, value):
        entry = self._validate_entry(value)
        with self._lock:
            entries = self._load()
            if any(item["name"].lower() == entry["name"].lower() for item in entries):
                raise ToolchainConfigError("工具链名称已存在：%s" % entry["name"])
            entries.append(entry)
            self._write(entries)
            return self.snapshot()

    def update(self, name, value):
        if not isinstance(name, str) or not name.strip():
            raise ToolchainConfigError("工具链名称不能为空")
        entry = self._validate_entry(value)
        with self._lock:
            entries = self._load()
            index = next(
                (index for index, item in enumerate(entries) if item["name"].lower() == name.strip().lower()),
                None,
            )
            if index is None:
                raise ToolchainConfigError("工具链不存在：%s" % name)
            if any(
                item["name"].lower() == entry["name"].lower() and item_index != index
                for item_index, item in enumerate(entries)
            ):
                raise ToolchainConfigError("工具链名称已存在：%s" % entry["name"])
            updated = dict(entries[index])
            updated.update(entry)
            entries[index] = updated
            self._write(entries)
            return self.snapshot()

    def remove(self, name):
        if not isinstance(name, str) or not name.strip():
            raise ToolchainConfigError("工具链名称不能为空")
        with self._lock:
            entries = self._load()
            remaining = [item for item in entries if item["name"].lower() != name.strip().lower()]
            if len(remaining) == len(entries):
                raise ToolchainConfigError("工具链不存在：%s" % name)
            self._write(remaining)
            return self.snapshot()

    def _load(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as source:
                value = json.load(source)
        except FileNotFoundError:
            return []
        except (OSError, ValueError) as exc:
            raise ToolchainConfigError("无法读取 sdk_cfg.json：%s" % exc)
        if not isinstance(value, list):
            raise ToolchainConfigError("sdk_cfg.json 必须是工具链数组")
        result = []
        for item in value:
            result.append(self._validate_entry(item, allow_extra=True))
        return result

    @staticmethod
    def _validate_entry(value, allow_extra=False):
        if not isinstance(value, dict):
            raise ToolchainConfigError("工具链配置项必须是对象")
        allowed = {"name", "path", "description"}
        if not allow_extra and set(value) - allowed:
            raise ToolchainConfigError("工具链配置只支持 name、path、description")
        name = value.get("name")
        path = value.get("path")
        description = value.get("description", "")
        if not isinstance(name, str) or not _NAME_PATTERN.match(name.strip()):
            raise ToolchainConfigError("工具链名称只能包含字母、数字、点、下划线、加号、冒号和连字符")
        if not isinstance(path, str) or not path.strip():
            raise ToolchainConfigError("工具链路径不能为空")
        if not isinstance(description, str):
            raise ToolchainConfigError("工具链说明必须是字符串")
        result = dict(value) if allow_extra else {}
        result.update({"name": name.strip(), "path": path.strip(), "description": description.strip()})
        return result

    def _write(self, entries):
        os.makedirs(self.config_root, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".sdk_cfg-", dir=self.config_root, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(entries, output, ensure_ascii=False, indent=4)
                output.write("\n")
            os.replace(temporary, self.config_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _deduplicate(values):
        result = []
        seen = set()
        for value in values:
            value = os.path.normcase(os.path.normpath(value))
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result

    def _windows_roots(self):
        roots = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("ProgramW6432"),
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("PROGRAMW6432"),
            os.environ.get("SystemDrive", "C:") + os.sep,
        ]
        return self._deduplicate([item for item in roots if item])

    def _registry_paths(self):
        if os.name != "nt":
            return []
        try:
            import winreg
        except ImportError:
            return []
        result = []
        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Keil\Products"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Keil\Products"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\IAR Systems"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\IAR Systems"),
        ]
        for hive, key_path in roots:
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    for index in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            child_name = winreg.EnumKey(key, index)
                            with winreg.OpenKey(key, child_name) as child:
                                for value_name in ("Path", "InstallPath", "InstallationPath", "InstallDir"):
                                    try:
                                        value, _ = winreg.QueryValueEx(child, value_name)
                                    except OSError:
                                        continue
                                    if isinstance(value, str) and value:
                                        result.append(value)
                        except OSError:
                            continue
            except OSError:
                continue
        return self._deduplicate(result)

    def _detect_windows(self, entries):
        configured = {os.path.normcase(os.path.normpath(os.path.expandvars(os.path.expanduser(item["path"])))) for item in entries}
        roots = self._windows_roots() + self._registry_paths()
        keil_roots = []
        iar_roots = []
        for root in roots:
            basename = os.path.basename(root).lower()
            if "keil" in basename:
                keil_roots.append(root)
            if "iar" in basename or "embedded workbench" in basename:
                iar_roots.append(root)
            keil_roots.extend(glob.glob(os.path.join(root, "Keil*")))
            iar_roots.extend(glob.glob(os.path.join(root, "IAR Systems", "Embedded Workbench*")))

        detected = []
        seen = set()
        for root in self._deduplicate(keil_roots):
            variants = [
                ("armcc", os.path.join(root, "ARM", "ARMCC", "bin"), "Keil MDK ARMCC"),
                ("armclang", os.path.join(root, "ARM", "ARMCLANG", "bin"), "Keil MDK ARMCLANG"),
            ]
            for name, path, label in variants:
                executable = os.path.join(path, name + ".exe")
                if not os.path.isfile(executable):
                    continue
                self._append_detected(detected, seen, name, path, label, configured, executable)

        for root in self._deduplicate(iar_roots):
            path = os.path.join(root, "arm", "bin")
            executable = os.path.join(path, "iccarm.exe")
            if os.path.isfile(executable):
                self._append_detected(detected, seen, "iccarm", path, "IAR Embedded Workbench for Arm", configured, executable)
        return detected

    @staticmethod
    def _append_detected(result, seen, config_name, path, label, configured, executable):
        key = os.path.normcase(os.path.normpath(path))
        if key in seen:
            return
        seen.add(key)
        result.append(
            {
                "id": "%s:%s" % (config_name, key),
                "name": label,
                "config_name": config_name,
                "path": path,
                "executable": executable,
                "configured": key in configured,
            }
        )


LocalToolchainManager = ToolchainManager
SdkConfigManager = ToolchainManager

__all__ = [
    "LocalToolchainManager",
    "SdkConfigManager",
    "ToolchainConfigBusy",
    "ToolchainConfigError",
    "ToolchainManager",
]

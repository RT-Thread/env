"""Install the Env terminal action in local file-manager context menus."""

from __future__ import annotations

import os
import platform
import tempfile
import threading

if __package__ and __package__.startswith("env"):
    from env.plugins.errors import StateError, UsageError
else:
    from plugins.errors import StateError, UsageError


class ContextMenuError(UsageError):
    """The context-menu integration is unavailable or failed."""


class ContextMenuBusy(StateError):
    """A context-menu change is already in progress."""


class FileContextMenuManager(object):
    """Manage a reversible, per-user ``Env终端中打开...`` entry."""

    MENU_LABEL = "Env终端中打开..."

    def __init__(self, env_root=None, platform_name=None):
        configured = env_root or os.environ.get("ENV_ROOT")
        if configured:
            self.env_root = os.path.abspath(configured)
        else:
            home = os.environ.get("HOME") or os.environ.get("USERPROFILE") or os.path.expanduser("~")
            self.env_root = os.path.abspath(os.path.join(home, ".env"))
        self.hostos = platform_name or platform.system()
        if self.hostos not in ("Linux", "Windows"):
            raise ContextMenuError("文件资源管理器菜单仅支持 Linux 和 Windows")
        self._lock = threading.RLock()

    @property
    def windows_helper(self):
        return os.path.join(self.env_root, "tools", "scripts", ".env-terminal.ps1")

    def snapshot(self):
        with self._lock:
            if self.hostos == "Windows":
                supported = os.name == "nt"
                locations = [
                    r"HKCU\Software\Classes\Directory\shell\EnvTerminal",
                    r"HKCU\Software\Classes\Directory\Background\shell\EnvTerminal",
                ]
                installed = supported and self._windows_installed()
                return {
                    "available": True,
                    "platform": self.hostos,
                    "supported": supported,
                    "installed": installed,
                    "label": self.MENU_LABEL,
                    "locations": locations,
                }
            return {
                "available": True,
                "platform": self.hostos,
                "supported": False,
                "installed": False,
                "label": self.MENU_LABEL,
                "locations": [],
            }

    def install(self):
        with self._lock:
            self._install_windows()
            return self.snapshot()

    def remove(self):
        with self._lock:
            self._remove_windows()
            return self.snapshot()

    def _windows_module(self):
        if self.hostos != "Windows" or os.name != "nt":
            raise ContextMenuError("Windows 文件资源管理器菜单只能在 Windows 上安装")
        try:
            import winreg
        except ImportError:
            raise ContextMenuError("当前 Python 缺少 Windows 注册表支持")
        return winreg

    def _windows_installed(self):
        winreg = self._windows_module()
        expected = self._windows_command()
        for key_path in (
            r"Software\Classes\Directory\shell\EnvTerminal\command",
            r"Software\Classes\Directory\Background\shell\EnvTerminal\command",
        ):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    value, _ = winreg.QueryValueEx(key, "")
                    if value == expected:
                        continue
                    return False
            except OSError:
                return False
        return os.path.isfile(self.windows_helper)

    def _windows_command(self):
        helper = self.windows_helper.replace("/", "\\")
        return 'powershell.exe -NoLogo -NoExit -ExecutionPolicy Bypass -File "%s" "%%V"' % helper

    def _install_windows(self):
        winreg = self._windows_module()
        self._atomic_text(
            self.windows_helper,
            """param([string]$TargetPath)\nif ([string]::IsNullOrWhiteSpace($TargetPath)) { $TargetPath = (Get-Location).Path }\nif (-not (Test-Path -LiteralPath $TargetPath -PathType Container)) { $TargetPath = Split-Path -Parent $TargetPath }\nSet-Location -LiteralPath $TargetPath\n. (Join-Path $PSScriptRoot 'env.ps1')\n""",
        )
        command = self._windows_command()
        for key_path in (
            r"Software\Classes\Directory\shell\EnvTerminal",
            r"Software\Classes\Directory\Background\shell\EnvTerminal",
        ):
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "MUIVerb", 0, winreg.REG_SZ, self.MENU_LABEL)
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, "powershell.exe")
                with winreg.CreateKey(key, "command") as command_key:
                    winreg.SetValueEx(command_key, "", 0, winreg.REG_SZ, command)

    def _remove_windows(self):
        winreg = self._windows_module()
        for key_path in (
            r"Software\Classes\Directory\shell\EnvTerminal",
            r"Software\Classes\Directory\Background\shell\EnvTerminal",
        ):
            self._delete_registry_tree(winreg, winreg.HKEY_CURRENT_USER, key_path)
        try:
            os.unlink(self.windows_helper)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise ContextMenuError("无法移除 Env 终端启动脚本：%s" % exc)

    @staticmethod
    def _delete_registry_tree(winreg, hive, path):
        try:
            with winreg.OpenKey(hive, path, 0, winreg.KEY_WRITE | winreg.KEY_READ) as key:
                while True:
                    try:
                        child = winreg.EnumKey(key, 0)
                    except OSError:
                        break
                    FileContextMenuManager._delete_registry_tree(winreg, key, child)
        except OSError:
            return
        try:
            winreg.DeleteKey(hive, path)
        except OSError:
            pass

    @staticmethod
    def _atomic_text(path, content):
        directory = os.path.dirname(path)
        os.makedirs(directory, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".%s-" % os.path.basename(path), dir=directory, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                output.write(content)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


__all__ = ["ContextMenuBusy", "ContextMenuError", "FileContextMenuManager"]

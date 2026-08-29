"""WebUI SDK configuration and installation manager.

The SDK index is intentionally treated as read-only metadata.  The Kconfig
file and its generated ``.config`` remain the source of truth for selection.
"""

from __future__ import annotations

import copy
import inspect
import json
import os
import platform
import re
import shutil
import tarfile
import tempfile
import threading
import time
import uuid
import zipfile
from contextlib import contextmanager
from urllib.parse import urlparse

import requests

if __package__ and __package__.startswith("env"):
    from env.plugins.errors import PackageError, PluginError, StateError, UsageError
    import env.kconfig as kconfig
else:
    from plugins.errors import PackageError, PluginError, StateError, UsageError
    import kconfig


class SdkError(PluginError):
    """Base error for SDK operations."""


class SdkUsageError(UsageError):
    """Malformed SDK request or unsupported selection."""


class SdkBusyError(StateError):
    """Another SDK update is already running in this WebUI process."""


class SdkPackageError(PackageError):
    """A SDK download or archive could not be used."""


class SdkCancelledError(SdkError):
    """An SDK update was cancelled by the WebUI caller."""


def _default_env_root():
    configured = os.environ.get("ENV_ROOT")
    if configured:
        return os.path.abspath(configured)
    home = os.environ.get("HOME") or os.environ.get("USERPROFILE") or os.path.expanduser("~")
    return os.path.abspath(os.path.join(home, ".env"))


def _safe_version(value):
    return isinstance(value, str) and bool(value) and re.match(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$", value)


def _safe_name(value):
    return isinstance(value, str) and bool(value) and re.match(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$", value)


def _prompt_text(symbol):
    for node in getattr(symbol, "nodes", ()):
        prompt = getattr(node, "prompt", None)
        if prompt:
            return prompt[0]
    return ""


def _normalise_prompt(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"\s+on\s+([a-z0-9_-]+)\s+host$", r"_\1", value)
    return value


def _symbol_suffix(enable_symbol, package_name):
    prefix = "PKG_USING_"
    return enable_symbol[len(prefix) :] if enable_symbol.startswith(prefix) else package_name.upper().replace("-", "_")


class SdkManager(object):
    """Manage the fixed SDK package set for one Env installation."""

    def __init__(self, env_root=None, packages_root=None, platform_name=None, downloader=None):
        self.env_root = os.path.abspath(env_root or _default_env_root())
        if packages_root is None:
            packages_root = os.path.join(self.env_root, "packages")
        self.packages_root = os.path.abspath(packages_root)
        self.config_root = os.path.join(self.env_root, "tools", "scripts")
        self.config_path = os.path.join(self.config_root, ".config")
        self.kconfig_path = os.path.join(self.config_root, "Kconfig")
        self.hostos = platform_name or platform.system()
        if self.hostos not in ("Linux", "Windows"):
            raise SdkUsageError("SDK management supports Linux and Windows hosts only")
        self.index_root = os.path.join(self.packages_root, "sdk", self.hostos)
        self.package_state_root = os.path.join(self.config_root, "packages")
        self.staging_root = os.path.join(self.package_state_root, ".sdk-staging")
        self.downloader = downloader or self._download
        self._apply_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._plans = {}
        self._tasks = {}
        self._cancel_events = {}

    @contextmanager
    def _kconfig_environment(self):
        values = {
            "PKGS_ROOT": self.packages_root,
            "PKGS_DIR": self.packages_root,
            "HOSTOS": self.hostos,
        }
        previous = {key: os.environ.get(key) for key in values}
        try:
            os.environ.update(values)
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def _new_kconfig(self, config_path=None):
        if not os.path.isfile(self.kconfig_path):
            raise SdkUsageError("SDK Kconfig was not found: %s" % self.kconfig_path)
        with self._kconfig_environment():
            config = __import__("kconfiglib").Kconfig(self.kconfig_path, warn=False)
            if config_path and os.path.isfile(config_path):
                config.load_config(config_path)
            return config

    def _index(self):
        if not os.path.isdir(self.index_root):
            raise SdkUsageError("SDK index directory was not found: %s" % self.index_root)
        result = []
        for name in sorted(os.listdir(self.index_root)):
            directory = os.path.join(self.index_root, name)
            metadata_path = os.path.join(directory, "package.json")
            if not os.path.isdir(directory) or not os.path.isfile(metadata_path):
                continue
            try:
                with open(metadata_path, "r", encoding="utf-8") as source:
                    metadata = json.load(source)
            except (OSError, ValueError) as exc:
                raise SdkUsageError("invalid SDK package metadata %s: %s" % (metadata_path, exc))
            if not isinstance(metadata, dict) or not _safe_name(metadata.get("name")):
                raise SdkUsageError("invalid SDK package name in %s" % metadata_path)
            versions = []
            for item in metadata.get("site") or []:
                if not isinstance(item, dict) or not _safe_version(item.get("version")):
                    continue
                versions.append(
                    {
                        "version": item["version"],
                        "url": item.get("URL") or item.get("url") or "",
                        "filename": item.get("filename") or "",
                        "size": self._package_size(item.get("size")),
                    }
                )
            if not versions:
                raise SdkUsageError("SDK package %s has no versions" % metadata["name"])
            result.append(
                {
                    "name": metadata["name"],
                    "description": metadata.get("description_zh") or metadata.get("description") or metadata["name"],
                    "description_en": metadata.get("description") or "",
                    "metadata_path": metadata_path,
                    "index_path": os.path.relpath(directory, self.packages_root).replace(os.sep, "/"),
                    "enable_symbol": metadata.get("enable") or "PKG_USING_%s" % metadata["name"].upper().replace("-", "_"),
                    "versions": versions,
                }
            )
        return result

    @staticmethod
    def _package_size(value):
        try:
            size = int(value)
        except (TypeError, ValueError):
            return None
        return size if size >= 0 else None

    def _choices(self, config):
        choices = {}
        for choice in config.unique_choices:
            owner = None
            for node in getattr(choice, "nodes", ()):
                prompt = getattr(node, "prompt", None)
                if prompt and getattr(prompt[1], "name", "").startswith("PKG_USING_"):
                    owner = prompt[1].name
                    break
            if owner:
                choices[owner] = choice
        return choices

    def _version_symbols(self, package, config, choice):
        versions = {item["version"]: None for item in package["versions"]}
        by_prompt = {_normalise_prompt(item["version"]): item["version"] for item in package["versions"]}
        for symbol in choice.syms if choice else ():
            prompt = _normalise_prompt(_prompt_text(symbol))
            if prompt in by_prompt:
                versions[by_prompt[prompt]] = symbol.name
                continue
            # Kconfig labels commonly have a leading v while package versions do not.
            prompt_without_v = prompt[1:] if prompt.startswith("v") else prompt
            for version in package["versions"]:
                candidate = version["version"].lower()
                if candidate.startswith("v"):
                    candidate = candidate[1:]
                if prompt_without_v == candidate:
                    versions[version["version"]] = symbol.name
                    break
        return versions

    def _config_snapshot(self):
        with self._state_lock:
            packages = self._index()
            config = self._new_kconfig(self.config_path)
            choices = self._choices(config)
            parsed = (
                {item["name"]: item for item in kconfig.parse(self.config_path)}
                if os.path.isfile(self.config_path)
                else {}
            )
            for package in packages:
                enable_name = package["enable_symbol"]
                enable = config.syms.get(enable_name)
                if enable is None:
                    raise SdkUsageError("Kconfig symbol %s was not found" % enable_name)
                enabled = enable.tri_value == 2
                upper = _symbol_suffix(enable_name, package["name"])
                version_symbol = config.syms.get("PKG_%s_VER" % upper)
                path_symbol = config.syms.get("PKG_%s_PATH" % upper)
                version_map = self._version_symbols(package, config, choices.get(enable_name))
                expected_version = version_symbol.str_value if enabled and version_symbol else None
                if expected_version not in {item["version"] for item in package["versions"]}:
                    parsed_item = parsed.get(upper) or {}
                    expected_version = parsed_item.get("ver") if enabled else None
                installed_version = None
                installed_candidates = []
                for item in package["versions"]:
                    target = os.path.join(self.package_state_root, "%s-%s" % (package["name"], item["version"]))
                    if os.path.isdir(target):
                        installed_candidates.append(item["version"])
                if expected_version in installed_candidates:
                    installed_version = expected_version
                elif installed_candidates:
                    installed_version = installed_candidates[0]
                if enabled and installed_version is None:
                    state = "selected_not_installed"
                elif not enabled and installed_version is not None:
                    state = "pending_remove"
                elif enabled and expected_version != installed_version:
                    state = "version_change"
                elif enabled:
                    state = "installed"
                else:
                    state = "disabled"
                package.update(
                    {
                        "enabled": enabled,
                        "expected_version": expected_version,
                        "installed_version": installed_version,
                        "state": state,
                        "path": (path_symbol.str_value if path_symbol and path_symbol.str_value else package["index_path"]),
                        "version_symbols": version_map,
                        "package_dir": "%s-%s" % (package["name"], expected_version) if expected_version else None,
                    }
                )
                package.pop("metadata_path", None)
            return {
                "available": True,
                "platform": self.hostos,
                "packages_root": self.packages_root,
                "index_root": self.index_root,
                "config_path": self.config_path,
                "revision": self.revision(),
                "config_revision": self.revision(),
                "packages": packages,
            }

    def revision(self):
        try:
            stat = os.stat(self.config_path)
        except OSError:
            return "missing"
        return "%d:%d" % (stat.st_mtime_ns, stat.st_size)

    def snapshot(self):
        with self._apply_lock:
            return self._config_snapshot()

    def _normalise_selection(self, request):
        if not isinstance(request, dict) or set(request) != {"packages"} or not isinstance(request["packages"], list):
            raise SdkUsageError("SDK plan must contain a packages list")
        available = {item["name"]: item for item in self._index()}
        if len(request["packages"]) != len(available):
            raise SdkUsageError("SDK plan must include every indexed package")
        result = {}
        for item in request["packages"]:
            if not isinstance(item, dict) or set(item) - {"name", "enabled", "version"}:
                raise SdkUsageError("invalid SDK package selection")
            name = item.get("name")
            if name not in available or name in result:
                raise SdkUsageError("unknown or duplicate SDK package: %s" % name)
            enabled = item.get("enabled")
            version = item.get("version")
            versions = {entry["version"] for entry in available[name]["versions"]}
            if not isinstance(enabled, bool):
                raise SdkUsageError("enabled must be a boolean for %s" % name)
            if enabled and version not in versions:
                raise SdkUsageError("unsupported version %s for %s" % (version, name))
            result[name] = {"enabled": enabled, "version": version if enabled else None}
        return result

    def plan(self, request):
        with self._apply_lock:
            return self._plan_locked(request)

    def _plan_locked(self, request):
        with self._state_lock:
            current = self._config_snapshot()
            selection = self._normalise_selection(request)
            operations = []
            removals = []
            for package in current["packages"]:
                desired = selection[package["name"]]
                installed = package["installed_version"]
                expected = package["expected_version"]
                if not desired["enabled"]:
                    if installed:
                        removals.append(package["name"])
                        operations.append({"action": "remove", "name": package["name"], "version": installed})
                    elif package["enabled"]:
                        operations.append({"action": "disable", "name": package["name"]})
                elif installed != desired["version"]:
                    if installed:
                        removals.append(package["name"])
                        action = "switch"
                    else:
                        action = "install"
                    operations.append(
                        {
                            "action": action,
                            "name": package["name"],
                            "from_version": installed,
                            "to_version": desired["version"],
                        }
                    )
                elif not package["enabled"] or expected != desired["version"]:
                    operations.append({"action": "enable", "name": package["name"], "version": desired["version"]})
            plan_id = uuid.uuid4().hex
            plan = {
                "plan_id": plan_id,
                "revision": current["revision"],
                "selection": selection,
                "operations": operations,
                "remove_confirmation": sorted(set(removals)),
                "snapshot": current,
                "created_at": time.time(),
            }
            self._plans[plan_id] = plan
            return {
                "plan_id": plan_id,
                "revision": plan["revision"],
                "config_revision": plan["revision"],
                "operations": operations,
                "remove_confirmation": plan["remove_confirmation"],
                "snapshot": current,
            }

    def start_apply(self, plan_id, confirm_remove):
        if not isinstance(plan_id, str) or not plan_id:
            raise SdkUsageError("plan_id must be a non-empty string")
        if not isinstance(confirm_remove, list) or any(not isinstance(item, str) for item in confirm_remove):
            raise SdkUsageError("confirm_remove must be a list of package names")
        # All public state operations acquire the update lock before the state
        # lock.  Keeping this order prevents a plan/snapshot request from
        # deadlocking with an apply request during the short hand-off window.
        if not self._apply_lock.acquire(False):
            raise SdkBusyError("another SDK update is already running")
        try:
            with self._state_lock:
                plan = self._plans.get(plan_id)
                if plan is None:
                    raise SdkUsageError("SDK plan is invalid or expired")
                required = set(plan["remove_confirmation"])
                if not required.issubset(set(confirm_remove)):
                    raise SdkUsageError("package removal requires explicit confirmation")
                if self.revision() != plan["revision"]:
                    raise StateError("SDK configuration changed; create a new plan")
                task_id = uuid.uuid4().hex
                operations = []
                for operation in plan["operations"]:
                    record = dict(operation)
                    record.update(
                        {
                            "status": "pending",
                            "stage": "queued",
                            "progress": 0,
                            "message": "等待执行",
                            "downloaded_bytes": 0,
                            "total_bytes": None,
                            "download_speed": 0,
                        }
                    )
                    operations.append(record)
                task = {
                    "task_id": task_id,
                    "plan_id": plan_id,
                    "status": "queued",
                    "stage": "queued",
                    "progress": 0,
                    "error": None,
                    "message": "任务已排队，等待开始",
                    "current_package": None,
                    "current_version": None,
                    "current_action": None,
                    "downloaded_bytes": 0,
                    "total_bytes": None,
                    "download_speed": 0,
                    "cancel_requested": False,
                    "operation_index": 0,
                    "operation_total": len(operations),
                    "operations": operations,
                    "created_at": time.time(),
                    "updated_at": time.time(),
                }
                self._tasks[task_id] = task
                self._cancel_events[task_id] = threading.Event()
                self._plans.pop(plan_id, None)
        except Exception:
            self._apply_lock.release()
            raise
        thread = threading.Thread(target=self._run_task, args=(task_id, plan), daemon=True)
        thread.start()
        # Return a snapshot so callers never serialize the worker's mutable dict
        # while the task thread is updating it.
        return self.task(task_id)

    def task(self, task_id):
        with self._state_lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise SdkUsageError("SDK task was not found")
            result = dict(task)
            result["operations"] = [dict(item) for item in task.get("operations", [])]
            if task.get("snapshot"):
                result["snapshot"] = copy.deepcopy(task["snapshot"])
            return result

    def cancel_task(self, task_id):
        """Request cooperative cancellation of a queued or running update."""
        if not isinstance(task_id, str) or not task_id:
            raise SdkUsageError("task_id must be a non-empty string")
        with self._state_lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise SdkUsageError("SDK task was not found")
            if task.get("status") in ("queued", "running"):
                event = self._cancel_events.get(task_id)
                if event is not None:
                    event.set()
                task.update(
                    {
                        "cancel_requested": True,
                        "message": "正在取消更新，等待当前操作回滚",
                        "updated_at": time.time(),
                    }
                )
            result = dict(task)
            result["operations"] = [dict(item) for item in task.get("operations", [])]
            if task.get("snapshot"):
                result["snapshot"] = copy.deepcopy(task["snapshot"])
            return result

    def _check_cancel(self, task_id):
        with self._state_lock:
            event = self._cancel_events.get(task_id)
            if event is not None and event.is_set():
                raise SdkCancelledError("SDK 更新已取消")

    def _set_task(self, task_id, **values):
        with self._state_lock:
            task = self._tasks[task_id]
            task.update(values)
            task["updated_at"] = time.time()

    @staticmethod
    def _task_progress(operation_index, operation_total, fraction):
        """Map an operation-local fraction to the transaction progress bar."""
        if operation_total <= 0:
            return 0
        fraction = max(0.0, min(1.0, fraction))
        # Reserve the final 10% for config/state writes and the final refresh.
        return max(1, min(89, int(round(((operation_index + fraction) / operation_total) * 89))))

    def _set_operation(self, task_id, operation_index, status=None, stage=None, progress=None, message=None):
        with self._state_lock:
            task = self._tasks[task_id]
            record = task["operations"][operation_index]
            if status is not None:
                record["status"] = status
            if stage is not None:
                record["stage"] = stage
            if progress is not None:
                record["progress"] = progress
            if message is not None:
                record["message"] = message
            task.update(
                {
                    "stage": stage or task.get("stage"),
                    "progress": progress if progress is not None else task.get("progress", 0),
                    "message": message or task.get("message", ""),
                    "operation_index": operation_index + 1,
                    "current_package": record.get("name"),
                    "current_version": record.get("to_version") or record.get("version"),
                    "current_action": record.get("action"),
                    "updated_at": time.time(),
                }
            )

    def _set_download_progress(
        self,
        task_id,
        operation_index,
        operation_total,
        downloaded_bytes,
        total_bytes,
        download_speed,
    ):
        self._check_cancel(task_id)
        with self._state_lock:
            task = self._tasks[task_id]
            record = task["operations"][operation_index]
            downloaded = max(0, int(downloaded_bytes or 0))
            total = int(total_bytes) if total_bytes is not None else None
            if total is not None:
                total = max(0, total)
            record.update(
                {
                    "downloaded_bytes": downloaded,
                    "total_bytes": total,
                    "download_speed": max(0, float(download_speed or 0)),
                }
            )
            fraction = 0.12
            if total:
                fraction += 0.16 * min(1.0, downloaded / total)
            task.update(
                {
                    "stage": "downloading",
                    "progress": self._task_progress(operation_index, operation_total, fraction),
                    "downloaded_bytes": record["downloaded_bytes"],
                    "total_bytes": record["total_bytes"],
                    "download_speed": record["download_speed"],
                    "updated_at": time.time(),
                }
            )

    def _finish_task_operations(self, task_id, status, stage, message, **values):
        with self._state_lock:
            task = self._tasks[task_id]
            for record in task.get("operations", []):
                record["status"] = status
                record["stage"] = stage
                record["progress"] = 100 if status == "succeeded" else record.get("progress", 0)
                record["message"] = message
            task.update(
                {
                    "status": status,
                    "progress": 100 if status == "succeeded" else task.get("progress", 0),
                    "stage": stage,
                    "message": message,
                    "current_package": None,
                    "current_version": None,
                    "current_action": None,
                    "updated_at": time.time(),
                }
            )
            task.update(values)

    def _fail_task_operations(self, task_id, message):
        with self._state_lock:
            task = self._tasks[task_id]
            current = task.get("operation_index", 0) - 1
            for index, record in enumerate(task.get("operations", [])):
                if record.get("status") == "succeeded":
                    continue
                record["status"] = "failed" if index == current else "skipped"
                record["stage"] = "failed" if index == current else "skipped"
                record["message"] = message if index == current else "未执行（事务已回滚）"

    def _cancel_task_operations(self, task_id, message):
        with self._state_lock:
            task = self._tasks[task_id]
            records = task.get("operations", [])
            current_index = next(
                (index for index, record in enumerate(records) if record.get("status") == "running"),
                None,
            )
            if current_index is None:
                current_index = next(
                    (index for index, record in enumerate(records) if record.get("status") != "succeeded"),
                    None,
                )
            for index, record in enumerate(records):
                if record.get("status") == "succeeded":
                    continue
                if index == current_index:
                    record["status"] = "cancelled"
                    record["stage"] = "cancelled"
                    record["message"] = message
                else:
                    record["status"] = "skipped"
                    record["stage"] = "skipped"
                    record["message"] = "未执行（更新已取消）" if index > (current_index or 0) else "已回滚（更新已取消）"
            current_record = records[current_index] if current_index is not None else {}
            task.update(
                {
                    "status": "cancelled",
                    "stage": "cancelled",
                    "message": message,
                    "current_package": current_record.get("name"),
                    "current_version": current_record.get("to_version") or current_record.get("version"),
                    "current_action": current_record.get("action"),
                    "cancelled_at": time.time(),
                    "updated_at": time.time(),
                }
            )

    def _run_task(self, task_id, plan):
        try:
            self._check_cancel(task_id)
            total = len(plan["operations"])
            self._set_task(
                task_id,
                status="running",
                stage="preparing",
                progress=1 if total else 92,
                message="准备执行 %d 项 SDK 操作" % total if total else "没有需要应用的 SDK 变更",
            )
            result = self._execute(plan, task_id)
            self._finish_task_operations(
                task_id,
                "succeeded",
                "completed",
                "SDK 更新完成，共 %d 项操作" % total,
                snapshot=result,
                finished_at=time.time(),
            )
        except SdkCancelledError:
            message = "更新已取消，临时变更已回滚"
            try:
                self._cancel_task_operations(task_id, message)
                with self._state_lock:
                    # A cancelled transaction is safe to retry against the same
                    # revision because _execute restored every changed path.
                    # Restoring through an atomic replace can legitimately
                    # change the filesystem mtime, so refresh the internal
                    # plan revision before making it available again.
                    plan["revision"] = self.revision()
                    self._plans[plan["plan_id"]] = plan
                self._set_task(
                    task_id,
                    error=None,
                    finished_at=time.time(),
                )
            except Exception as rollback_exc:
                self._fail_task_operations(task_id, "取消更新失败：%s" % rollback_exc)
                self._set_task(
                    task_id,
                    status="failed",
                    stage="failed",
                    error={"code": rollback_exc.__class__.__name__.lower(), "message": str(rollback_exc)},
                    message="SDK 更新失败：%s" % rollback_exc,
                    finished_at=time.time(),
                )
        except Exception as exc:
            self._fail_task_operations(task_id, "操作失败：%s" % exc)
            self._set_task(
                task_id,
                status="failed",
                stage="failed",
                error={"code": exc.__class__.__name__.lower(), "message": str(exc)},
                message="SDK 更新失败：%s" % exc,
                finished_at=time.time(),
            )
        finally:
            with self._state_lock:
                self._cancel_events.pop(task_id, None)
            self._apply_lock.release()

    def _render_config(self, selection):
        directory = self.config_root
        os.makedirs(directory, exist_ok=True)
        temporary = tempfile.NamedTemporaryFile(prefix=".sdk-config-", dir=directory, delete=False)
        temporary.close()
        try:
            with self._state_lock:
                config = self._new_kconfig(self.config_path)
                choices = self._choices(config)
                packages = self._index()
                for package in packages:
                    desired = selection[package["name"]]
                    enable = config.syms.get(package["enable_symbol"])
                    if enable is None:
                        raise SdkUsageError("Kconfig symbol %s was not found" % package["enable_symbol"])
                    enable.set_value(2 if desired["enabled"] else 0)
                    if desired["enabled"]:
                        upper = _symbol_suffix(package["enable_symbol"], package["name"])
                        version_symbol = config.syms.get("PKG_%s_VER" % upper)
                        choice = choices.get(package["enable_symbol"])
                        version_symbols = self._version_symbols(package, config, choice)
                        selected_name = version_symbols.get(desired["version"])
                        if not selected_name:
                            raise SdkUsageError("Kconfig has no choice for %s %s" % (package["name"], desired["version"]))
                        config.syms[selected_name].set_value(2)
                        if version_symbol and version_symbol.str_value != desired["version"]:
                            raise SdkUsageError("Kconfig did not select %s %s" % (package["name"], desired["version"]))
                config.write_config(temporary.name, save_old=False)
            with open(temporary.name, "rb") as source:
                content = source.read()
            # Validate both modern Kconfig loading and the legacy parser contract.
            check_path = temporary.name
            check = self._new_kconfig(check_path)
            parsed = {item["name"]: item for item in kconfig.parse(check_path)}
            for package in self._index():
                desired = selection[package["name"]]
                upper = _symbol_suffix(package["enable_symbol"], package["name"])
                if desired["enabled"]:
                    if (
                        check.syms[package["enable_symbol"]].tri_value != 2
                        or check.syms["PKG_%s_VER" % upper].str_value != desired["version"]
                    ):
                        raise SdkUsageError("generated .config failed validation for %s" % package["name"])
                    if parsed.get(upper, {}).get("ver") != desired["version"]:
                        raise SdkUsageError("legacy .config parser failed validation for %s" % package["name"])
            return temporary.name, content
        except Exception:
            try:
                os.unlink(temporary.name)
            except OSError:
                pass
            raise

    def _download(self, url, destination, progress_callback=None):
        return self._download_with_progress(url, destination, progress_callback)

    def _download_with_progress(self, url, destination, progress_callback=None):
        if not url:
            raise SdkPackageError("SDK package URL is empty")
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        total = None
        try:
            candidate = int(response.headers.get("content-length"))
            total = candidate if candidate >= 0 else None
        except (AttributeError, TypeError, ValueError):
            pass
        downloaded = 0
        started = time.monotonic()
        if progress_callback:
            progress_callback(downloaded, total, 0)
        with open(destination, "wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)
                    downloaded += len(chunk)
                    elapsed = max(time.monotonic() - started, 0.001)
                    if progress_callback:
                        progress_callback(downloaded, total, downloaded / elapsed)

    @staticmethod
    def _downloader_progress_mode(downloader):
        try:
            signature = inspect.signature(downloader)
        except (TypeError, ValueError):
            return None
        parameters = signature.parameters.values()
        positional = [
            item
            for item in parameters
            if item.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        if "progress_callback" in signature.parameters or any(
            item.kind == inspect.Parameter.VAR_KEYWORD for item in parameters
        ):
            return "keyword"
        if any(item.kind == inspect.Parameter.VAR_POSITIONAL for item in parameters) or len(positional) >= 3:
            return "positional"
        return None

    def _run_downloader(self, url, destination, progress_callback):
        mode = self._downloader_progress_mode(self.downloader)
        if mode == "keyword":
            return self.downloader(url, destination, progress_callback=progress_callback)
        if mode == "positional":
            return self.downloader(url, destination, progress_callback)
        started = time.monotonic()
        result = self.downloader(url, destination)
        elapsed = max(time.monotonic() - started, 0.001)
        downloaded = os.path.getsize(destination) if os.path.isfile(destination) else 0
        progress_callback(downloaded, None, downloaded / elapsed)
        return result

    def _extract(self, archive_path, destination):
        os.makedirs(destination, exist_ok=True)
        names = []
        try:
            if zipfile.is_zipfile(archive_path):
                with zipfile.ZipFile(archive_path, "r") as archive:
                    infos = archive.infolist()
                    names = [info.filename for info in infos]
                    self._validate_archive_names(names)
                    # SDK archives are trusted local artifacts; preserve links
                    # because toolchains use them for command aliases and ABI libs.
                    archive.extractall(destination)
            elif tarfile.is_tarfile(archive_path):
                with tarfile.open(archive_path, "r:*") as archive:
                    members = archive.getmembers()
                    names = [member.name for member in members]
                    self._validate_archive_names(names)
                    # Match the CLI policy: retain hardlinks and symlinks in
                    # the toolchain archive while keeping member paths checked.
                    archive.extractall(destination)
            else:
                raise SdkPackageError("SDK archive format is not supported")
        except SdkPackageError:
            raise
        except Exception as exc:
            raise SdkPackageError("SDK archive extraction failed: %s" % exc)
        if not names or not os.listdir(destination):
            raise SdkPackageError("SDK archive is empty")

    @staticmethod
    def _validate_archive_names(names):
        for name in names:
            normal = name.replace("\\", "/")
            if normal.startswith("/") or re.match(r"^[A-Za-z]:/", normal) or ".." in normal.split("/"):
                raise SdkPackageError("SDK archive contains an unsafe path")

    def _prepare_package(self, package, version, task_root, task_id, operation_index, operation_total):
        self._check_cancel(task_id)
        entry = next((item for item in package["versions"] if item["version"] == version), None)
        if entry is None:
            raise SdkUsageError("unsupported version %s for %s" % (version, package["name"]))
        archive_suffix = os.path.splitext(entry["filename"] or urlparse(entry["url"]).path)[1]
        archive_path = os.path.join(task_root, "%s-%s%s" % (package["name"], version, archive_suffix))
        extract_path = os.path.join(task_root, "%s-extracted" % package["name"])
        target = os.path.join(task_root, "%s-%s.ready" % (package["name"], version))
        self._set_operation(
            task_id,
            operation_index,
            stage="downloading",
            progress=self._task_progress(operation_index, operation_total, 0.12),
            message="正在下载 %s %s" % (package["name"], version),
        )
        self._set_download_progress(task_id, operation_index, operation_total, 0, entry.get("size"), 0)
        download_started = time.monotonic()
        last_download_update = [download_started]
        last_download_total = [entry.get("size")]

        def report_download(downloaded_bytes, total_bytes, download_speed, force=False):
            self._check_cancel(task_id)
            now = time.monotonic()
            if not force and downloaded_bytes and now - last_download_update[0] < 0.15:
                return
            last_download_update[0] = now
            if total_bytes is not None:
                last_download_total[0] = total_bytes
            self._set_download_progress(
                task_id,
                operation_index,
                operation_total,
                downloaded_bytes,
                last_download_total[0],
                download_speed,
            )

        self._run_downloader(entry["url"], archive_path, report_download)
        self._check_cancel(task_id)
        downloaded_bytes = os.path.getsize(archive_path) if os.path.isfile(archive_path) else 0
        elapsed = max(time.monotonic() - download_started, 0.001)
        report_download(downloaded_bytes, last_download_total[0], downloaded_bytes / elapsed, force=True)
        self._set_operation(
            task_id,
            operation_index,
            stage="downloaded",
            progress=self._task_progress(operation_index, operation_total, 0.28),
            message="已下载 %s %s，准备展开" % (package["name"], version),
        )
        self._set_operation(
            task_id,
            operation_index,
            stage="extracting",
            progress=self._task_progress(operation_index, operation_total, 0.38),
            message="正在展开 %s %s" % (package["name"], version),
        )
        self._extract(archive_path, extract_path)
        self._check_cancel(task_id)
        children = [os.path.join(extract_path, item) for item in os.listdir(extract_path)]
        if len(children) == 1 and os.path.isdir(children[0]):
            source = children[0]
            self._check_cancel(task_id)
            os.replace(source, target)
            shutil.rmtree(extract_path, ignore_errors=True)
        else:
            os.makedirs(target, exist_ok=True)
            for child in children:
                self._check_cancel(task_id)
                os.replace(child, os.path.join(target, os.path.basename(child)))
            shutil.rmtree(extract_path, ignore_errors=True)
        if not os.path.isdir(target) or not os.listdir(target):
            raise SdkPackageError("SDK archive produced no files")
        self._set_operation(
            task_id,
            operation_index,
            status="staged",
            stage="staged",
            progress=self._task_progress(operation_index, operation_total, 0.78),
            message="已展开 %s %s，等待写入配置" % (package["name"], version),
        )
        return target

    def _execute(self, plan, task_id):
        os.makedirs(self.package_state_root, exist_ok=True)
        os.makedirs(self.staging_root, exist_ok=True)
        task_root = tempfile.mkdtemp(prefix="%s-" % task_id, dir=self.staging_root)
        config_temp = None
        backups = []
        placed = []
        old_config_exists = os.path.isfile(self.config_path)
        state_paths = [
            os.path.join(self.package_state_root, "pkgs.json"),
            os.path.join(self.package_state_root, "pkgs_error.json"),
            os.path.join(self.config_root, "sdk_list.json"),
        ]
        old_state = {}
        for path in state_paths:
            try:
                with open(path, "rb") as source:
                    old_state[path] = source.read()
            except OSError:
                old_state[path] = None
        try:
            with open(self.config_path, "rb") as source:
                old_config = source.read()
        except OSError:
            old_config = None
        try:
            prepared = {}
            current = plan["snapshot"]
            by_name = {item["name"]: item for item in current["packages"]}
            operations = plan["operations"]
            operation_total = len(operations)
            for operation_index, operation in enumerate(operations):
                self._check_cancel(task_id)
                package_name = operation["name"]
                package = by_name[package_name]
                version = operation.get("to_version") or operation.get("version")
                action = operation["action"]
                self._set_operation(
                    task_id,
                    operation_index,
                    status="running",
                    stage="preparing",
                    progress=self._task_progress(operation_index, operation_total, 0.04),
                    message="准备%s %s%s" % (
                        {"install": "安装", "switch": "切换版本", "remove": "移除", "disable": "禁用", "enable": "启用"}.get(action, action),
                        package_name,
                        (" " + version) if version else "",
                    ),
                )
                self._check_cancel(task_id)
                if operation["action"] in ("install", "switch"):
                    prepared[package["name"]] = self._prepare_package(
                        package,
                        operation["to_version"],
                        task_root,
                        task_id,
                        operation_index,
                        operation_total,
                    )
                    self._check_cancel(task_id)
                else:
                    self._set_operation(
                        task_id,
                        operation_index,
                        status="staged",
                        stage="staged",
                        progress=self._task_progress(operation_index, operation_total, 0.78),
                        message="已准备%s %s，等待写入配置" % (
                            {"remove": "移除", "disable": "禁用", "enable": "启用"}.get(action, action),
                            package_name,
                        ),
                    )
                    self._check_cancel(task_id)
            self._check_cancel(task_id)
            self._set_task(
                task_id,
                stage="writing_config",
                progress=92,
                message="正在写入 .config 和 SDK 包状态（共 %d 项操作）" % operation_total,
                current_package=None,
                current_version=None,
                current_action="write_config",
            )
            config_temp, _ = self._render_config(plan["selection"])
            self._check_cancel(task_id)
            targets = []
            for operation in plan["operations"]:
                if operation["action"] in ("remove", "switch"):
                    targets.append((operation["name"], operation.get("from_version") or operation.get("version"), None))
                if operation["action"] in ("install", "switch"):
                    targets.append((operation["name"], operation.get("to_version"), prepared[operation["name"]]))
            # Move old folders out of the way before placing prepared folders. They can
            # be restored if metadata/config writing fails.
            for name, version, source in targets:
                self._check_cancel(task_id)
                if not version:
                    continue
                target = os.path.join(self.package_state_root, "%s-%s" % (name, version))
                if os.path.isdir(target):
                    backup = os.path.join(task_root, "backup-%s-%s" % (name, version))
                    os.replace(target, backup)
                    backups.append((backup, target))
                if source:
                    self._check_cancel(task_id)
                    os.replace(source, target)
                    placed.append(target)
            if os.path.isfile(config_temp):
                self._check_cancel(task_id)
                os.replace(config_temp, self.config_path)
                config_temp = None
            self._check_cancel(task_id)
            self._write_state_files(plan["selection"])
            self._check_cancel(task_id)
            self._set_task(
                task_id,
                stage="refreshing",
                progress=98,
                message="正在刷新 SDK 安装状态",
                current_action="refresh",
            )
            self._check_cancel(task_id)
            result = self._config_snapshot()
            shutil.rmtree(task_root, ignore_errors=True)
            return result
        except Exception:
            for target in reversed(placed):
                if os.path.isdir(target):
                    shutil.rmtree(target, ignore_errors=True)
            for backup, target in reversed(backups):
                if os.path.isdir(backup) and not os.path.exists(target):
                    os.replace(backup, target)
            if config_temp and os.path.exists(config_temp):
                os.unlink(config_temp)
            if old_config is None:
                if not old_config_exists and os.path.isfile(self.config_path):
                    os.unlink(self.config_path)
            else:
                self._atomic_bytes(self.config_path, old_config)
            for path, content in old_state.items():
                if content is None:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
                else:
                    self._atomic_bytes(path, content)
            raise
        finally:
            shutil.rmtree(task_root, ignore_errors=True)

    def _write_state_files(self, selection):
        os.makedirs(self.package_state_root, exist_ok=True)
        entries = []
        sdk_entries = []
        for package in self._index():
            desired = selection[package["name"]]
            if not desired["enabled"]:
                continue
            entry = {
                "name": package["name"].upper().replace("-", "_"),
                "path": package["index_path"],
                "ver": desired["version"],
            }
            entries.append(entry)
            sdk_entries.append({"name": package["name"], "path": "%s-%s" % (package["name"], desired["version"])})
        self._atomic_json(os.path.join(self.package_state_root, "pkgs.json"), entries)
        self._atomic_json(os.path.join(self.package_state_root, "pkgs_error.json"), [])
        self._atomic_json(os.path.join(self.config_root, "sdk_list.json"), sdk_entries)

    @staticmethod
    def _atomic_json(path, value):
        directory = os.path.dirname(path)
        os.makedirs(directory, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".%s-" % os.path.basename(path), dir=directory, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(value, output, ensure_ascii=False, indent=2)
                output.write("\n")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _atomic_bytes(path, content):
        directory = os.path.dirname(path)
        os.makedirs(directory, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".%s-" % os.path.basename(path), dir=directory)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(content)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

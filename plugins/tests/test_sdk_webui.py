import io
import json
import os
import shutil
import tarfile
import tempfile
import time
import unittest
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from sdk_manager import SdkBusyError, SdkManager, SdkUsageError
import kconfig
from plugins.webui.server import WebUIServer


class SdkManagerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = self.temporary.name
        self.scripts = os.path.join(self.root, "tools", "scripts")
        self.packages = os.path.join(self.root, "packages")
        os.makedirs(self.scripts)
        os.makedirs(os.path.join(self.packages, "sdk", "Linux", "demo-gcc"))
        os.makedirs(os.path.join(self.packages, "sdk", "Windows", "demo-gcc"))
        shutil.copy(
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "Kconfig"),
            os.path.join(self.scripts, "Kconfig"),
        )
        sdk_root = os.path.join(self.packages, "sdk")
        with open(os.path.join(sdk_root, "Kconfig"), "w", encoding="utf-8") as output:
            output.write(
                'config HOSTOS\n    string\n    option env="HOSTOS"\n    default "Linux"\n\nrsource "$HOSTOS/Kconfig"\n'
            )
        for hostos in ("Linux", "Windows"):
            with open(os.path.join(sdk_root, hostos, "Kconfig"), "w", encoding="utf-8") as output:
                output.write('rsource "*/Kconfig"\n')
            with open(os.path.join(sdk_root, hostos, "demo-gcc", "Kconfig"), "w", encoding="utf-8") as output:
                output.write(
                    """menuconfig PKG_USING_DEMO_GCC
    bool "demo toolchain"
    default n

if PKG_USING_DEMO_GCC
    config PKG_DEMO_GCC_PATH
        string
        default "sdk/$HOSTOS/demo-gcc"
    choice
        prompt "Version"
        config PKG_USING_DEMO_GCC_V1
            bool "v1"
        config PKG_USING_DEMO_GCC_V2
            bool "v2"
    endchoice
    config PKG_DEMO_GCC_VER
        string
        default "v1" if PKG_USING_DEMO_GCC_V1
        default "v2" if PKG_USING_DEMO_GCC_V2
endif
"""
                )
            with open(os.path.join(sdk_root, hostos, "demo-gcc", "package.json"), "w", encoding="utf-8") as output:
                json.dump(
                    {
                        "name": "demo-gcc",
                        "description": "demo",
                        "description_zh": "演示工具链",
                        "enable": "PKG_USING_DEMO_GCC",
                        "site": [
                            {"version": "v1", "URL": "fake://v1", "filename": "demo-v1.tar.gz"},
                            {"version": "v2", "URL": "fake://v2", "filename": "demo-v2.tar.gz"},
                        ],
                    },
                    output,
                )
        with open(os.path.join(self.scripts, ".config"), "w", encoding="utf-8") as output:
            output.write("# CONFIG_PKG_USING_DEMO_GCC is not set\n")
        self.archives = {"v1": self._archive("v1"), "v2": self._archive("v2")}
        self.fail_download = False
        self.block_download = None
        self.manager = SdkManager(self.root, platform_name="Linux", downloader=self._download)

    def tearDown(self):
        self.temporary.cleanup()

    def _archive(self, version):
        path = os.path.join(self.root, "demo-%s.tar.gz" % version)
        with tarfile.open(path, "w:gz") as archive:
            content = io.BytesIO(("demo %s" % version).encode("ascii"))
            info = tarfile.TarInfo("demo-%s/readme.txt" % version)
            info.size = len(content.getbuffer())
            archive.addfile(info, content)
        return path

    def _download(self, url, destination, progress_callback=None):
        if self.block_download is not None:
            self.block_download.wait(2)
        if self.fail_download:
            with open(destination, "wb") as output:
                output.write(b"not an archive")
            return
        version = url.rsplit("/", 1)[-1]
        total = os.path.getsize(self.archives[version])
        downloaded = 0
        started = time.monotonic()
        if progress_callback:
            progress_callback(0, total, 0)
        with open(self.archives[version], "rb") as source, open(destination, "wb") as output:
            while True:
                chunk = source.read(64)
                if not chunk:
                    break
                output.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    elapsed = max(time.monotonic() - started, 0.001)
                    progress_callback(downloaded, total, downloaded / elapsed)

    def _apply(self, selection, confirm_remove=None):
        plan = self.manager.plan({"packages": selection})
        task = self.manager.start_apply(
            plan["plan_id"], plan["remove_confirmation"] if confirm_remove is None else confirm_remove
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = self.manager.task(task["task_id"])
            if current["status"] not in ("queued", "running"):
                return current, plan
            time.sleep(0.01)
        self.fail("SDK task did not complete")

    def _selection(self, enabled, version=None, hostos=None):
        return [{"name": "demo-gcc", "enabled": enabled, "version": version if enabled else None}]

    def test_config_compatibility_install_switch_and_remove(self):
        initial = self.manager.snapshot()
        self.assertEqual(initial["packages"][0]["state"], "disabled")
        metadata_path = os.path.join(self.packages, "sdk", "Linux", "demo-gcc", "package.json")
        with open(metadata_path, "rb") as source:
            metadata_before = source.read()

        task, plan = self._apply(self._selection(True, "v1"))
        self.assertEqual(task["status"], "succeeded")
        self.assertEqual(task["operation_total"], 1)
        self.assertEqual(task["operation_index"], 1)
        self.assertEqual(task["operations"][0]["status"], "succeeded")
        self.assertIn("SDK 更新完成", task["message"])
        parsed = kconfig.parse(os.path.join(self.scripts, ".config"))
        self.assertEqual({item["name"]: item["ver"] for item in parsed}, {"DEMO_GCC": "v1"})
        self.assertTrue(os.path.isdir(os.path.join(self.scripts, "packages", "demo-gcc-v1")))
        with open(os.path.join(self.scripts, "packages", "pkgs.json"), "r", encoding="utf-8") as source:
            self.assertEqual(json.load(source)[0]["ver"], "v1")
        with open(os.path.join(self.scripts, "sdk_list.json"), "r", encoding="utf-8") as source:
            self.assertEqual(json.load(source)[0]["path"], "demo-gcc-v1")

        task, plan = self._apply(self._selection(True, "v2"))
        self.assertEqual(task["status"], "succeeded")
        self.assertFalse(os.path.exists(os.path.join(self.scripts, "packages", "demo-gcc-v1")))
        self.assertTrue(os.path.isdir(os.path.join(self.scripts, "packages", "demo-gcc-v2")))
        self.assertEqual(kconfig.parse(os.path.join(self.scripts, ".config"))[0]["ver"], "v2")

        remove_plan = self.manager.plan({"packages": self._selection(False)})
        self.assertEqual(remove_plan["remove_confirmation"], ["demo-gcc"])
        with self.assertRaises(SdkUsageError):
            self.manager.start_apply(remove_plan["plan_id"], [])
        task = self.manager.start_apply(remove_plan["plan_id"], ["demo-gcc"])
        while self.manager.task(task["task_id"])["status"] in ("queued", "running"):
            time.sleep(0.01)
        self.assertEqual(self.manager.task(task["task_id"])["status"], "succeeded")
        self.assertFalse(os.path.exists(os.path.join(self.scripts, "packages", "demo-gcc-v2")))
        self.assertEqual(kconfig.parse(os.path.join(self.scripts, ".config")), [])
        with open(metadata_path, "rb") as source:
            self.assertEqual(source.read(), metadata_before)

    def test_extract_failure_preserves_previous_install_and_config(self):
        task, _ = self._apply(self._selection(True, "v1"))
        self.assertEqual(task["status"], "succeeded")
        with open(os.path.join(self.scripts, ".config"), "rb") as source:
            config_before = source.read()
        self.fail_download = True
        task, _ = self._apply(self._selection(True, "v2"))
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["operations"][0]["status"], "failed")
        self.assertEqual(task["stage"], "failed")
        self.assertIn("SDK 更新失败", task["message"])
        self.assertTrue(os.path.isdir(os.path.join(self.scripts, "packages", "demo-gcc-v1")))
        self.assertFalse(os.path.exists(os.path.join(self.scripts, "packages", "demo-gcc-v2")))
        with open(os.path.join(self.scripts, ".config"), "rb") as source:
            self.assertEqual(source.read(), config_before)
        self.assertEqual(os.listdir(self.manager.staging_root), [])

    @unittest.skipIf(os.name == "nt", "symlink extraction requires Windows link privileges")
    def test_extract_preserves_toolchain_links(self):
        archive_path = os.path.join(self.root, "linked-toolchain.tar.bz2")
        destination = os.path.join(self.root, "linked-toolchain")
        with tarfile.open(archive_path, "w:bz2") as archive:
            directory = tarfile.TarInfo("toolchain/bin")
            directory.type = tarfile.DIRTYPE
            directory.mode = 0o755
            archive.addfile(directory)
            content = b"toolchain binary"
            binary = tarfile.TarInfo("toolchain/bin/tool")
            binary.size = len(content)
            archive.addfile(binary, io.BytesIO(content))
            alias = tarfile.TarInfo("toolchain/bin/alias")
            alias.type = tarfile.SYMTYPE
            alias.linkname = "tool"
            archive.addfile(alias)
            hardlink = tarfile.TarInfo("toolchain/bin/hardlink")
            hardlink.type = tarfile.LNKTYPE
            hardlink.linkname = "toolchain/bin/tool"
            archive.addfile(hardlink)

        self.manager._extract(archive_path, destination)
        alias_path = os.path.join(destination, "toolchain", "bin", "alias")
        binary_path = os.path.join(destination, "toolchain", "bin", "tool")
        hardlink_path = os.path.join(destination, "toolchain", "bin", "hardlink")
        self.assertTrue(os.path.islink(alias_path))
        self.assertEqual(os.readlink(alias_path), "tool")
        with open(alias_path, "rb") as source:
            self.assertEqual(source.read(), content)
        self.assertEqual(os.stat(binary_path).st_ino, os.stat(hardlink_path).st_ino)

    def test_state_write_failure_rolls_back_directory_and_config(self):
        task, _ = self._apply(self._selection(True, "v1"))
        self.assertEqual(task["status"], "succeeded")
        with open(os.path.join(self.scripts, ".config"), "rb") as source:
            config_before = source.read()
        original = self.manager._write_state_files

        def fail_state(_selection):
            raise OSError("simulated state write failure")

        self.manager._write_state_files = fail_state
        try:
            task, _ = self._apply(self._selection(True, "v2"))
        finally:
            self.manager._write_state_files = original
        self.assertEqual(task["status"], "failed")
        self.assertTrue(os.path.isdir(os.path.join(self.scripts, "packages", "demo-gcc-v1")))
        self.assertFalse(os.path.exists(os.path.join(self.scripts, "packages", "demo-gcc-v2")))
        with open(os.path.join(self.scripts, ".config"), "rb") as source:
            self.assertEqual(source.read(), config_before)

    def test_webui_lock_allows_one_apply(self):
        import threading

        task, _ = self._apply(self._selection(True, "v1"))
        self.assertEqual(task["status"], "succeeded")
        self.block_download = threading.Event()
        plan = self.manager.plan({"packages": self._selection(True, "v2")})
        second_plan = self.manager.plan({"packages": self._selection(True, "v2")})
        first = self.manager.start_apply(plan["plan_id"], ["demo-gcc"])
        with self.assertRaises(SdkBusyError):
            self.manager.start_apply(second_plan["plan_id"], ["demo-gcc"])
        self.block_download.set()
        while self.manager.task(first["task_id"])["status"] in ("queued", "running"):
            time.sleep(0.01)
        self.assertEqual(self.manager.task(first["task_id"])["status"], "succeeded")

    def test_task_reports_active_operation_details(self):
        import threading

        self.block_download = threading.Event()
        plan = self.manager.plan({"packages": self._selection(True, "v1")})
        task = self.manager.start_apply(plan["plan_id"], [])
        deadline = time.monotonic() + 2
        current = self.manager.task(task["task_id"])
        while time.monotonic() < deadline and current["stage"] != "downloading":
            time.sleep(0.01)
            current = self.manager.task(task["task_id"])
        self.assertEqual(current["status"], "running")
        self.assertEqual(current["operation_index"], 1)
        self.assertEqual(current["operation_total"], 1)
        self.assertEqual(current["current_package"], "demo-gcc")
        self.assertEqual(current["current_version"], "v1")
        self.assertEqual(current["current_action"], "install")
        self.assertIn("下载", current["message"])
        self.assertGreater(current["progress"], 0)
        self.assertEqual(current["downloaded_bytes"], 0)
        self.block_download.set()
        while self.manager.task(task["task_id"])["status"] in ("queued", "running"):
            time.sleep(0.01)
        completed = self.manager.task(task["task_id"])
        self.assertEqual(completed["status"], "succeeded")
        self.assertGreater(completed["downloaded_bytes"], 0)
        self.assertEqual(completed["downloaded_bytes"], completed["total_bytes"])
        self.assertGreater(completed["download_speed"], 0)

    def test_cancel_running_update_rolls_back_and_keeps_plan(self):
        import threading

        task, _ = self._apply(self._selection(True, "v1"))
        with open(os.path.join(self.scripts, ".config"), "rb") as source:
            config_before = source.read()
        self.block_download = threading.Event()
        plan = self.manager.plan({"packages": self._selection(True, "v2")})
        task = self.manager.start_apply(plan["plan_id"], ["demo-gcc"])
        deadline = time.monotonic() + 2
        current = self.manager.task(task["task_id"])
        while time.monotonic() < deadline and current["stage"] != "downloading":
            time.sleep(0.01)
            current = self.manager.task(task["task_id"])
        self.assertEqual(current["status"], "running")
        requested = self.manager.cancel_task(task["task_id"])
        self.assertTrue(requested["cancel_requested"])
        self.block_download.set()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = self.manager.task(task["task_id"])
            if current["status"] not in ("queued", "running"):
                break
            time.sleep(0.01)
        self.assertEqual(current["status"], "cancelled")
        self.assertEqual(current["stage"], "cancelled")
        self.assertIn("已取消", current["message"])
        self.assertEqual(current["operations"][0]["status"], "cancelled")
        self.assertTrue(os.path.isdir(os.path.join(self.scripts, "packages", "demo-gcc-v1")))
        self.assertFalse(os.path.exists(os.path.join(self.scripts, "packages", "demo-gcc-v2")))
        with open(os.path.join(self.scripts, ".config"), "rb") as source:
            self.assertEqual(source.read(), config_before)
        self.assertEqual(os.listdir(self.manager.staging_root), [])

        retry = self.manager.start_apply(plan["plan_id"], ["demo-gcc"])
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = self.manager.task(retry["task_id"])
            if current["status"] not in ("queued", "running"):
                break
            time.sleep(0.01)
        self.assertEqual(current["status"], "succeeded")
        self.assertTrue(os.path.isdir(os.path.join(self.scripts, "packages", "demo-gcc-v2")))

    def test_invalid_apply_releases_update_lock(self):
        with self.assertRaises(SdkUsageError):
            self.manager.start_apply("missing-plan", [])
        next_plan = self.manager.plan({"packages": self._selection(True, "v1")})
        task = self.manager.start_apply(next_plan["plan_id"], [])
        while self.manager.task(task["task_id"])["status"] in ("queued", "running"):
            time.sleep(0.01)
        self.assertEqual(self.manager.task(task["task_id"])["status"], "succeeded")

        plan = self.manager.plan({"packages": self._selection(False)})
        with self.assertRaises(SdkUsageError):
            self.manager.start_apply(plan["plan_id"], [])
        next_plan = self.manager.plan({"packages": self._selection(False)})
        task = self.manager.start_apply(next_plan["plan_id"], ["demo-gcc"])
        while self.manager.task(task["task_id"])["status"] in ("queued", "running"):
            time.sleep(0.01)
        self.assertEqual(self.manager.task(task["task_id"])["status"], "succeeded")

    def test_plan_reconciles_selected_but_missing_directory(self):
        with open(os.path.join(self.scripts, ".config"), "w", encoding="utf-8") as output:
            output.write("CONFIG_PKG_USING_DEMO_GCC=y\nCONFIG_PKG_USING_DEMO_GCC_V1=y\nCONFIG_PKG_DEMO_GCC_VER=\"v1\"\n")
        plan = self.manager.plan({"packages": self._selection(True, "v1")})
        self.assertEqual(plan["operations"], [{"action": "install", "name": "demo-gcc", "from_version": None, "to_version": "v1"}])

    def test_platform_directory_is_selected(self):
        windows = SdkManager(self.root, platform_name="Windows", downloader=self._download)
        snapshot = windows.snapshot()
        self.assertTrue(snapshot["index_root"].endswith(os.path.join("sdk", "Windows")))
        self.assertEqual(snapshot["platform"], "Windows")

    def test_missing_config_is_created_from_kconfig_defaults(self):
        os.unlink(os.path.join(self.scripts, ".config"))
        self.assertEqual(self.manager.snapshot()["revision"], "missing")
        task, _ = self._apply(self._selection(True, "v1"))
        self.assertEqual(task["status"], "succeeded")
        self.assertTrue(os.path.isfile(os.path.join(self.scripts, ".config")))
        self.assertEqual(kconfig.parse(os.path.join(self.scripts, ".config"))[0]["ver"], "v1")

    def test_http_api_plan_apply_task_and_csrf(self):
        server = WebUIServer(
            env_root=self.root,
            workspace=self.root,
            launcher_dir=os.path.join(self.root, "launchers"),
        )
        server.application.sdk.downloader = self._download
        thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
        thread.start()
        opener = build_opener(HTTPCookieProcessor(CookieJar()))
        origin = server.url.rstrip("/")

        def request(path, method="GET", body=None, csrf=None):
            headers = {}
            data = json.dumps(body).encode("utf-8") if body is not None else None
            if method != "GET":
                headers.update({"Origin": origin, "Sec-Fetch-Site": "same-origin", "Content-Type": "application/json"})
                if csrf is not None:
                    headers["X-Env-CSRF"] = csrf
            request_obj = Request(server.url + path.lstrip("/"), data=data, headers=headers, method=method)
            with opener.open(request_obj) as response:
                return response.status, json.loads(response.read().decode("utf-8"))["data"]

        try:
            with opener.open(server.launch_url):
                pass
            _, session = request("/api/v1/session")
            _, snapshot = request("/api/v1/sdk")
            selection = [{"name": "demo-gcc", "enabled": True, "version": "v1"}]
            _, plan = request("/api/v1/sdk/plan", "POST", {"packages": selection}, session["csrf_token"])
            self.assertEqual(plan["operations"][0]["action"], "install")
            with self.assertRaises(HTTPError) as denied:
                request("/api/v1/sdk/apply", "POST", {"plan_id": plan["plan_id"]})
            self.assertEqual(denied.exception.code, 403)
            status, task = request(
                "/api/v1/sdk/apply",
                "POST",
                {"plan_id": plan["plan_id"], "confirm_remove": []},
                session["csrf_token"],
            )
            self.assertEqual(status, 202)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                _, current = request("/api/v1/sdk/tasks/%s" % task["task_id"])
                if current["status"] not in ("queued", "running"):
                    break
                time.sleep(0.01)
            self.assertEqual(current["status"], "succeeded")
            self.assertEqual(current["operation_total"], 1)
            self.assertEqual(current["operations"][0]["status"], "succeeded")
            self.assertEqual(current["snapshot"]["packages"][0]["installed_version"], "v1")
            status, cancelled = request(
                "/api/v1/sdk/tasks/%s/cancel" % task["task_id"],
                "POST",
                {},
                session["csrf_token"],
            )
            self.assertEqual(status, 202)
            self.assertEqual(cancelled["status"], "succeeded")
        finally:
            server.shutdown()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

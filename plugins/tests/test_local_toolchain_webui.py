import json
import os
import tempfile
import threading
import unittest
from unittest import mock
from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, Request, build_opener

from file_context_menu import ContextMenuError, FileContextMenuManager
from toolchain_manager import ToolchainConfigError, ToolchainManager
from plugins.webui.server import WebUIServer


class ToolchainManagerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = self.temporary.name
        self.manager = ToolchainManager(self.root, platform_name="Linux")

    def tearDown(self):
        self.temporary.cleanup()

    def test_add_remove_uses_sdk_cfg_array_and_atomic_replace(self):
        self.assertEqual(self.manager.snapshot()["entries"], [])
        state = self.manager.add({"name": "arm-none-eabi-gcc", "path": "/opt/gcc/bin", "description": "ARM GCC"})
        self.assertEqual(state["entries"][0]["name"], "arm-none-eabi-gcc")
        with open(self.manager.config_path, "r", encoding="utf-8") as source:
            self.assertEqual(json.load(source), state["entries"])
        with self.assertRaises(ToolchainConfigError):
            self.manager.add({"name": "ARM GCC", "path": "/opt/other"})
        state = self.manager.remove("arm-none-eabi-gcc")
        self.assertEqual(state["entries"], [])

    def test_invalid_existing_config_is_reported(self):
        os.makedirs(os.path.dirname(self.manager.config_path), exist_ok=True)
        with open(self.manager.config_path, "w", encoding="utf-8") as output:
            output.write("{}")
        with self.assertRaises(ToolchainConfigError):
            self.manager.snapshot()

    def test_existing_optional_fields_are_preserved(self):
        os.makedirs(os.path.dirname(self.manager.config_path), exist_ok=True)
        original = [{"name": "gcc", "path": "/opt/gcc", "description": "", "vendor": "local"}]
        with open(self.manager.config_path, "w", encoding="utf-8") as output:
            json.dump(original, output)
        self.manager.add({"name": "clang", "path": "/opt/clang"})
        with open(self.manager.config_path, "r", encoding="utf-8") as source:
            entries = json.load(source)
        self.assertEqual(entries[0]["vendor"], "local")
        self.assertEqual([entry["name"] for entry in entries], ["gcc", "clang"])

    def test_update_edits_entry_and_preserves_extra_fields(self):
        self.manager.add({"name": "gcc", "path": "/opt/gcc", "description": "old"})
        with open(self.manager.config_path, "r", encoding="utf-8") as source:
            entries = json.load(source)
        entries[0]["vendor"] = "local"
        with open(self.manager.config_path, "w", encoding="utf-8") as output:
            json.dump(entries, output)
        state = self.manager.update(
            "gcc", {"name": "gcc-arm", "path": "/opt/gcc-arm", "description": "new"}
        )
        self.assertEqual(state["entries"][0]["name"], "gcc-arm")
        self.assertEqual(state["entries"][0]["path"], "/opt/gcc-arm")
        self.assertEqual(state["entries"][0]["vendor"], "local")

    def test_update_rejects_duplicate_name(self):
        self.manager.add({"name": "gcc", "path": "/opt/gcc"})
        self.manager.add({"name": "clang", "path": "/opt/clang"})
        with self.assertRaises(ToolchainConfigError):
            self.manager.update("gcc", {"name": "clang", "path": "/opt/new"})

    def test_windows_detection_reports_keil_and_iar_compilers(self):
        keil = os.path.join(self.root, "Keil_v5", "ARM", "ARMCLANG", "bin")
        iar = os.path.join(self.root, "IAR Systems", "Embedded Workbench 9.2", "arm", "bin")
        os.makedirs(keil)
        os.makedirs(iar)
        open(os.path.join(keil, "armclang.exe"), "w").close()
        open(os.path.join(iar, "iccarm.exe"), "w").close()
        manager = ToolchainManager(self.root, platform_name="Windows")
        with mock.patch.object(manager, "_windows_roots", return_value=[self.root]), mock.patch.object(
            manager, "_registry_paths", return_value=[]
        ):
            detected = manager.snapshot()["detected"]
        self.assertEqual({item["config_name"] for item in detected}, {"armclang", "iccarm"})


class FileContextMenuManagerTest(unittest.TestCase):
    def test_linux_host_does_not_expose_file_context_menu(self):
        manager = FileContextMenuManager(tempfile.gettempdir(), platform_name="Linux")
        self.assertFalse(manager.snapshot()["supported"])
        self.assertFalse(manager.snapshot()["installed"])
        with self.assertRaises(ContextMenuError):
            manager.install()


class LocalSettingsApiTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.xdg = os.path.join(self.temporary.name, "xdg")
        self.env_root = os.path.join(self.temporary.name, "env")
        self.environ = mock.patch.dict(os.environ, {"XDG_DATA_HOME": self.xdg, "ENV_PLUGIN_MARKET_URL": ""}, clear=False)
        self.environ.start()
        self.server = WebUIServer(env_root=self.env_root, workspace=self.temporary.name)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self.origin = self.server.url.rstrip("/")
        with self.opener.open(self.server.launch_url):
            pass
        _, session = self.request("/api/v1/session")
        self.csrf = session["csrf_token"]

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.environ.stop()
        self.temporary.cleanup()

    def request(self, path, method="GET", body=None, csrf=True):
        headers = {}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if method != "GET":
            headers.update({"Origin": self.origin, "Sec-Fetch-Site": "same-origin"})
            if csrf:
                headers["X-Env-CSRF"] = self.csrf
        request = Request(self.server.url + path.lstrip("/"), data=data, headers=headers, method=method)
        with self.opener.open(request) as response:
            return response.status, json.loads(response.read().decode("utf-8"))["data"]

    def test_toolchain_and_context_menu_endpoints(self):
        _, state = self.request("/api/v1/settings/toolchains")
        self.assertEqual(state["entries"], [])
        status, state = self.request(
            "/api/v1/settings/toolchains", "POST", {"name": "gcc", "path": "/opt/gcc", "description": "GCC"}
        )
        self.assertEqual(status, 201)
        self.assertEqual(state["entries"][0]["name"], "gcc")
        status, state = self.request(
            "/api/v1/settings/toolchains/gcc", "PUT", {"name": "gcc-arm", "path": "/opt/gcc-arm", "description": "ARM GCC"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(state["entries"][0]["name"], "gcc-arm")
        _, menu = self.request("/api/v1/settings/file-context-menu")
        self.assertFalse(menu["installed"])
        self.assertFalse(menu["supported"])
        self.request("/api/v1/settings/toolchains/gcc-arm", "DELETE")
        self.assertEqual(self.request("/api/v1/settings/toolchains")[1]["entries"], [])


if __name__ == "__main__":
    unittest.main()

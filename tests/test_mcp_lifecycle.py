import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from mcp import load_mcp
from mcp.mcp_client import StdioMcpClient
from lib import caplib
from http.server import BaseHTTPRequestHandler, HTTPServer


STDIO_ITEM = {
    "id": "test-mcp",
    "name": "测试 MCP",
    "description": "测试生命周期。",
    "remark": "仅用于测试。",
    "enabled": True,
    "transport": "stdio",
    "params": {"command": sys.executable, "args": [], "env": {}, "cwd": None},
}


class FakeClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def list_tools(self):
        return []


class LoadMcpLifecycleTests(unittest.TestCase):
    def test_load_defaults_to_non_persistent_connection(self):
        with (
            mock.patch.object(sys, "argv", ["load_mcp.py", "--name", "测试 MCP"]),
            mock.patch.object(load_mcp, "find_mcp", return_value=STDIO_ITEM),
            mock.patch.object(load_mcp, "open_mcp_client", return_value=FakeClient()),
            mock.patch.object(load_mcp, "_spawn_relay", return_value=(1234, 5678)) as spawn_relay,
            mock.patch.object(load_mcp, "print_json"),
        ):
            load_mcp.main()

        spawn_relay.assert_not_called()

    def test_close_stops_existing_session_without_starting_mcp(self):
        with (
            mock.patch.object(sys, "argv", ["load_mcp.py", "--name", "测试 MCP", "--close"]),
            mock.patch.object(load_mcp, "find_mcp", return_value=STDIO_ITEM),
            mock.patch.object(load_mcp, "close_session", create=True) as close_session,
            mock.patch.object(load_mcp, "open_mcp_client") as open_client,
            mock.patch.object(load_mcp, "print_json"),
        ):
            try:
                load_mcp.main()
            except SystemExit as exc:
                self.fail(f"--close 尚未实现：{exc}")

        close_session.assert_called_once_with("test-mcp")
        open_client.assert_not_called()

    def test_keep_alive_passes_lifecycle_options_to_relay(self):
        argv = [
            "load_mcp.py",
            "--name",
            "测试 MCP",
            "--keep-alive",
            "--idle-timeout",
            "42",
            "--owner",
            "none",
            "--no-kill-process-tree",
        ]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(load_mcp, "find_mcp", return_value=STDIO_ITEM),
            mock.patch.object(load_mcp, "open_mcp_client", return_value=FakeClient()),
            mock.patch.object(
                load_mcp, "_spawn_relay", return_value=(1234, 5678, "shutdown-token")
            ) as spawn_relay,
            mock.patch.object(load_mcp, "write_session") as write_session,
            mock.patch.object(load_mcp, "kill_stale_session"),
            mock.patch.object(load_mcp, "print_json"),
        ):
            try:
                load_mcp.main()
            except SystemExit as exc:
                self.fail(f"保活生命周期参数尚未实现：{exc}")

        spawn_relay.assert_called_once_with(
            STDIO_ITEM,
            idle_timeout=42,
            owner=None,
            kill_process_tree=False,
        )
        session = write_session.call_args.args[1]
        self.assertEqual(session["shutdown_token"], "shutdown-token")

    def test_auto_owner_uses_detected_platform_process(self):
        detected = {"pid": 321, "parent_pid": 1, "name": "Hermes.exe"}
        with mock.patch.object(load_mcp, "detect_owner_process", create=True, return_value=detected):
            owner = load_mcp._resolve_owner(None)

        self.assertEqual(owner, detected)

    def test_manual_owner_pid_uses_exact_process(self):
        requested = {"pid": 321, "parent_pid": 999, "name": "python.exe"}
        with (
            mock.patch.object(load_mcp, "snapshot_processes", create=True, return_value={321: requested}),
            mock.patch.object(
                load_mcp,
                "detect_owner_process",
                return_value={"pid": 999, "parent_pid": 1, "name": "Hermes.exe"},
            ),
        ):
            owner = load_mcp._resolve_owner(321)

        self.assertEqual(owner, requested)


class RelayLifecycleTests(unittest.TestCase):
    def test_relay_exits_after_configured_idle_timeout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "relay.json"
            config_path.write_text(
                json.dumps(
                    {
                        "mcp": {
                            "command": sys.executable,
                            "args": [str(ROOT / "tests" / "fake_stdio_mcp.py")],
                            "env": {},
                            "cwd": str(ROOT),
                        },
                        "idle_timeout": 0.5,
                        "shutdown_token": "test-token",
                        "owner": None,
                        "kill_process_tree": False,
                    }
                ),
                encoding="utf-8",
            )
            process = subprocess.Popen(
                [sys.executable, str(ROOT / "tools" / "mcp" / "relay.py"), str(config_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            try:
                ready_line = process.stdout.readline().strip()
                if not ready_line.startswith("RELAY_READY"):
                    self.fail(process.stderr.read())
                process.wait(timeout=3)
                self.assertEqual(process.returncode, 0)
                self.assertFalse(config_path.exists())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=3)
                process.stdout.close()
                process.stderr.close()

    def test_relay_exits_when_owner_process_ends(self):
        owner = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "relay.json"
            config_path.write_text(
                json.dumps(
                    {
                        "mcp": {
                            "command": sys.executable,
                            "args": [str(ROOT / "tests" / "fake_stdio_mcp.py")],
                            "env": {},
                            "cwd": str(ROOT),
                        },
                        "idle_timeout": 0,
                        "shutdown_token": "test-token",
                        "owner": {"pid": owner.pid, "name": "python.exe"},
                        "kill_process_tree": False,
                    }
                ),
                encoding="utf-8",
            )
            relay = subprocess.Popen(
                [sys.executable, str(ROOT / "tools" / "mcp" / "relay.py"), str(config_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            try:
                ready_line = relay.stdout.readline().strip()
                if not ready_line.startswith("RELAY_READY"):
                    self.fail(relay.stderr.read())
                owner.terminate()
                owner.wait(timeout=3)
                try:
                    relay.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.fail("Owner 退出后 relay 仍在运行")
                self.assertEqual(relay.returncode, 0)
            finally:
                if owner.poll() is None:
                    owner.kill()
                    owner.wait(timeout=3)
                if relay.poll() is None:
                    relay.kill()
                    relay.wait(timeout=3)
                relay.stdout.close()
                relay.stderr.close()

    def test_failed_mcp_initialization_does_not_leave_process_running(self):
        client = StdioMcpClient(
            {
                "command": sys.executable,
                "args": ["-c", "import time; time.sleep(60)"],
                "env": {},
                "cwd": str(ROOT),
            },
            timeout=0.2,
        )
        try:
            with self.assertRaises(caplib.CapabilityError):
                client.__enter__()
            self.assertIsNotNone(client.process)
            self.assertIsNotNone(client.process.poll(), "初始化失败的 MCP 进程仍在运行")
        finally:
            client.__exit__(None, None, None)

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object 仅在 Windows 验证")
    def test_job_object_closes_mcp_descendant_processes(self):
        child_pid = None
        with tempfile.TemporaryDirectory() as temp_dir:
            child_pid_path = Path(temp_dir) / "child.pid"
            config_path = Path(temp_dir) / "relay.json"
            config_path.write_text(
                json.dumps(
                    {
                        "mcp": {
                            "command": sys.executable,
                            "args": [str(ROOT / "tests" / "fake_child_stdio_mcp.py")],
                            "env": {"CHILD_PID_FILE": str(child_pid_path)},
                            "cwd": str(ROOT),
                        },
                        "idle_timeout": 0,
                        "shutdown_token": "test-token",
                        "owner": None,
                        "kill_process_tree": True,
                    }
                ),
                encoding="utf-8",
            )
            relay = subprocess.Popen(
                [sys.executable, str(ROOT / "tools" / "mcp" / "relay.py"), str(config_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            try:
                ready_line = relay.stdout.readline().strip()
                if not ready_line.startswith("RELAY_READY"):
                    self.fail(relay.stderr.read())
                deadline = time.monotonic() + 3
                while not child_pid_path.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(child_pid_path.exists(), "假 MCP 未记录子进程 PID")
                child_pid = int(child_pid_path.read_text(encoding="utf-8"))
                port = int(ready_line.split("=")[1])
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/shutdown",
                    data=json.dumps({"token": "test-token"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=2):
                    pass
                relay.wait(timeout=3)
                time.sleep(0.2)
                self.assertNotIn(child_pid, caplib.snapshot_processes())
            finally:
                if relay.poll() is None:
                    relay.kill()
                    relay.wait(timeout=3)
                if child_pid in caplib.snapshot_processes():
                    os.kill(child_pid, signal.SIGTERM)
                relay.stdout.close()
                relay.stderr.close()


class SessionLifecycleTests(unittest.TestCase):
    def test_close_session_requests_graceful_relay_shutdown(self):
        received = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                received.update(json.loads(self.rfile.read(length)))
                data = b'{"ok": true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
                caplib, "SESSION_DIR", Path(temp_dir)
            ):
                caplib.write_session(
                    "test-mcp",
                    {
                        "mcp_id": "test-mcp",
                        "transport": "stdio_relay",
                        "relay_url": f"http://127.0.0.1:{server.server_port}",
                        "shutdown_token": "secret-token",
                    },
                )
                closed = caplib.close_session("test-mcp")

                self.assertTrue(closed)
                self.assertEqual(received, {"token": "secret-token"})
                self.assertIsNone(caplib.read_session("test-mcp"))
        finally:
            server.server_close()
            thread.join(timeout=2)

    def test_close_session_waits_for_relay_process_exit(self):
        session = {
            "mcp_id": "test-mcp",
            "transport": "stdio_relay",
            "relay_url": "http://127.0.0.1:1234",
            "shutdown_token": "secret-token",
            "pid": 123,
        }
        response = mock.MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        watcher = mock.MagicMock()
        watcher.is_alive.side_effect = [True, False]
        with (
            mock.patch.object(caplib, "read_session", return_value=session),
            mock.patch.object(caplib, "delete_session"),
            mock.patch.object(caplib.urllib.request, "urlopen", return_value=response),
            mock.patch.object(caplib, "OwnerWatcher", return_value=watcher) as watcher_type,
        ):
            caplib.close_session("test-mcp")

        watcher_type.assert_called_once_with(123)
        self.assertEqual(watcher.is_alive.call_count, 2)
        watcher.close.assert_called_once_with()

    @unittest.skipUnless(sys.platform == "win32", "Windows 进程树回退仅在 Windows 验证")
    def test_close_legacy_session_falls_back_to_taskkill_tree(self):
        session = {
            "mcp_id": "test-mcp",
            "transport": "stdio_relay",
            "pid": 123,
            "kill_process_tree": True,
        }
        with (
            mock.patch.object(caplib, "read_session", return_value=session),
            mock.patch.object(caplib, "delete_session"),
            mock.patch.object(caplib, "OwnerWatcher", side_effect=caplib.CapabilityError("gone")),
            mock.patch.object(caplib.subprocess, "run") as run,
        ):
            caplib.close_session("test-mcp")

        run.assert_called_once_with(
            ["taskkill", "/PID", "123", "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    def test_relay_does_not_delete_replacement_session(self):
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            caplib, "SESSION_DIR", Path(temp_dir)
        ):
            caplib.write_session("test-mcp", {"pid": 222})

            deleted = caplib.delete_session_if_pid("test-mcp", 111)

            self.assertFalse(deleted)
            self.assertIsNotNone(caplib.read_session("test-mcp"))

    def test_relay_deletes_its_own_session(self):
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            caplib, "SESSION_DIR", Path(temp_dir)
        ):
            caplib.write_session("test-mcp", {"pid": 111})

            deleted = caplib.delete_session_if_pid("test-mcp", 111)

            self.assertTrue(deleted)
            self.assertIsNone(caplib.read_session("test-mcp"))

    def test_relay_exits_after_authenticated_shutdown_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "relay.json"
            config_path.write_text(
                json.dumps(
                    {
                        "mcp": {
                            "command": sys.executable,
                            "args": [str(ROOT / "tests" / "fake_stdio_mcp.py")],
                            "env": {},
                            "cwd": str(ROOT),
                        },
                        "idle_timeout": 0,
                        "shutdown_token": "test-token",
                        "owner": None,
                        "kill_process_tree": False,
                    }
                ),
                encoding="utf-8",
            )
            process = subprocess.Popen(
                [sys.executable, str(ROOT / "tools" / "mcp" / "relay.py"), str(config_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            try:
                ready_line = process.stdout.readline().strip()
                if not ready_line.startswith("RELAY_READY"):
                    self.fail(process.stderr.read())
                port = int(ready_line.split("=")[1])
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/shutdown",
                    data=json.dumps({"token": "test-token"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(request, timeout=2) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                except urllib.error.HTTPError as exc:
                    self.fail(f"/shutdown 尚未实现：HTTP {exc.code}")
                self.assertTrue(payload["ok"])
                process.wait(timeout=3)
                self.assertEqual(process.returncode, 0)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=3)
                process.stdout.close()
                process.stderr.close()


class OwnerDetectionTests(unittest.TestCase):
    def test_selects_known_platform_from_ancestor_chain(self):
        chain = [
            {"pid": 10, "parent_pid": 20, "name": "powershell.exe"},
            {"pid": 20, "parent_pid": 30, "name": "codex.exe"},
            {"pid": 30, "parent_pid": 40, "name": "ChatGPT.exe"},
        ]

        owner = caplib.select_owner_process(chain)

        self.assertEqual(owner, chain[1])

    def test_unknown_platform_uses_nearest_non_shell_ancestor(self):
        chain = [
            {"pid": 10, "parent_pid": 20, "name": "powershell.exe"},
            {"pid": 20, "parent_pid": 30, "name": "node.exe"},
            {"pid": 30, "parent_pid": 40, "name": "explorer.exe"},
        ]

        owner = caplib.select_owner_process(chain)

        self.assertEqual(owner, chain[1])

    def test_builds_ancestor_chain_from_process_table(self):
        process_table = {
            10: {"pid": 10, "parent_pid": 20, "name": "powershell.exe"},
            20: {"pid": 20, "parent_pid": 30, "name": "codex.exe"},
            30: {"pid": 30, "parent_pid": 0, "name": "ChatGPT.exe"},
        }

        chain = caplib.build_ancestor_chain(process_table, 10)

        self.assertEqual([item["pid"] for item in chain], [10, 20, 30])

    def test_detect_owner_uses_current_ancestor_snapshot(self):
        process_table = {
            10: {"pid": 10, "parent_pid": 20, "name": "powershell.exe"},
            20: {"pid": 20, "parent_pid": 0, "name": "codex.exe"},
        }
        with mock.patch.object(caplib, "snapshot_processes", create=True, return_value=process_table):
            owner = caplib.detect_owner_process(10)

        self.assertEqual(owner, process_table[20])


if __name__ == "__main__":
    unittest.main()

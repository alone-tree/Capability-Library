import json
import hmac
import os
import queue
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.caplib import CapabilityError, ROOT


PROTOCOL_VERSION = "2025-03-26"


class WindowsJobObject:
    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimitInformation),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._close_handle = self._kernel32.CloseHandle
        self._close_handle.argtypes = [wintypes.HANDLE]
        create_job = self._kernel32.CreateJobObjectW
        create_job.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        create_job.restype = wintypes.HANDLE
        set_information = self._kernel32.SetInformationJobObject
        set_information.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        set_information.restype = wintypes.BOOL
        self._handle = create_job(None, None)
        if not self._handle:
            raise CapabilityError(f"创建 Windows Job Object 失败：{ctypes.WinError(ctypes.get_last_error())}")
        information = ExtendedLimitInformation()
        information.BasicLimitInformation.LimitFlags = 0x00002000
        success = set_information(
            self._handle,
            9,
            ctypes.byref(information),
            ctypes.sizeof(information),
        )
        if not success:
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise CapabilityError(f"配置 Windows Job Object 失败：{error}")

    def assign(self, process):
        import ctypes
        from ctypes import wintypes

        self._kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self._kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        if not self._kernel32.AssignProcessToJobObject(self._handle, wintypes.HANDLE(process._handle)):
            raise CapabilityError(f"MCP 加入 Windows Job Object 失败：{ctypes.WinError(ctypes.get_last_error())}")

    def close(self):
        if self._handle:
            self._close_handle(self._handle)
            self._handle = None


class JsonRpcId:
    def __init__(self):
        self.value = 0

    def next(self):
        self.value += 1
        return self.value


def initialize_payload(rpc_id):
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "capability-library", "version": "0.1.0"},
        },
    }


def initialized_notification():
    return {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}


class StdioMcpClient:
    def __init__(self, params, timeout=30, kill_process_tree=True):
        self.params = params
        self.timeout = timeout
        self.process = None
        self.lines = queue.Queue()
        self.reader = None
        self.ids = JsonRpcId()
        self.kill_process_tree = kill_process_tree
        self.job = None

    def __enter__(self):
        command = self.params["command"]
        args = self.params.get("args", [])
        env = self.params.get("env") or None
        cwd = self.params.get("cwd")
        if cwd:
            cwd = str((ROOT / cwd).resolve()) if not Path(cwd).is_absolute() else cwd
        else:
            cwd = str(ROOT)
        merged_env = None
        if env:
            merged_env = os.environ.copy()
            merged_env.update(env)
        if os.name == "nt" and self.kill_process_tree:
            self.job = WindowsJobObject()
        try:
            self.process = subprocess.Popen(
                [command] + args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                cwd=cwd,
                env=merged_env,
            )
        except Exception:
            if self.job:
                self.job.close()
                self.job = None
            raise
        if self.job:
            try:
                self.job.assign(self.process)
            except Exception:
                self.process.kill()
                self.process.wait(timeout=3)
                self.job.close()
                self.job = None
                raise
        self.reader = threading.Thread(target=self._read_stdout, daemon=True)
        self.reader.start()
        try:
            self.initialize()
        except Exception:
            self.__exit__(*sys.exc_info())
            raise
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
        finally:
            if self.job:
                self.job.close()
                self.job = None
            if self.process:
                for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                    if stream:
                        try:
                            stream.close()
                        except OSError:
                            pass
            if self.reader and self.reader.is_alive():
                self.reader.join(timeout=0.2)

    def _read_stdout(self):
        for line in self.process.stdout:
            if line.strip():
                self.lines.put(line)

    def send(self, message):
        if not self.process or self.process.poll() is not None:
            raise CapabilityError("MCP 进程未运行")
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def request(self, method, params=None):
        rpc_id = self.ids.next()
        message = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
        if params is not None:
            message["params"] = params
        self.send(message)
        return self.wait_response(rpc_id)

    def notify(self, method, params=None):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self.send(message)

    def wait_response(self, rpc_id):
        while True:
            try:
                line = self.lines.get(timeout=self.timeout)
            except queue.Empty as exc:
                raise CapabilityError(f"等待 MCP 响应超时：id={rpc_id}") from exc
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("id") != rpc_id:
                continue
            if "error" in payload:
                raise CapabilityError(f"MCP 返回错误：{payload['error']}")
            return payload.get("result")

    def initialize(self):
        rpc_id = self.ids.next()
        self.send(initialize_payload(rpc_id))
        result = self.wait_response(rpc_id)
        self.send(initialized_notification())
        return result

    def list_tools(self):
        result = self.request("tools/list", {})
        return result.get("tools", []) if isinstance(result, dict) else result

    def call_tool(self, tool_name, params):
        return self.request("tools/call", {"name": tool_name, "arguments": params})


class HttpMcpClient:
    def __init__(self, params, timeout=30):
        self.params = params
        self.timeout = timeout
        self.ids = JsonRpcId()
        self.session_id = None

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def post(self, message, expect_response=True):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        headers.update(self.params.get("headers", {}))
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        request = urllib.request.Request(
            self.params["url"],
            data=json.dumps(message, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                session_id = response.headers.get("Mcp-Session-Id")
                if session_id:
                    self.session_id = session_id
                body = response.read().decode("utf-8")
                if not expect_response or response.status == 202 or not body:
                    return None
                content_type = response.headers.get("Content-Type", "")
                if "text/event-stream" in content_type:
                    return parse_sse_json(body)
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise CapabilityError(f"HTTP MCP 请求失败：{exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise CapabilityError(f"HTTP MCP 连接失败：{exc}") from exc

    def request(self, method, params=None):
        rpc_id = self.ids.next()
        message = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
        if params is not None:
            message["params"] = params
        payload = self.post(message)
        if isinstance(payload, list):
            payload = next((item for item in payload if item.get("id") == rpc_id), None)
        if not isinstance(payload, dict):
            raise CapabilityError(f"HTTP MCP 响应格式错误：{payload}")
        if "error" in payload:
            raise CapabilityError(f"MCP 返回错误：{payload['error']}")
        return payload.get("result")

    def notify(self, method, params=None):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self.post(message, expect_response=False)

    def initialize(self):
        result = self.request("initialize", initialize_payload(self.ids.next())["params"])
        self.notify("notifications/initialized", {})
        return result

    def list_tools(self):
        result = self.request("tools/list", {})
        return result.get("tools", []) if isinstance(result, dict) else result

    def call_tool(self, tool_name, params):
        return self.request("tools/call", {"name": tool_name, "arguments": params})


def parse_sse_json(body):
    messages = []
    chunks = []
    for line in body.splitlines():
        if not line.strip():
            if chunks:
                messages.append("\n".join(chunks))
                chunks = []
            continue
        if line.startswith("data:"):
            chunks.append(line[5:].strip())
    if chunks:
        messages.append("\n".join(chunks))
    parsed = [json.loads(item) for item in messages if item and item != "[DONE]"]
    if len(parsed) == 1:
        return parsed[0]
    return parsed


def open_mcp_client(item, timeout=30):
    transport = item["transport"]
    if transport == "stdio":
        return StdioMcpClient(item["params"], timeout=timeout)
    if transport == "streamable_http":
        return HttpMcpClient(item["params"], timeout=timeout)
    raise CapabilityError(f"不支持的 MCP transport：{transport}")


class RelayServer:
    """HTTP relay that proxies tool calls to a live stdio MCP client."""

    def __init__(self, client, host="127.0.0.1", port=0, shutdown_token=None):
        self.client = client
        self.host = host
        self.port = port
        self._server = None
        self._thread = None
        self._activity_lock = threading.Lock()
        self._active_requests = 0
        self._last_activity = time.monotonic()
        self._shutdown_token = shutdown_token
        self._shutdown_event = threading.Event()

    @property
    def url(self):
        return f"http://{self.host}:{self.port}"

    def start(self):
        parent = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length)) if length > 0 else {}
                if self.path == "/shutdown":
                    token = str(body.get("token", ""))
                    expected = str(parent._shutdown_token or "")
                    if not expected or not hmac.compare_digest(token, expected):
                        self._send_json(403, {"ok": False, "error": "无效的关闭令牌"})
                        return
                    self._send_json(200, {"ok": True})
                    parent._shutdown_event.set()
                    return

                parent._request_started()
                try:
                    if self.path == "/tools/list":
                        result = parent.client.list_tools()
                    elif self.path == "/tools/call":
                        result = parent.client.call_tool(body["tool"], body.get("params", {}))
                    else:
                        self._send_json(404, {"ok": False, "error": "未知路径"})
                        return
                    data = json.dumps({"ok": True, "result": result}, ensure_ascii=False).encode("utf-8")
                except Exception as exc:
                    data = json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False).encode("utf-8")
                finally:
                    parent._request_finished()
                self._send_bytes(200, data)

            def _send_json(self, status, payload):
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self._send_bytes(status, data)

            def _send_bytes(self, status, data):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self._server = HTTPServer((self.host, self.port), _Handler)
        self.port = self._server.server_port
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.port

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()

    def _request_started(self):
        with self._activity_lock:
            self._active_requests += 1
            self._last_activity = time.monotonic()

    def _request_finished(self):
        with self._activity_lock:
            self._active_requests -= 1
            self._last_activity = time.monotonic()

    def is_idle(self, timeout):
        if timeout <= 0:
            return False
        with self._activity_lock:
            return self._active_requests == 0 and time.monotonic() - self._last_activity >= timeout

    def shutdown_requested(self):
        return self._shutdown_event.is_set()


def call_tool_via_relay(relay_url, tool_name, params, timeout=30):
    payload = {"tool": tool_name, "params": params}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{relay_url}/tools/call",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            response = json.loads(resp.read().decode("utf-8"))
            if response.get("ok"):
                return response["result"]
            raise CapabilityError(response.get("error", "Relay 返回错误"))
    except urllib.error.URLError as exc:
        raise CapabilityError(f"Relay 连接失败：{exc}。MCP 会话可能已断开，请重新 load_mcp。")


def call_tool_via_http_session(session, tool_name, params, timeout=30):
    client = HttpMcpClient.__new__(HttpMcpClient)
    client.params = {"url": session["url"], "headers": session.get("headers", {})}
    client.timeout = timeout
    client.ids = JsonRpcId()
    client.session_id = session.get("session_id")
    return client.call_tool(tool_name, params)

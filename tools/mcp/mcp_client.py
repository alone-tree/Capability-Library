import json
import os
import queue
import signal
import subprocess
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.caplib import CapabilityError, ROOT


PROTOCOL_VERSION = "2025-03-26"


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
    def __init__(self, params, timeout=30):
        self.params = params
        self.timeout = timeout
        self.process = None
        self.lines = queue.Queue()
        self.reader = None
        self.ids = JsonRpcId()

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
            import os

            merged_env = os.environ.copy()
            merged_env.update(env)
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
        self.reader = threading.Thread(target=self._read_stdout, daemon=True)
        self.reader.start()
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()

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

    def __init__(self, client, host="127.0.0.1", port=0):
        self.client = client
        self.host = host
        self.port = port
        self._server = None
        self._thread = None

    @property
    def url(self):
        return f"http://{self.host}:{self.port}"

    def start(self):
        parent = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length)) if length > 0 else {}
                try:
                    if self.path == "/tools/list":
                        result = parent.client.list_tools()
                    elif self.path == "/tools/call":
                        result = parent.client.call_tool(body["tool"], body.get("params", {}))
                    else:
                        self.send_response(404)
                        self.end_headers()
                        return
                    data = json.dumps({"ok": True, "result": result}, ensure_ascii=False).encode("utf-8")
                except Exception as exc:
                    data = json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
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

import json
import os
import signal
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MCPS_REGISTRY = ROOT / "mcps" / "registry.json"
SESSION_DIR = Path(tempfile.gettempdir()) / "capability-library" / "sessions"
KNOWN_PLATFORM_PROCESSES = {
    "hermes.exe",
    "codex.exe",
    "chatgpt.exe",
    "claude.exe",
    "workbuddy.exe",
    "codebuddy.exe",
}
SHELL_WRAPPER_PROCESSES = {
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "conhost.exe",
    "explorer.exe",
    "sh",
    "bash",
    "zsh",
    "fish",
    "system",
}


class CapabilityError(Exception):
    pass


class OwnerWatcher:
    def __init__(self, pid):
        self.pid = int(pid)
        self._handle = None
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            open_process = kernel32.OpenProcess
            open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            open_process.restype = wintypes.HANDLE
            self._handle = open_process(0x00100000, False, self.pid)
            if not self._handle:
                raise CapabilityError(f"Owner 进程不存在或无法监控：PID {self.pid}")

    def is_alive(self):
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            wait_for_single_object = kernel32.WaitForSingleObject
            wait_for_single_object.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            wait_for_single_object.restype = wintypes.DWORD
            return wait_for_single_object(self._handle, 0) == 0x00000102
        try:
            os.kill(self.pid, 0)
            return True
        except (ProcessLookupError, OSError):
            return False

    def close(self):
        if self._handle:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [wintypes.HANDLE]
            close_handle(self._handle)
            self._handle = None


def select_owner_process(ancestor_chain):
    for process in ancestor_chain:
        if process.get("name", "").lower() in KNOWN_PLATFORM_PROCESSES:
            return process
    for process in ancestor_chain:
        if process.get("name", "").lower() not in SHELL_WRAPPER_PROCESSES:
            return process
    return None


def build_ancestor_chain(process_table, start_pid, limit=32):
    chain = []
    current_pid = start_pid
    seen = set()
    while current_pid and current_pid not in seen and len(chain) < limit:
        process = process_table.get(current_pid)
        if process is None:
            break
        chain.append(process)
        seen.add(current_pid)
        current_pid = process.get("parent_pid", 0)
    return chain


def snapshot_processes():
    if os.name == "nt":
        return _snapshot_windows_processes()
    output = subprocess.check_output(["ps", "-axo", "pid=,ppid=,comm="], text=True)
    processes = {}
    for line in output.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) != 3:
            continue
        pid, parent_pid, name = parts
        processes[int(pid)] = {"pid": int(pid), "parent_pid": int(parent_pid), "name": Path(name).name}
    return processes


def _snapshot_windows_processes():
    import ctypes
    from ctypes import wintypes

    class ProcessEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_snapshot = kernel32.CreateToolhelp32Snapshot
    create_snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    create_snapshot.restype = wintypes.HANDLE
    process_first = kernel32.Process32FirstW
    process_first.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32)]
    process_first.restype = wintypes.BOOL
    process_next = kernel32.Process32NextW
    process_next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32)]
    process_next.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]

    snapshot = create_snapshot(0x00000002, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        raise CapabilityError(f"无法读取进程列表：WinError {ctypes.get_last_error()}")
    processes = {}
    entry = ProcessEntry32()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        success = process_first(snapshot, ctypes.byref(entry))
        while success:
            pid = int(entry.th32ProcessID)
            processes[pid] = {
                "pid": pid,
                "parent_pid": int(entry.th32ParentProcessID),
                "name": entry.szExeFile,
            }
            success = process_next(snapshot, ctypes.byref(entry))
    finally:
        close_handle(snapshot)
    return processes


def detect_owner_process(start_pid=None):
    process_table = snapshot_processes()
    chain = build_ancestor_chain(process_table, start_pid or os.getppid())
    return select_owner_process(chain)


def read_json(path, default=None):
    if not path.exists():
        if default is not None:
            return default
        raise CapabilityError(f"文件不存在：{path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CapabilityError(f"JSON 格式错误：{path} 第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}") from exc


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def output_error(message, code="error", **extra):
    payload = {"ok": False, "error": {"code": code, "message": str(message)}}
    payload.update(extra)
    print_json(payload)


def load_mcps():
    data = read_json(MCPS_REGISTRY, default=[])
    if not isinstance(data, list):
        raise CapabilityError("mcps/registry.json 必须是数组")
    return data


def find_mcp(name_or_id):
    candidates = [item for item in load_mcps() if item.get("enabled", True)]
    for item in candidates:
        if item.get("id") == name_or_id or item.get("name") == name_or_id:
            return item
    raise CapabilityError(f"找不到已启用 MCP：{name_or_id}")


def validate_mcp_item(item):
    for key in ("id", "name", "description", "remark", "enabled", "transport", "params"):
        if key not in item:
            raise CapabilityError(f"MCP 注册项缺少字段：{key}")
    transport = item["transport"]
    params = item["params"]
    if not isinstance(params, dict):
        raise CapabilityError("MCP params 必须是对象")
    if transport == "stdio":
        if not params.get("command"):
            raise CapabilityError("stdio MCP 缺少 params.command")
        if "args" in params and not isinstance(params["args"], list):
            raise CapabilityError("stdio MCP 的 params.args 必须是数组")
        if "env" in params and not isinstance(params["env"], dict):
            raise CapabilityError("stdio MCP 的 params.env 必须是对象")
    elif transport == "streamable_http":
        if not params.get("url"):
            raise CapabilityError("streamable_http MCP 缺少 params.url")
        if "headers" in params and not isinstance(params["headers"], dict):
            raise CapabilityError("streamable_http MCP 的 params.headers 必须是对象")
    else:
        raise CapabilityError(f"不支持的 MCP transport：{transport}")


def read_session(mcp_id):
    path = SESSION_DIR / f"{mcp_id}.json"
    if not path.exists():
        return None
    return read_json(path)


def write_session(mcp_id, data):
    path = SESSION_DIR / f"{mcp_id}.json"
    write_json(path, data)


def delete_session(mcp_id):
    path = SESSION_DIR / f"{mcp_id}.json"
    if path.exists():
        path.unlink()


def delete_session_if_pid(mcp_id, pid):
    session = read_session(mcp_id)
    if session is None or session.get("pid") != pid:
        return False
    delete_session(mcp_id)
    return True


def close_session(mcp_id):
    session = read_session(mcp_id)
    if session is None:
        return False
    pid = session.get("pid")
    watcher = None
    if pid is not None:
        try:
            watcher = OwnerWatcher(pid)
        except CapabilityError:
            watcher = None
    shutdown_sent = False
    relay_url = session.get("relay_url")
    shutdown_token = session.get("shutdown_token")
    if session.get("transport") == "stdio_relay" and relay_url and shutdown_token:
        request = urllib.request.Request(
            f"{relay_url}/shutdown",
            data=json.dumps({"token": shutdown_token}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                shutdown_sent = response.status == 200
        except (urllib.error.URLError, TimeoutError, OSError):
            shutdown_sent = False
    if shutdown_sent and watcher:
        deadline = time.monotonic() + 3
        alive = watcher.is_alive()
        while alive and time.monotonic() < deadline:
            time.sleep(0.05)
            alive = watcher.is_alive()
        shutdown_sent = not alive
    if pid is not None and not shutdown_sent:
        if os.name == "nt" and session.get("kill_process_tree", True):
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
    if watcher:
        watcher.close()
    delete_session(mcp_id)
    return True


def kill_stale_session(mcp_id):
    close_session(mcp_id)

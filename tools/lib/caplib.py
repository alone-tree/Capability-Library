import json
import os
import signal
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MCPS_REGISTRY = ROOT / "mcps" / "registry.json"
SESSION_DIR = Path(tempfile.gettempdir()) / "capability-library" / "sessions"


class CapabilityError(Exception):
    pass


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


def kill_stale_session(mcp_id):
    session = read_session(mcp_id)
    if session is None:
        return
    pid = session.get("pid")
    if pid is None:
        delete_session(mcp_id)
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        pass
    delete_session(mcp_id)

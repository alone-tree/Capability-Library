import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.caplib import (
    ROOT,
    CapabilityError,
    find_mcp,
    kill_stale_session,
    output_error,
    print_json,
    validate_mcp_item,
    write_session,
)
from mcp.mcp_client import open_mcp_client


def main():
    parser = argparse.ArgumentParser(description="加载 MCP 并返回完整工具描述（默认保持连接）")
    parser.add_argument("--name", required=True, help="MCP 名称或 ID")
    parser.add_argument("--no-keep-alive", action="store_true", help="一次性连接，不保持")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    try:
        item = find_mcp(args.name)
        validate_mcp_item(item)

        if args.no_keep_alive:
            with open_mcp_client(item, timeout=args.timeout) as client:
                tools = client.list_tools()
            print_json({"ok": True, "mcp": _summarize(item), "tools": tools})
            return

        kill_stale_session(item["id"])

        client = open_mcp_client(item, timeout=args.timeout)
        client.__enter__()
        tools = client.list_tools()

        if item["transport"] == "stdio":
            port, relay_pid = _spawn_relay(item)
            write_session(item["id"], {
                "mcp_id": item["id"],
                "transport": "stdio_relay",
                "relay_url": f"http://127.0.0.1:{port}",
                "pid": relay_pid,
            })
            client.__exit__(None, None, None)
            print_json({
                "ok": True,
                "mcp": _summarize(item),
                "tools": tools,
                "session": {"relay_url": f"http://127.0.0.1:{port}"},
            })

        else:
            write_session(item["id"], {
                "mcp_id": item["id"],
                "transport": "streamable_http",
                "url": item["params"]["url"],
                "headers": item["params"].get("headers", {}),
                "session_id": client.session_id,
            })
            client.__exit__(None, None, None)
            print_json({
                "ok": True,
                "mcp": _summarize(item),
                "tools": tools,
                "session": {"session_id": client.session_id},
            })

    except CapabilityError as exc:
        output_error(exc, code="load_mcp_failed")


def _spawn_relay(item):
    """启动独立的 relay 子进程，返回端口号。"""
    relay_script = ROOT / "tools" / "mcp" / "relay.py"
    params_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="caplib_relay_", delete=False, encoding="utf-8"
    )
    params_file.write(json.dumps(item["params"], ensure_ascii=False))
    params_file.close()

    proc = subprocess.Popen(
        [sys.executable, str(relay_script), params_file.name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )

    port = None
    for _ in range(60):
        line = proc.stdout.readline()
        if not line:
            break
        if line.startswith("RELAY_READY"):
            port = int(line.strip().split("=")[1])
            break

    if port is None:
        stderr = proc.stderr.read()
        raise CapabilityError(f"Relay 启动失败：{stderr}")

    return port, proc.pid


def _summarize(item):
    return {
        "id": item["id"],
        "name": item["name"],
        "description": item["description"],
        "remark": item["remark"],
        "transport": item["transport"],
    }


if __name__ == "__main__":
    main()

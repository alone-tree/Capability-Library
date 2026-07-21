import argparse
import json
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.caplib import (
    ROOT,
    CapabilityError,
    close_session,
    detect_owner_process,
    find_mcp,
    kill_stale_session,
    output_error,
    print_json,
    snapshot_processes,
    validate_mcp_item,
    write_session,
)
from mcp.mcp_client import open_mcp_client


def main():
    parser = argparse.ArgumentParser(description="加载 MCP 并返回完整工具描述（默认不保持连接）")
    parser.add_argument("--name", required=True, help="MCP 名称或 ID")
    keep_alive_group = parser.add_mutually_exclusive_group()
    keep_alive_group.add_argument("--keep-alive", action="store_true", help="保持 stdio MCP 会话供后续调用复用")
    keep_alive_group.add_argument("--no-keep-alive", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--close", action="store_true", help="关闭已有的保活会话")
    parser.add_argument("--idle-timeout", type=float, default=300, help="保活会话空闲超时秒数，0 表示禁用")
    parser.add_argument("--owner", choices=("auto", "none"), default="auto", help="Owner 进程识别方式")
    parser.add_argument("--owner-pid", type=int, help="手动指定 Owner PID，优先于 --owner")
    parser.add_argument("--no-kill-process-tree", action="store_true", help="关闭 MCP 时保留其派生子进程")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    try:
        item = find_mcp(args.name)
        validate_mcp_item(item)
        if args.idle_timeout < 0:
            raise CapabilityError("--idle-timeout 不能小于 0")
        if args.owner_pid is not None and args.owner_pid <= 0:
            raise CapabilityError("--owner-pid 必须是正整数")

        if args.close:
            closed = close_session(item["id"])
            print_json({"ok": True, "mcp": _summarize(item), "closed": closed})
            return

        if not args.keep_alive:
            with open_mcp_client(item, timeout=args.timeout) as client:
                tools = client.list_tools()
            print_json({"ok": True, "mcp": _summarize(item), "tools": tools})
            return

        kill_stale_session(item["id"])

        with open_mcp_client(item, timeout=args.timeout) as client:
            tools = client.list_tools()
            session_id = getattr(client, "session_id", None)

        if item["transport"] == "stdio":
            owner = None if args.owner == "none" and args.owner_pid is None else _resolve_owner(args.owner_pid)
            port, relay_pid, shutdown_token = _spawn_relay(
                item,
                idle_timeout=args.idle_timeout,
                owner=owner,
                kill_process_tree=not args.no_kill_process_tree,
            )
            write_session(item["id"], {
                "mcp_id": item["id"],
                "transport": "stdio_relay",
                "relay_url": f"http://127.0.0.1:{port}",
                "pid": relay_pid,
                "shutdown_token": shutdown_token,
                "kill_process_tree": not args.no_kill_process_tree,
            })
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
                "session_id": session_id,
            })
            print_json({
                "ok": True,
                "mcp": _summarize(item),
                "tools": tools,
                "session": {"session_id": session_id},
            })

    except CapabilityError as exc:
        output_error(exc, code="load_mcp_failed")


def _resolve_owner(owner_pid):
    if owner_pid is None:
        return detect_owner_process()
    owner = snapshot_processes().get(owner_pid)
    if owner is None:
        raise CapabilityError(f"找不到指定的 Owner 进程：PID {owner_pid}")
    return owner


def _spawn_relay(item, idle_timeout=300, owner=None, kill_process_tree=True):
    """启动独立的 relay 子进程，返回端口号。"""
    relay_script = ROOT / "tools" / "mcp" / "relay.py"
    params_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="caplib_relay_", delete=False, encoding="utf-8"
    )
    shutdown_token = secrets.token_urlsafe(32)
    config = {
        "mcp": item["params"],
        "idle_timeout": idle_timeout,
        "shutdown_token": shutdown_token,
        "owner": owner,
        "kill_process_tree": kill_process_tree,
        "mcp_id": item["id"],
    }
    params_file.write(json.dumps(config, ensure_ascii=False))
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

    return port, proc.pid, shutdown_token


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

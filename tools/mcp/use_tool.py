import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.caplib import (
    CapabilityError,
    delete_session,
    find_mcp,
    output_error,
    print_json,
    read_session,
    validate_mcp_item,
)
from mcp.mcp_client import (
    call_tool_via_http_session,
    call_tool_via_relay,
    open_mcp_client,
)


def main():
    parser = argparse.ArgumentParser(description="调用具体 MCP 工具")
    parser.add_argument("--mcp", required=True, help="MCP 名称或 ID")
    parser.add_argument("--tool", required=True, help="工具名")
    params_group = parser.add_mutually_exclusive_group()
    params_group.add_argument("--params-json", help="工具参数 JSON 对象")
    params_group.add_argument("--params-file", help="工具参数 JSON 文件")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    try:
        params = _load_params(args)
        if not isinstance(params, dict):
            raise CapabilityError("参数必须是 JSON 对象")

        item = find_mcp(args.mcp)
        validate_mcp_item(item)

        session = read_session(item["id"])
        if session:
            result = _call_via_session(session, args.tool, params, args.timeout)
        else:
            with open_mcp_client(item, timeout=args.timeout) as client:
                result = client.call_tool(args.tool, params)

        print_json({"ok": True, "mcp": {"id": item["id"], "name": item["name"]}, "tool": args.tool, "result": result})

    except json.JSONDecodeError as exc:
        output_error(f"--params-json 格式错误：第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}", code="invalid_params_json")
    except CapabilityError as exc:
        output_error(exc, code="use_tool_failed")


def _call_via_session(session, tool, params, timeout):
    transport = session.get("transport")
    try:
        if transport == "stdio_relay":
            return call_tool_via_relay(session["relay_url"], tool, params, timeout)
        if transport == "streamable_http":
            return call_tool_via_http_session(session, tool, params, timeout)
        raise CapabilityError(f"未知的 session transport：{transport}")
    except CapabilityError:
        delete_session(session.get("mcp_id", ""))
        raise


def _load_params(args):
    if args.params_file:
        try:
            return json.loads(Path(args.params_file).read_text(encoding="utf-8"))
        except OSError as exc:
            raise CapabilityError(f"无法读取参数文件：{args.params_file}") from exc
    return json.loads(args.params_json or "{}")


if __name__ == "__main__":
    main()

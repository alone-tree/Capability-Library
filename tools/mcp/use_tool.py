import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.caplib import CapabilityError, find_mcp, output_error, print_json, validate_mcp_item
from mcp.mcp_client import open_mcp_client


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
        params = load_params(args)
        if not isinstance(params, dict):
            raise CapabilityError("--params-json 必须是 JSON 对象")
        item = find_mcp(args.mcp)
        validate_mcp_item(item)
        with open_mcp_client(item, timeout=args.timeout) as client:
            result = client.call_tool(args.tool, params)
        print_json({"ok": True, "mcp": {"id": item["id"], "name": item["name"]}, "tool": args.tool, "result": result})
    except json.JSONDecodeError as exc:
        output_error(f"--params-json 格式错误：第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}", code="invalid_params_json")
    except CapabilityError as exc:
        output_error(exc, code="use_tool_failed")


def load_params(args):
    if args.params_file:
        try:
            return json.loads(Path(args.params_file).read_text(encoding="utf-8"))
        except OSError as exc:
            raise CapabilityError(f"无法读取参数文件：{args.params_file}") from exc
    return json.loads(args.params_json or "{}")


if __name__ == "__main__":
    main()

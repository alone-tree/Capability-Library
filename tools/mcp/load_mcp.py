import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.caplib import CapabilityError, find_mcp, output_error, print_json, validate_mcp_item
from mcp.mcp_client import open_mcp_client


def main():
    parser = argparse.ArgumentParser(description="加载 MCP 并返回完整工具描述")
    parser.add_argument("--name", required=True, help="MCP 名称或 ID")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    try:
        item = find_mcp(args.name)
        validate_mcp_item(item)
        with open_mcp_client(item, timeout=args.timeout) as client:
            tools = client.list_tools()
        print_json({"ok": True, "mcp": summarize_mcp(item), "tools": tools})
    except CapabilityError as exc:
        output_error(exc, code="load_mcp_failed")


def summarize_mcp(item):
    return {
        "id": item["id"],
        "name": item["name"],
        "description": item["description"],
        "remark": item["remark"],
        "transport": item["transport"],
    }


if __name__ == "__main__":
    main()

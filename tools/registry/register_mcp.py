import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.caplib import (
    CapabilityError,
    MCPS_REGISTRY,
    load_mcps,
    output_error,
    print_json,
    random_id,
    validate_mcp_item,
    write_json,
)
from registry.refresh_manifest_md import refresh_mcps_md


def main():
    parser = argparse.ArgumentParser(description="注册 MCP 到能力库注册表")
    parser.add_argument("--name", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--remark", default="")
    parser.add_argument("--transport", required=True, choices=["stdio", "streamable_http"])
    params_group = parser.add_mutually_exclusive_group(required=True)
    params_group.add_argument("--params-json")
    params_group.add_argument("--params-file")
    args = parser.parse_args()
    try:
        params = load_params(args)
        if not isinstance(params, dict):
            raise CapabilityError("--params-json 必须是 JSON 对象")
        mcps = load_mcps()
        ensure_unique(mcps, args.name)
        item = {
            "id": random_id("mcp"),
            "name": args.name,
            "description": args.description,
            "remark": args.remark,
            "enabled": True,
            "transport": args.transport,
            "params": params,
        }
        validate_mcp_item(item)
        mcps.append(item)
        write_json(MCPS_REGISTRY, mcps)
        refresh_mcps_md(mcps)
        print_json({"ok": True, "mcp": item})
    except json.JSONDecodeError as exc:
        output_error(f"--params-json 格式错误：第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}", code="invalid_params_json")
    except CapabilityError as exc:
        output_error(exc, code="register_mcp_failed")


def ensure_unique(mcps, name):
    for item in mcps:
        if item.get("name") == name:
            raise CapabilityError(f"MCP 名称已存在：{name}")


def load_params(args):
    if args.params_file:
        try:
            return json.loads(Path(args.params_file).read_text(encoding="utf-8"))
        except OSError as exc:
            raise CapabilityError(f"无法读取参数文件：{args.params_file}") from exc
    return json.loads(args.params_json)


if __name__ == "__main__":
    main()

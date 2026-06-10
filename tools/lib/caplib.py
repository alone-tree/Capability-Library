import json
import os
import re
import secrets
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILLS_MANIFEST = ROOT / "skills" / "manifest.json"
MCPS_REGISTRY = ROOT / "mcps" / "registry.json"
CONFIG_LOCAL = ROOT / "config.local.json"
CONFIG_EXAMPLE = ROOT / "config.example.json"


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


def random_id(prefix):
    return f"{prefix}_{secrets.token_hex(6)}"


def load_skills():
    data = read_json(SKILLS_MANIFEST, default=[])
    if not isinstance(data, list):
        raise CapabilityError("skills/manifest.json 必须是数组")
    return data


def load_mcps():
    data = read_json(MCPS_REGISTRY, default=[])
    if not isinstance(data, list):
        raise CapabilityError("mcps/registry.json 必须是数组")
    return data


def resolve_config_value(value, config=None):
    if not isinstance(value, str):
        return value
    config = config or load_config(optional=True)

    def replace(match):
        name = match.group(1)
        if name in os.environ:
            return os.environ[name]
        secrets_map = config.get("secrets", {})
        if name in secrets_map:
            return str(secrets_map[name])
        return match.group(0)

    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", replace, value)


def resolve_placeholders(obj, config=None):
    if isinstance(obj, dict):
        return {key: resolve_placeholders(value, config) for key, value in obj.items()}
    if isinstance(obj, list):
        return [resolve_placeholders(value, config) for value in obj]
    return resolve_config_value(obj, config)


def load_config(optional=False):
    if not CONFIG_LOCAL.exists():
        if optional:
            return {}
        raise CapabilityError("缺少 config.local.json。请复制 config.example.json 并填入配置。")
    data = read_json(CONFIG_LOCAL)
    if not isinstance(data, dict):
        raise CapabilityError("config.local.json 必须是对象")
    return data


def find_mcp(name_or_id):
    candidates = [item for item in load_mcps() if item.get("enabled", True)]
    for item in candidates:
        if item.get("id") == name_or_id or item.get("name") == name_or_id:
            return item
    raise CapabilityError(f"找不到已启用 MCP：{name_or_id}")


def validate_skill_item(item):
    for key in ("id", "name", "path", "description", "remark", "enabled"):
        if key not in item:
            raise CapabilityError(f"Skill 清单项缺少字段：{key}")
    path = (ROOT / item["path"]).resolve()
    skills_root = (ROOT / "skills").resolve()
    if not str(path).startswith(str(skills_root)):
        raise CapabilityError("Skill 路径必须在 skills/ 目录内")
    if not path.exists():
        raise CapabilityError(f"Skill 文件不存在：{item['path']}")


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

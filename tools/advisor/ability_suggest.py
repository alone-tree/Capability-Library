import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.caplib import (
    CapabilityError,
    CONFIG_EXAMPLE,
    CONFIG_LOCAL,
    ROOT,
    load_config,
    load_mcps,
    load_skills,
    output_error,
    print_json,
)


def main():
    parser = argparse.ArgumentParser(description="向前台咨询 LLM 询问可用能力")
    parser.add_argument("query", help="自然语言需求描述")
    parser.add_argument("--scope", choices=["local", "remote", "all"], default="local", help="第一版只实现 local")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    try:
        if args.scope != "local":
            raise CapabilityError("第一版只实现本地能力库，remote/all 仅为未来扩展预留")
        skills = [item for item in load_skills() if item.get("enabled", True)]
        mcps = [item for item in load_mcps() if item.get("enabled", True)]
        guide = read_guide()
        raw = ask_deepseek(args.query, guide, skills, mcps, args.timeout)
        suggested = parse_model_json(raw)
        print_json(enrich_suggestions(suggested, skills, mcps))
    except CapabilityError as exc:
        output_error(exc, code="ability_suggest_failed")


def read_guide():
    path = ROOT / "skills" / "capability-library-guide" / "SKILL.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def ask_deepseek(query, guide, skills, mcps, timeout):
    config = load_config()
    deepseek = config.get("deepseek", {})
    api_key = deepseek.get("api_key")
    if not api_key or api_key == "填入你的 DeepSeek API Key":
        raise CapabilityError(f"DeepSeek API Key 未配置。请根据 {CONFIG_EXAMPLE.name} 创建 {CONFIG_LOCAL.name}。")
    base_url = deepseek.get("base_url", "https://api.deepseek.com/chat/completions")
    model = deepseek.get("model", "deepseek-chat")
    prompt = build_prompt(query, guide, skills, mcps)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是能力库前台咨询。只返回 JSON，不要返回 Markdown。推荐必须来自给定清单。",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        base_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise CapabilityError(f"DeepSeek 请求失败：{exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise CapabilityError(f"DeepSeek 连接失败：{exc}") from exc
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise CapabilityError(f"DeepSeek 响应格式异常：{data}") from exc


def build_prompt(query, guide, skills, mcps):
    visible_mcps = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "description": item.get("description"),
            "remark": item.get("remark"),
            "transport": item.get("transport"),
        }
        for item in mcps
    ]
    return (
        "请根据用户需求，从能力库中推荐相关 Skill 和 MCP。\n"
        "返回 JSON 格式：\n"
        "{\n"
        "  \"skills\": [{\"id\": \"...\", \"name\": \"...\", \"reason\": \"...\"}],\n"
        "  \"mcps\": [{\"id\": \"...\", \"name\": \"...\", \"reason\": \"...\"}],\n"
        "  \"summary\": \"简短建议\"\n"
        "}\n\n"
        f"用户需求：{query}\n\n"
        f"能力库说明：\n{guide}\n\n"
        f"Skill 清单：\n{json.dumps(skills, ensure_ascii=False, indent=2)}\n\n"
        f"MCP 注册表：\n{json.dumps(visible_mcps, ensure_ascii=False, indent=2)}\n"
    )


def parse_model_json(raw):
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CapabilityError(f"前台咨询返回的不是合法 JSON：{raw}") from exc
    if not isinstance(data, dict):
        raise CapabilityError("前台咨询 JSON 顶层必须是对象")
    return data


def enrich_suggestions(suggested, skills, mcps):
    skill_map = build_lookup(skills)
    mcp_map = build_lookup(mcps)
    return {
        "ok": True,
        "summary": suggested.get("summary", ""),
        "skills": [enrich_skill(item, skill_map) for item in suggested.get("skills", [])],
        "mcps": [enrich_mcp(item, mcp_map) for item in suggested.get("mcps", [])],
    }


def build_lookup(items):
    result = {}
    for item in items:
        result[item.get("id")] = item
        result[item.get("name")] = item
    return result


def enrich_skill(suggestion, lookup):
    source = lookup.get(suggestion.get("id")) or lookup.get(suggestion.get("name"))
    if not source:
        return {"missing": True, "reason": suggestion.get("reason", ""), "raw": suggestion}
    return {
        "id": source["id"],
        "name": source["name"],
        "path": str((ROOT / source["path"]).resolve()),
        "relative_path": source["path"],
        "description": source["description"],
        "remark": source["remark"],
        "reason": suggestion.get("reason", ""),
    }


def enrich_mcp(suggestion, lookup):
    source = lookup.get(suggestion.get("id")) or lookup.get(suggestion.get("name"))
    if not source:
        return {"missing": True, "reason": suggestion.get("reason", ""), "raw": suggestion}
    return {
        "id": source["id"],
        "name": source["name"],
        "description": source["description"],
        "remark": source["remark"],
        "transport": source["transport"],
        "reason": suggestion.get("reason", ""),
    }


if __name__ == "__main__":
    main()

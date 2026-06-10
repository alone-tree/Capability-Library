from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.caplib import CapabilityError, ROOT, load_mcps, load_skills, output_error


def main():
    try:
        refresh_skills_md(load_skills())
        refresh_mcps_md(load_mcps())
        print("ok")
    except CapabilityError as exc:
        output_error(exc, code="refresh_manifest_failed")


def refresh_skills_md(skills):
    lines = ["# Skill 清单", "", "> 本文件由 `tools/registry/refresh_manifest_md.py` 根据 `skills/manifest.json` 生成。", ""]
    if not skills:
        lines.append("当前没有已注册 Skill。")
    for item in skills:
        lines.extend(
            [
                f"## {item.get('name', '')}",
                "",
                f"- ID：`{item.get('id', '')}`",
                f"- 路径：`{item.get('path', '')}`",
                f"- 启用：{'是' if item.get('enabled', True) else '否'}",
                f"- 描述：{item.get('description', '')}",
                f"- 备注：{item.get('remark', '')}",
                "",
            ]
        )
    (ROOT / "skills" / "manifest.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def refresh_mcps_md(mcps):
    lines = ["# MCP 注册表", "", "> 本文件由 `tools/registry/refresh_manifest_md.py` 根据 `mcps/registry.json` 生成。", ""]
    if not mcps:
        lines.append("当前没有已注册 MCP。")
    for item in mcps:
        lines.extend(
            [
                f"## {item.get('name', '')}",
                "",
                f"- ID：`{item.get('id', '')}`",
                f"- 启用：{'是' if item.get('enabled', True) else '否'}",
                f"- 传输：`{item.get('transport', '')}`",
                f"- 描述：{item.get('description', '')}",
                f"- 备注：{item.get('remark', '')}",
                "",
            ]
        )
    (ROOT / "mcps" / "registry.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

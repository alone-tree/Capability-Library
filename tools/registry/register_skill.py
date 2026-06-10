import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.caplib import (
    CapabilityError,
    ROOT,
    SKILLS_MANIFEST,
    load_skills,
    output_error,
    print_json,
    random_id,
    validate_skill_item,
    write_json,
)
from registry.refresh_manifest_md import refresh_skills_md


def main():
    parser = argparse.ArgumentParser(description="注册 Skill 到能力库清单")
    parser.add_argument("--name", required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--remark", default="")
    args = parser.parse_args()
    try:
        skills = load_skills()
        ensure_unique(skills, args.name, args.path)
        item = {
            "id": random_id("skill"),
            "name": args.name,
            "path": normalize_skill_path(args.path),
            "description": args.description,
            "remark": args.remark,
            "enabled": True,
        }
        validate_skill_item(item)
        skills.append(item)
        write_json(SKILLS_MANIFEST, skills)
        refresh_skills_md(skills)
        print_json({"ok": True, "skill": item})
    except CapabilityError as exc:
        output_error(exc, code="register_skill_failed")


def normalize_skill_path(path_text):
    path = Path(path_text)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError as exc:
            raise CapabilityError("Skill 路径必须在能力库仓库内") from exc
    return path.as_posix()


def ensure_unique(skills, name, path):
    normalized = normalize_skill_path(path)
    for item in skills:
        if item.get("name") == name:
            raise CapabilityError(f"Skill 名称已存在：{name}")
        if item.get("path") == normalized:
            raise CapabilityError(f"Skill 路径已存在：{normalized}")


if __name__ == "__main__":
    main()

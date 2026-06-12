"""将能力库安全同步到用户目录。

用法：
    python scripts/deploy.py <目标目录>
    python scripts/deploy.py <目标目录> --replace-user-data
"""

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

UPDATE_DIRS = ["tools", "docs", "tests", "scripts", "skills", "mcps"]
UPDATE_FILES = ["README.md", "config.example.json", ".gitignore", ".gitattributes", "LICENSE"]
USER_DATA_FILES = {
    Path("config.local.json"),
    Path("skills") / "manifest.json",
    Path("skills") / "manifest.md",
    Path("mcps") / "registry.json",
    Path("mcps") / "registry.md",
}


def _copy_tree_merge(src, dst, replace_user_data=False):
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        project_rel = Path(src.name) / rel

        if project_rel in USER_DATA_FILES and not replace_user_data:
            continue

        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def main():
    parser = argparse.ArgumentParser(description="安全同步能力库到用户目录")
    parser.add_argument("target", help="目标目录路径")
    parser.add_argument(
        "--replace-user-data",
        action="store_true",
        help="同时覆盖 skills/manifest.* 和 mcps/registry.* 等用户数据",
    )
    args = parser.parse_args()

    target = Path(args.target).resolve()
    if target == ROOT:
        print("目标目录不能是当前开发目录。", file=sys.stderr)
        sys.exit(1)

    if not target.exists():
        print(f"目标目录不存在，将创建：{target}")
        target.mkdir(parents=True)

    for name in UPDATE_DIRS:
        src = ROOT / name
        if not src.exists():
            continue
        _copy_tree_merge(src, target / name, args.replace_user_data)

    for name in UPDATE_FILES:
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, target / name)

    mode = "覆盖用户数据" if args.replace_user_data else "安全更新"
    print(f"{mode}完成 → {target}")


if __name__ == "__main__":
    main()

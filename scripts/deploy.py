"""将能力库部署到用户目录。

用法：
    python scripts/deploy.py <目标目录>            # 更新代码，保留用户数据
    python scripts/deploy.py <目标目录> --overwrite # 覆盖模式：连用户能力清单一起覆盖
"""

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 每次部署都完整覆盖的代码目录
CODE_DIRS = ["tools"]
# 只更新内置 Skill，不碰用户自建 Skill
BUILTIN_SKILLS = ["skills/capability-library-maintenance"]
# 参考文档
DOC_DIRS = ["docs"]
# 根目录文件
ROOT_FILES = ["README.md", "LICENSE"]
# 首次部署时从模板创建，后续不覆盖
TEMPLATE_FILES = [
    ("templates/CAPABILITY.md", "CAPABILITY.md"),
    ("templates/mcps/registry.json", "mcps/registry.json"),
]
# --overwrite 时额外覆盖
OVERWRITE_DIRS = ["mcps"]
OVERWRITE_FILES = ["CAPABILITY.md"]


def _copy_dir(src, dst):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _ensure_parent(path):
    path.parent.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="部署能力库到用户目录")
    parser.add_argument("target", help="目标目录路径")
    parser.add_argument("--overwrite", action="store_true", help="覆盖模式：连用户能力清单一起覆盖")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    target.mkdir(parents=True, exist_ok=True)

    # 代码目录：完整覆盖
    for name in CODE_DIRS:
        src = ROOT / name
        if src.exists():
            _copy_dir(src, target / name)

    # 内置 Skill：只更新指定目录，不动用户自建 Skill
    for name in BUILTIN_SKILLS:
        src = ROOT / name
        dst = target / name
        if src.exists():
            _copy_dir(src, dst)

    # 文档
    for name in DOC_DIRS:
        src = ROOT / name
        if src.exists():
            _copy_dir(src, target / name)

    # 根目录文件
    for name in ROOT_FILES:
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, target / name)

    # 模板文件：仅缺失时创建
    for src_rel, dst_rel in TEMPLATE_FILES:
        dst = target / dst_rel
        if not dst.exists():
            _ensure_parent(dst)
            shutil.copy2(ROOT / src_rel, dst)

    # 覆盖模式
    if args.overwrite:
        for name in OVERWRITE_DIRS:
            src = ROOT / name
            if src.exists():
                _copy_dir(src, target / name)
        for name in OVERWRITE_FILES:
            src = ROOT / name
            if src.exists():
                shutil.copy2(src, target / name)

    mode = "覆盖" if args.overwrite else "更新"
    print(f"{mode}完成 → {target}")


if __name__ == "__main__":
    main()

"""将能力库部署到用户目录。

用法：
    python scripts/deploy.py <目标目录>            # 更新模式：只更新代码
    python scripts/deploy.py <目标目录> --overwrite # 覆盖模式：全量覆盖
"""

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

UPDATE_DIRS = ["tools", "skills", "docs", "tests", "scripts"]
UPDATE_FILES = ["README.md", "config.example.json", ".gitignore", ".gitattributes", "LICENSE"]
OVERWRITE_DIRS = ["mcps"]  # 覆盖模式下额外覆盖
PRESERVE_FILES = ["config.local.json"]


def _copy_dir(src, dst):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def main():
    parser = argparse.ArgumentParser(description="部署能力库到用户目录")
    parser.add_argument("target", help="目标目录路径")
    parser.add_argument("--overwrite", action="store_true", help="覆盖模式：连 mcps/ 一起更新（保留 config.local.json）")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    if not target.exists():
        print(f"目标目录不存在，将创建：{target}")
        target.mkdir(parents=True)

    # 更新代码文件
    for name in UPDATE_DIRS:
        src = ROOT / name
        if not src.exists():
            continue
        _copy_dir(src, target / name)

    for name in UPDATE_FILES:
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, target / name)

    # 覆盖模式：额外覆盖 mcps/
    if args.overwrite:
        for name in OVERWRITE_DIRS:
            src = ROOT / name
            if not src.exists():
                continue
            _copy_dir(src, target / name)

    # 确保存在但不覆盖
    for name in PRESERVE_FILES:
        dst = target / name
        if not dst.exists():
            src = ROOT / name
            if src.exists():
                shutil.copy2(src, dst)

    mode = "覆盖" if args.overwrite else "更新"
    print(f"{mode}完成 → {target}")


if __name__ == "__main__":
    main()

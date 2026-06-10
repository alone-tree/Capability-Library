import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "releases"

EXCLUDE_SUFFIXES = {".pyc"}
EXCLUDE_NAMES = {"__pycache__", ".git", ".codegraph", ".pytest_cache", "releases"}
EXCLUDE_FILES = {"config.local.json"}


def should_exclude(path, root):
    if path.name in EXCLUDE_FILES:
        return True
    rel = path.relative_to(root)
    for part in rel.parts:
        if part in EXCLUDE_NAMES:
            return True
    return False


def build_release(output_name=None):
    if output_name is None:
        output_name = "capability-library"

    RELEASES.mkdir(parents=True, exist_ok=True)
    build_dir = RELEASES / output_name
    zip_path = RELEASES / f"{output_name}.zip"

    if build_dir.exists():
        shutil.rmtree(build_dir)
    if zip_path.exists():
        zip_path.unlink()

    build_dir.mkdir()

    for item in ROOT.iterdir():
        if should_exclude(item, ROOT):
            continue
        dest = build_dir / item.name
        if item.is_dir():
            _copy_dir(item, dest)
        else:
            shutil.copy2(item, dest)

    _make_zip(build_dir, zip_path)
    shutil.rmtree(build_dir)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Release built: {zip_path} ({size_mb:.1f} MB)")


def _copy_dir(src, dst):
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in EXCLUDE_NAMES:
            continue
        if item.name in EXCLUDE_FILES:
            continue
        if item.suffix in EXCLUDE_SUFFIXES:
            continue
        dest = dst / item.name
        if item.is_dir():
            _copy_dir(item, dest)
        else:
            shutil.copy2(item, dest)


def _make_zip(src_dir, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in src_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(src_dir.parent)
                zf.write(file_path, arcname)


def main():
    parser = argparse.ArgumentParser(description="打包能力库 release zip")
    parser.add_argument("--name", default="capability-library", help="输出文件名（不含扩展名）")
    args = parser.parse_args()

    try:
        build_release(args.name)
    except Exception as exc:
        print(f"打包失败: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

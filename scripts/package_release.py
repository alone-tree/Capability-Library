"""使用部署清单构建仅供新用户首次安装的能力库压缩包。"""

import argparse
import sys
import tempfile
import zipfile
from pathlib import Path

from deploy import deploy


ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "releases"


def _make_zip(source_dir, zip_path):
    """把临时用户实例打包，并保留顶层目录名。"""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(source_dir.parent))


def build_release(output_name="capability-library-user", releases_dir=None):
    """从空目录执行一次部署，确保安装包与真实首次安装完全一致。"""
    destination = Path(releases_dir) if releases_dir else RELEASES
    destination.mkdir(parents=True, exist_ok=True)
    zip_path = destination / f"{output_name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    with tempfile.TemporaryDirectory() as temp_dir:
        user_root = Path(temp_dir) / output_name
        deploy(user_root)
        _make_zip(user_root, zip_path)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"用户版安装包已生成：{zip_path}（{size_mb:.1f} MB）")
    return zip_path


def main():
    parser = argparse.ArgumentParser(description="构建能力库新用户安装包")
    parser.add_argument(
        "--name", default="capability-library-user", help="输出文件名（不含扩展名）"
    )
    args = parser.parse_args()

    try:
        build_release(args.name)
    except Exception as exc:
        print(f"打包失败：{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

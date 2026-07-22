"""按文件将能力库程序更新到用户目录，同时保留全部用户数据。

用法：
    python scripts/deploy.py <目标目录>
    python scripts/deploy.py <目标目录> --check
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ".caplib/deploy-state.json"
STATE_FORMAT = 1

# 开发版拥有的通用程序和用户说明。源文件与用户版目标文件显式对应。
MANAGED_FILES = (
    ("user-version/README.md", "README.md"),
    ("LICENSE", "LICENSE"),
    ("tools/lib/__init__.py", "tools/lib/__init__.py"),
    ("tools/lib/caplib.py", "tools/lib/caplib.py"),
    ("tools/mcp/__init__.py", "tools/mcp/__init__.py"),
    ("tools/mcp/echo_mcp.py", "tools/mcp/echo_mcp.py"),
    ("tools/mcp/load_mcp.py", "tools/mcp/load_mcp.py"),
    ("tools/mcp/mcp_client.py", "tools/mcp/mcp_client.py"),
    ("tools/mcp/relay.py", "tools/mcp/relay.py"),
    ("tools/mcp/use_tool.py", "tools/mcp/use_tool.py"),
)

# 用户数据模板只在首次安装、目标文件不存在时创建，以后永不覆盖。
SEED_FILES = (
    ("templates/CAPABILITY.md", "CAPABILITY.md"),
    ("templates/capability-entry/SKILL.md", "capability-entry/SKILL.md"),
    ("templates/mcps/registry.json", "mcps/registry.json"),
)

# 这些路径属于用户。受管文件清单不得进入这些范围。
PROTECTED_FILES = {"CAPABILITY.md"}
PROTECTED_PREFIXES = ("capability-entry/", "skills/", "mcps/")
ENTRY_README_MARKERS = ("../README.md", "capability-library/README.md")


def _safe_relative(path):
    """拒绝绝对路径和目录穿越，部署状态文件不能扩大写入范围。"""
    candidate = Path(path)
    if candidate.is_absolute() or not candidate.parts:
        raise ValueError(f"不是安全的相对路径：{path}")
    if any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError(f"不是安全的相对路径：{path}")
    return candidate.as_posix()


def _validate_manifest():
    """阻止开发者误把用户文件加入自动覆盖清单。"""
    seen = set()
    seen_sources = set()
    for source_raw, target_raw in MANAGED_FILES:
        source = _safe_relative(source_raw)
        target = _safe_relative(target_raw)
        if source in seen_sources:
            raise ValueError(f"受管源文件重复：{source}")
        if target in seen:
            raise ValueError(f"受管目标文件重复：{target}")
        if target in PROTECTED_FILES or target.startswith(PROTECTED_PREFIXES):
            raise ValueError(f"受管文件进入用户数据范围：{target}")
        if not (ROOT / source).is_file():
            raise FileNotFoundError(f"开发版受管源文件不存在：{source}")
        seen_sources.add(source)
        seen.add(target)

    for source_raw, target_raw in SEED_FILES:
        source = _safe_relative(source_raw)
        target = _safe_relative(target_raw)
        if not (ROOT / source).is_file():
            raise FileNotFoundError(f"用户模板不存在：{source}")
        if target in seen:
            raise ValueError(f"模板目标与受管文件冲突：{target}")


def _sha256(path):
    """计算文件哈希；大文件按块读取。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_copy(source, target):
    """先复制到同目录临时文件，再原子替换目标文件。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    os.close(file_descriptor)
    temp_path = Path(temp_name)
    try:
        shutil.copy2(source, temp_path)
        os.replace(temp_path, target)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _atomic_write_json(target, data):
    """以 UTF-8 无 BOM 原子写入部署状态。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    file_descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        os.replace(temp_path, target)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _load_state(target):
    """读取旧部署状态；缺失或损坏时按首次接管处理，不删除任何文件。"""
    state_path = target / STATE_FILE
    if not state_path.is_file():
        return {"format": STATE_FORMAT, "managed_files": {}}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"format": STATE_FORMAT, "managed_files": {}}
    if state.get("format") != STATE_FORMAT:
        return {"format": STATE_FORMAT, "managed_files": {}}
    managed_files = state.get("managed_files")
    if not isinstance(managed_files, dict):
        managed_files = {}
    return {"format": STATE_FORMAT, "managed_files": managed_files}


def _remove_empty_parents(path, stop):
    """只清理删除受管文件后产生的空目录，不越过目标根目录。"""
    current = path.parent
    while current != stop and current.is_dir():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _entry_migration_warning(target):
    """提醒老用户手动把统一 README 接入自定义入口。"""
    entry = target / "capability-entry" / "SKILL.md"
    if not entry.is_file():
        return None
    try:
        content = entry.read_text(encoding="utf-8")
    except OSError:
        return "无法读取 capability-entry/SKILL.md，请手动确认用户版 README 入口。"
    normalized_content = content.replace("\\", "/")
    if not any(marker in normalized_content for marker in ENTRY_README_MARKERS):
        return (
            "capability-entry/SKILL.md 是用户文件，更新器未修改；"
            "当前入口尚未引用用户版 README 中的 MCP 使用说明，需要手动迁移。"
        )
    return None


def deploy(target, check=False):
    """执行或预览文件级更新，返回便于测试和展示的结果。"""
    _validate_manifest()
    target = Path(target).resolve()
    old_state = _load_state(target)
    old_managed = old_state["managed_files"]
    managed_sources = {
        _safe_relative(target): ROOT / _safe_relative(source)
        for source, target in MANAGED_FILES
    }
    source_hashes = {
        target_path: _sha256(source_path)
        for target_path, source_path in managed_sources.items()
    }
    result = {
        "created": [],
        "updated": [],
        "unchanged": [],
        "seeded": [],
        "preserved": [],
        "removed": [],
        "warnings": [],
    }

    for relative_path, source_hash in source_hashes.items():
        source = managed_sources[relative_path]
        destination = target / relative_path
        if destination.is_file() and _sha256(destination) == source_hash:
            result["unchanged"].append(relative_path)
            continue
        action = "updated" if destination.exists() else "created"
        result[action].append(relative_path)
        if not check:
            _atomic_copy(source, destination)

    for source_raw, target_raw in SEED_FILES:
        source_relative = _safe_relative(source_raw)
        target_relative = _safe_relative(target_raw)
        destination = target / target_relative
        if destination.exists():
            result["preserved"].append(target_relative)
            continue
        result["seeded"].append(target_relative)
        if not check:
            _atomic_copy(ROOT / source_relative, destination)

    current_managed = set(source_hashes)
    for raw_path, deployed_hash in sorted(old_managed.items()):
        try:
            relative_path = _safe_relative(raw_path)
        except ValueError:
            result["warnings"].append(f"忽略部署状态中的不安全路径：{raw_path}")
            continue
        if relative_path in current_managed:
            continue
        destination = target / relative_path
        if not destination.is_file():
            continue
        if _sha256(destination) != deployed_hash:
            result["preserved"].append(relative_path)
            result["warnings"].append(
                f"旧受管文件已被用户修改，予以保留：{relative_path}"
            )
            continue
        result["removed"].append(relative_path)
        if not check:
            destination.unlink()
            _remove_empty_parents(destination, target)

    warning = _entry_migration_warning(target)
    if warning:
        result["warnings"].append(warning)

    new_state = {"format": STATE_FORMAT, "managed_files": source_hashes}
    state_path = target / STATE_FILE
    state_changed = True
    if state_path.is_file():
        try:
            state_changed = json.loads(state_path.read_text(encoding="utf-8")) != new_state
        except (OSError, json.JSONDecodeError):
            state_changed = True
    if not check and state_changed:
        _atomic_write_json(state_path, new_state)

    return result


def _print_result(result, check):
    """输出简洁、可审计的更新摘要。"""
    prefix = "将" if check else "已"
    labels = (
        ("created", f"{prefix}创建"),
        ("updated", f"{prefix}更新"),
        ("seeded", f"{prefix}初始化"),
        ("removed", f"{prefix}删除旧受管文件"),
        ("unchanged", "无需更新"),
        ("preserved", "保持不变"),
    )
    for key, label in labels:
        paths = result[key]
        if paths:
            print(f"{label}（{len(paths)}）：")
            for path in paths:
                print(f"  {path}")
    for warning in result["warnings"]:
        print(f"警告：{warning}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="按文件更新能力库并保留用户数据")
    parser.add_argument("target", help="用户版能力库目录")
    parser.add_argument(
        "--check", action="store_true", help="只预览将发生的变化，不写入文件"
    )
    args = parser.parse_args()

    try:
        result = deploy(args.target, check=args.check)
    except Exception as exc:
        print(f"更新失败：{exc}", file=sys.stderr)
        sys.exit(1)

    _print_result(result, args.check)
    mode = "检查完成" if args.check else "更新完成"
    print(f"{mode} → {Path(args.target).resolve()}")


if __name__ == "__main__":
    main()

"""代码探索Agent处理器"""

import platform
import subprocess
from pathlib import Path
from typing import Any, Dict


def _find_rg() -> str:
    """查找 ripgrep 或回退到系统 grep"""
    import shutil

    rg = shutil.which("rg")
    if rg:
        return rg
    if platform.system() == "Windows":
        find = shutil.which("findstr")
        if find:
            return find
    return shutil.which("grep") or "grep"


async def handler(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    """处理代码探索请求"""
    action = args.get("action", "explore")
    target = args.get("target", "")
    path = args.get("path", ".") or "."

    if action == "explore":
        return _directory_tree(path, max_depth=3)

    elif action == "find_symbol":
        rg = _find_rg()
        try:
            result = subprocess.run(
                [rg, "--no-heading", "-n", target, path], capture_output=True, text=True, timeout=30
            )
            return result.stdout.strip() or f"未找到符号: {target}"
        except Exception as e:
            return f"搜索失败: {e}"

    elif action == "find_definitions":
        rg = _find_rg()
        pattern = rf"^(def|class|async def)\s+{target}" if target else r"^(def|class|async def)\s+"
        try:
            result = subprocess.run(
                [rg, "--no-heading", "-n", pattern, path], capture_output=True, text=True, timeout=30
            )
            return result.stdout.strip() or f"未找到定义: {target}"
        except Exception as e:
            return f"搜索失败: {e}"

    elif action == "find_references":
        rg = _find_rg()
        try:
            result = subprocess.run(
                [rg, "--no-heading", "-n", target, path], capture_output=True, text=True, timeout=30
            )
            return result.stdout.strip() or f"未找到引用: {target}"
        except Exception as e:
            return f"搜索失败: {e}"

    elif action == "analyze_structure":
        return _project_analyze(path)

    else:
        return f"未知动作: {action}"


def _directory_tree(root: str, max_depth: int = 3) -> str:
    """生成目录树"""
    root_path = Path(root)
    if not root_path.exists():
        return f"路径不存在: {root}"
    lines = [f"项目结构: {root_path.absolute()}"]
    for item in sorted(root_path.iterdir()):
        _walk(item, "", 1, max_depth, lines)
    return "\n".join(lines)


def _walk(item: Path, prefix: str, depth: int, max_depth: int, lines: list) -> None:
    if depth > max_depth:
        return
    if item.name.startswith(".") and item.name not in (".env", ".gitignore"):
        return
    if item.name in ("node_modules", "__pycache__", ".git", "dist", "build"):
        return
    connector = "└── " if depth == max_depth or not _has_visible_children(item, depth, max_depth) else "├── "
    lines.append(f"{prefix}{connector}{item.name}{'/' if item.is_dir() else ''}")
    if item.is_dir():
        for child in sorted(item.iterdir()):
            _walk(child, prefix + "│   ", depth + 1, max_depth, lines)


def _has_visible_children(item: Path, depth: int, max_depth: int) -> bool:
    if depth >= max_depth or not item.is_dir():
        return False
    for child in item.iterdir():
        if child.name.startswith(".") or child.name in ("node_modules", "__pycache__", ".git", "dist", "build"):
            continue
        return True
    return False


def _project_analyze(path: str) -> str:
    """项目文件统计"""
    root = Path(path)
    if not root.exists():
        return f"路径不存在: {path}"

    stats = {"py": 0, "js": 0, "ts": 0, "java": 0, "go": 0, "other": 0}
    total_lines = 0

    for file in root.rglob("*"):
        if file.is_file():
            ext = file.suffix.lstrip(".")
            if ext in stats:
                stats[ext] += 1
            else:
                stats["other"] += 1
            try:
                total_lines += len(file.read_text(encoding="utf-8", errors="ignore").split("\n"))
            except Exception:
                pass

    return (
        f"项目分析: {root.absolute()}\n"
        + f"总文件数: {sum(stats.values())}\n"
        + f"总行数: {total_lines}\n"
        + f"Python: {stats['py']}, JS: {stats['js']}, TS: {stats['ts']}, "
        + f"Java: {stats['java']}, Go: {stats['go']}, Other: {stats['other']}"
    )


__skill_meta__ = {
    "name": "code_explorer",
    "version": "1.0.0",
    "description": "代码探索Agent - 分析项目结构、理解代码关系",
}

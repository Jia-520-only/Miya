"""Code architect agent handler"""

import subprocess
from pathlib import Path
from typing import Any, Dict


def _directory_tree(root: str, max_depth: int = 2) -> str:
    root_path = Path(root)
    if not root_path.exists():
        return f"路径不存在: {root}"
    lines = [f"{root_path.absolute()}"]
    for item in sorted(root_path.iterdir()):
        _walk(item, "", 1, max_depth, lines)
    return "\n".join(lines)


def _walk(item: Path, prefix: str, depth: int, max_depth: int, lines: list) -> None:
    if depth > max_depth:
        return
    if item.name.startswith(".") or item.name in ("node_modules", "__pycache__", ".git", "dist", "build"):
        return
    lines.append(f"{prefix}├── {item.name}{'/' if item.is_dir() else ''}")
    if item.is_dir():
        for child in sorted(item.iterdir()):
            _walk(child, prefix + "│   ", depth + 1, max_depth, lines)


def _project_analyze(root: str) -> str:
    path = Path(root)
    if not path.exists():
        return f"路径不存在: {root}"
    stats = {"py": 0, "js": 0, "ts": 0, "java": 0, "go": 0, "other": 0}
    total_lines = 0
    for file in path.rglob("*"):
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
        f"项目: {path.absolute()}\n"
        + f"文件: {sum(stats.values())} 个, 行数: {total_lines}\n"
        + f"Python: {stats['py']}, JS: {stats['js']}, TS: {stats['ts']}, "
        + f"Java: {stats['java']}, Go: {stats['go']}, Other: {stats['other']}"
    )


async def handler(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Handle code architecture requests"""
    action = args.get("action", "design")
    target = args.get("target", "")
    requirements = args.get("requirements", "")

    if action == "design" or action == "structure":
        return await _design_architecture(target)
    elif action == "plan_modules":
        return await _plan_modules(target, requirements)
    elif action == "refactor":
        return await _refactor_analysis(target)
    elif action == "analyze_dependencies":
        return await _analyze_dependencies(target)
    else:
        return f"Unknown action: {action}"


async def _design_architecture(target: str) -> str:
    """Design architecture analysis"""
    project_info = _project_analyze(target or ".")

    languages = []
    if "Python" in project_info:
        languages.append("Python")
    if "JavaScript" in project_info or "TypeScript" in project_info:
        languages.append("JS/TS")
    if "Java" in project_info:
        languages.append("Java")

    report = f"""=== Architecture Design Analysis ===

Project: {target or "current directory"}

Project Info:
{project_info}

Architecture Suggestions:"""

    if not languages:
        report += "\n- Cannot detect project language"
    elif "Python" in languages:
        report += """
Recommended patterns:
- Modular design: split by functionality
- Data layer: separate database/api
- Service layer: business logic
- Interface layer: API/CLI

Suggested structure:
project/
├── core/          # core business
├── models/        # data models
├── services/      # service layer
├── api/           # API interfaces
├── utils/         # utilities
└── tests/         # tests
"""

    return report


async def _plan_modules(target: str, requirements: str) -> str:
    """Plan module structure"""
    report = f"""=== Module Planning ===

Target: {target or "new module"}
Requirements: {requirements or "not specified"}"""

    if not requirements:
        report += """

Please provide requirements, e.g.:
- "user management system"
- "API service"
- "data processing pipeline"
"""
        return report

    if "user" in requirements.lower() or "auth" in requirements.lower():
        report += """

User-related modules:
- user/models.py        # user model
- user/auth.py          # auth logic
- user/validators.py     # validators
- user/service.py       # user service
"""

    if "api" in requirements.lower() or "interface" in requirements.lower():
        report += """

API-related modules:
- api/routes.py         # route definitions
- api/middleware.py     # middleware
- api/serializers.py    # serializers
- api/views.py          # views
"""

    if "data" in requirements.lower() or "database" in requirements.lower():
        report += """

Data layer modules:
- database/connection.py    # connection management
- database/models.py        # data models
- database/repositories.py  # repository pattern
- database/migrations.py   # migrations
"""

    return report


async def _refactor_analysis(target: str) -> str:
    """Refactoring analysis"""
    tree = _directory_tree(target or ".", max_depth=2)

    issues = []

    if tree.count("\n") < 10:
        issues.append("  - Flat structure, suggest layering")

    if "tests" not in tree.lower() and "test" not in tree.lower():
        issues.append("  - Missing test directory")

    if "docs" not in tree.lower() and "doc" not in tree.lower():
        issues.append("  - Missing docs directory")

    report = f"""=== Refactoring Analysis: {target or "current project"} ===

Current structure:
{tree[:500]}"""

    if issues:
        report += "\n\nIssues found:"
        report += "\n".join(issues)
    else:
        report += "\n\nStructure looks reasonable"

    report += """

Refactoring suggestions:
1. Separate concerns - organize by functionality
2. Dependency injection - reduce coupling
3. Interface abstraction - define clear interfaces
4. Error handling - unified exception handling
"""

    return report


async def _analyze_dependencies(target: str) -> str:
    """Analyze dependencies"""
    cmd = "pip list" if target.endswith(".py") or not target else "npm list"
    try:
        result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=30, shell=False)
        deps = result.stdout
    except Exception as e:
        return f"Cannot get dependency list: {e}"

    lines = [l for l in deps.split("\n") if l.strip() and not l.startswith("==")]
    count = len([l for l in lines if "==" in l or "@" in l])

    report = f"""=== Dependency Analysis ===

Target: {target or "current project"}

Dependencies: {count}

List:
"""

    for line in lines[:20]:
        if "==" in line or "@" in line:
            report += f"  - {line.strip()}\n"

    if count > 50:
        report += """
Warning: Many dependencies
- Check for unused dependencies
- Avoid duplicate functionality
- Consider lighter alternatives
"""

    return report


__skill_meta__ = {
    "name": "code_architect",
    "version": "1.0.0",
    "description": "Code architecture agent - design, planning, refactoring",
}

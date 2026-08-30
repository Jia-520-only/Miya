"""代码审查Agent处理器"""

import re
from pathlib import Path
from typing import Any, Dict


async def handler(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    """处理代码审查请求"""
    action = args.get("action", "review")
    target = args.get("target", "")

    if not target:
        return "Error: No target specified"

    try:
        code = Path(target).read_text(encoding="utf-8")
    except Exception as e:
        return f"Error: Cannot read {target} - {e}"

    if action == "review" or action == "analyze_quality":
        return _analyze_quality(code, target)
    elif action == "find_bugs":
        return _find_bugs(code, target)
    elif action == "check_errors":
        return _check_errors(code, target)
    elif action == "security_scan":
        return _security_scan(code, target)
    else:
        return f"Unknown action: {action}"


def _analyze_quality(code: str, target: str) -> str:
    """分析代码质量"""
    lines = code.split("\n")
    total_lines = len([l for l in lines if l.strip()])
    blank_lines = len([l for l in lines if not l.strip()])
    comment_lines = len([l for l in lines if l.strip().startswith(("#", "//"))])

    functions = re.findall(r"def\s+(\w+)\s*\(", code)
    classes = re.findall(r"class\s+(\w+)", code)
    imports = re.findall(r"^import\s+(\w+)|^from\s+(\w+)", code, re.MULTILINE)

    complexity = 0
    for line in lines:
        if any(kw in line for kw in ["if ", "elif ", "for ", "while ", "and ", "or "]):
            complexity += 1

    report = f"""=== Code Quality Analysis: {target} ===

Stats:
- Total lines: {len(lines)}
- Code lines: {total_lines}
- Blank lines: {blank_lines}
- Comment lines: {comment_lines}

Structure:
- Functions: {len(functions)}
- Classes: {len(classes)}
- Imports: {len(set(imports))}

Complexity: {complexity} branches

Suggestions:"""

    if complexity > 20:
        report += "\n- High complexity, consider splitting functions"
    if len(functions) > 20:
        report += "\n- Many functions, consider modularizing"
    if comment_lines / max(total_lines, 1) < 0.1:
        report += "\n- Low comments, consider adding documentation"

    return report


def _find_bugs(code: str, target: str) -> str:
    """查找潜在bug"""
    issues = []

    bug_patterns = [
        (r"==\s*=", "Possible use of = instead of ==", "WARN"),
        (r"\.append\([^)]*\+[^)]*\)", "Chained append may have issues", "NOTE"),
        (r"except\s*:", "Bare except catches all exceptions", "WARN"),
        (r"print\s*\(", "Using print for debugging", "HINT"),
        (r"# TODO", "TODO marker exists", "HINT"),
    ]

    lines = code.split("\n")
    for i, line in enumerate(lines, 1):
        for pattern, msg, level in bug_patterns:
            if re.search(pattern, line):
                issues.append(f"  [{level}] Line {i}: {msg}")
                issues.append(f"    {line.strip()[:60]}")

    if not issues:
        return f"[OK] No obvious bugs found: {target}"

    return f"""=== Bug Detection: {target} ===

Found {len(issues) // 2} issues:
""" + "\n".join(issues)


def _check_errors(code: str, target: str) -> str:
    """检查错误处理"""
    issues = []

    if "try:" not in code and "except" not in code:
        issues.append("  - Missing exception handling")

    if ".get(" in code and "default" not in code:
        issues.append("  - Some .get() calls missing default values")

    empty_funcs = re.findall(r"def\s+(\w+)\s*\([^)]*\)\s*:\s*\n\s*(?:pass|...)", code)
    if empty_funcs:
        for func in empty_funcs:
            issues.append(f"  - Function {func} is empty")

    if not issues:
        return f"[OK] Error handling check passed: {target}"

    return f"""=== Error Handling Check: {target} ===

Found {len(issues)} issues:
""" + "\n".join(issues)


def _security_scan(code: str, target: str) -> str:
    """安全扫描"""
    issues = []

    security_patterns = [
        (r"eval\s*\(", "Using eval has security risk", "HIGH"),
        (r"exec\s*\(", "Using exec has security risk", "HIGH"),
        (r"os\.system\s*\(", "Using os.system has injection risk", "MEDIUM"),
        (r"subprocess\.\s*shell\s*=\s*True", "shell=True has injection risk", "HIGH"),
        (r'password\s*=\s*["\']', "Hardcoded password", "HIGH"),
        (r'api[_-]?key\s*=\s*["\']', "Hardcoded API key", "HIGH"),
        (r"pickle\.load\s*\(", "Pickle deserialization risk", "MEDIUM"),
    ]

    lines = code.split("\n")
    for i, line in enumerate(lines, 1):
        for pattern, msg, level in security_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                issues.append(f"  [{level}] Line {i}: {msg}")
                issues.append(f"    {line.strip()[:60]}")

    if not issues:
        return f"[OK] Security scan passed: {target}"

    return f"""=== Security Scan: {target} ===

Found {len(issues) // 2} security issues:
""" + "\n".join(issues)


__skill_meta__ = {
    "name": "code_reviewer",
    "version": "1.0.0",
    "description": "Code review agent - quality, bug detection, security scan",
}

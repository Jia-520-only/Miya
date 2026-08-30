"""
Performance Analyzer Agent - 性能分析
分析代码性能问题
"""

import re
from pathlib import Path
from typing import Any, Dict


async def handler(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    """处理性能分析请求"""
    target = args.get("target", ".")
    action = args.get("action", "analyze")

    if action == "analyze":
        return await _analyze_performance(target)
    else:
        return f"未知动作: {action}"


async def _analyze_performance(target: str) -> str:
    """分析性能问题"""
    path = Path(target)
    if not path.exists():
        return f"目标不存在: {target}"

    issues = []

    patterns = [
        (r"for\s+.*\s+in\s+.*:\s+for\s+", "嵌套循环", "O(n²) 复杂度"),
        (r"while\s+True:", "无限循环风险", "检查循环终止条件"),
        (r"\.append\s*\(\s*for\s+", "列表推导式在 append", "使用列表推导式"),
        (r"re\.compile\s*\(\s*\)", "正则未缓存", "预编译正则表达式"),
        (r"json\.loads?\s*\(\s*\)", "JSON 频繁解析", "考虑缓存解析结果"),
        (r"\.get\s*\(\s*['\"]\s*\)", "字典频繁 get", "考虑使用 defaultdict"),
        (r"sleep\s*\(\s*0\s*\)", "无意义 sleep", "移除不必要的延迟"),
    ]

    file_types = ["*.py"]

    for ext in file_types:
        for file in path.rglob(ext):
            if "__pycache__" in str(file):
                continue

            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    for pattern, issue_type, suggestion in patterns:
                        if re.search(pattern, line):
                            issues.append(
                                {
                                    "file": str(file),
                                    "line": i,
                                    "type": issue_type,
                                    "suggestion": suggestion,
                                    "code": line.strip()[:60],
                                }
                            )
            except:
                pass

    if not issues:
        return "✅ 未发现明显性能问题"

    result = f"⚠️ 发现 {len(issues)} 个性能问题:\n\n"
    for i, issue in enumerate(issues[:20], 1):
        result += f"{i}. [{issue['type']}]\n"
        result += f"   {issue['file']}:{issue['line']}\n"
        result += f"   {issue['code']}\n"
        result += f"   💡 {issue['suggestion']}\n\n"

    if len(issues) > 20:
        result += f"... 还有 {len(issues) - 20} 个问题"

    return result

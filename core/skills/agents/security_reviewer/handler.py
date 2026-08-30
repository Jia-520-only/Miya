"""
Security Reviewer Agent - 安全审查
检测代码中的安全漏洞和风险
"""

import re
from pathlib import Path
from typing import Any, Dict


async def handler(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    """处理安全审查请求"""
    target = args.get("target", ".")
    action = args.get("action", "scan")

    if action == "scan":
        return await _scan_security(target)
    else:
        return f"未知动作: {action}"


async def _scan_security(target: str) -> str:
    """扫描安全问题"""
    path = Path(target)
    if not path.exists():
        return f"目标不存在: {target}"

    issues = []

    patterns = [
        (r"password\s*=\s*['\"][^'\"]+['\"]", "硬编码密码"),
        (r"api[_-]?key\s*=\s*['\"][^'\"]+['\"]", "硬编码 API Key"),
        (r"secret\s*=\s*['\"][^'\"]+['\"]", "硬编码 Secret"),
        (r"token\s*=\s*['\"][^'\"]+['\"]", "硬编码 Token"),
        (r"os\.system\s*\(", "os.system 调用"),
        (r"eval\s*\(", "eval 调用"),
        (r"exec\s*\(", "exec 调用"),
        (r"subprocess\.\w+\s*\(\s*shell\s*=\s*True", "Shell 注入风险"),
        (r"pickle\.loads?\s*\(", "Pickle 反序列化"),
        (r"yaml\.load\s*\(", "YAML 注入"),
    ]

    file_types = ["*.py", "*.js", "*.ts", "*.java", "*.go"]

    for ext in file_types:
        for file in path.rglob(ext):
            if "node_modules" in str(file) or "__pycache__" in str(file):
                continue

            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                for pattern, issue_type in patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        issues.append({"file": str(file), "type": issue_type, "pattern": pattern})
            except:
                pass

    if not issues:
        return "✅ 未发现明显安全问题"

    result = f"⚠️ 发现 {len(issues)} 个安全问题:\n\n"
    for i, issue in enumerate(issues[:20], 1):
        result += f"{i}. [{issue['type']}]\n   {issue['file']}\n\n"

    if len(issues) > 20:
        result += f"... 还有 {len(issues) - 20} 个问题"

    return result

"""DSH 统一执行路由。

DSH 能覆盖终端、文件、代码和项目编排类任务。这个模块只处理边界
上的能力归并：旧工具仍可保留在注册表中供兼容代码使用，但模型看到
的工具目录和新的执行入口统一收敛到 ``mcp_dsh_execute``。
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

DSH_EXECUTE_TOOL = "mcp_dsh_execute"

# 这些入口的职责已经被 DSH 覆盖。保留实现是为了兼容旧插件和外部调用，
# 但不再把它们作为模型的平行选择。
DSH_OWNED_TOOLS = frozenset(
    {
        "mcp_code_executor_execute",
        "mcp_filesystem_read_file",
        "mcp_filesystem_write_file",
        "mcp_filesystem_delete_file",
        "mcp_filesystem_list_files",
        "mcp_filesystem_search_files",
        "python_interpreter",
        "terminal_execute",
        "terminal_command",
        "terminal_exec",
        "multi_terminal",
        "code_execute",
        "file_read",
        "file_write",
        "file_edit",
        "execute_shell",
        "python_exec",
        "grep",
        "file_delete",
        "directory_tree",
        "file_grep",
        "file_glob",
        "project_analyze",
        "git_status",
        "git_diff",
        "git_log",
        "git_branch",
        "git_commit",
        "git_push",
        "git_pull",
        "git_checkout",
        "git_stash",
        "project_context",
        "task_plan",
        "suggestions",
        "list_skills",
    }
)

DSH_TOOL_ALIASES = {name: DSH_EXECUTE_TOOL for name in DSH_OWNED_TOOLS}

# 权限配置中的旧节点。DSH 合并了这些执行边界后，已有用户授权仍应
# 继续生效；权限检查会按候选顺序优先尝试规范节点。
DSH_PERMISSION_ALIASES = {
    DSH_EXECUTE_TOOL: (
        "terminal.execute",
        "terminal_command",
        "file_access",
        "code_generator",
    ),
}


def is_dsh_owned_tool(name: str) -> bool:
    """判断工具是否属于 DSH 已覆盖的兼容入口。"""

    return name in DSH_OWNED_TOOLS


def permission_tool_names(name: str) -> List[str]:
    """返回权限检查应兼容的工具名顺序。

    新授权统一使用规范入口；旧别名保留在候选列表中，避免迁移期间
    已有授权突然失效。执行本身仍只会走规范后的 DSH 工具。
    """

    canonical = canonical_tool_name(name)
    names = [canonical]
    if canonical != name:
        names.append(name)
    names.extend(DSH_PERMISSION_ALIASES.get(canonical, ()))
    return list(dict.fromkeys(names))


def canonical_tool_name(name: str) -> str:
    """返回模型和执行边界使用的规范工具名。"""

    return DSH_TOOL_ALIASES.get(name, name)


def canonical_tool_names(names: Iterable[str]) -> List[str]:
    """归并旧入口并保持原顺序。"""

    return list(dict.fromkeys(canonical_tool_name(name) for name in names))


def collapse_dsh_schemas(schemas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """隐藏 DSH 已覆盖的重复 schema。

    若当前注册表还没有 DSH，则保留旧工具，确保启动顺序或降级环境下
    仍然可用。调用方得到的是新的列表，不会修改注册表中的原对象。
    """

    names = {schema.get("function", {}).get("name") for schema in schemas if isinstance(schema, dict)}
    if DSH_EXECUTE_TOOL not in names:
        return list(schemas)

    result: List[Dict[str, Any]] = []
    seen = set()
    for schema in schemas:
        name = schema.get("function", {}).get("name") if isinstance(schema, dict) else None
        if not name:
            result.append(schema)
            continue
        canonical = canonical_tool_name(name)
        if canonical == DSH_EXECUTE_TOOL and name != DSH_EXECUTE_TOOL:
            continue
        if name in seen:
            continue
        seen.add(name)
        result.append(schema)
    return result


def _json_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _compat_task(tool_name: str, args: Dict[str, Any]) -> str:
    """把旧工具参数转换为 DSH 可执行的自然语言任务。"""

    if args.get("task"):
        return str(args["task"])

    if tool_name == "mcp_code_executor_execute":
        language = args.get("language", "代码")
        return f"执行以下 {language} 代码：\n{args.get('code', '')}"
    if tool_name in {"mcp_filesystem_read_file", "file_read"}:
        task = f"读取文件：{args.get('file_path', args.get('path', ''))}"
        if args.get("offset") is not None or args.get("limit") is not None:
            task += f"（offset={args.get('offset', 0)}, limit={args.get('limit', '')}）"
        return task
    if tool_name in {"mcp_filesystem_write_file", "file_write", "file_edit"}:
        if tool_name == "file_edit":
            return (
                f"将文件 {args.get('path', '')} 中的以下内容替换：\n"
                f"旧内容：\n{args.get('old', '')}\n新内容：\n{args.get('new', '')}"
            )
        mode = args.get("mode", "w")
        operation = "追加到文件末尾" if mode == "a" else f"按模式 {mode} 写入或编辑"
        return f"{operation}文件 {args.get('file_path', args.get('path', ''))}，内容如下：\n{args.get('content', '')}"
    if tool_name in {"mcp_filesystem_delete_file", "file_delete"}:
        return f"删除文件或目录：{args.get('file_path', args.get('path', ''))}"
    if tool_name in {"mcp_filesystem_list_files", "directory_tree"}:
        return f"列出目录 {args.get('path', '.')} 的文件，pattern={args.get('pattern', '*')}，recursive={args.get('recursive', False)}"
    if tool_name in {"mcp_filesystem_search_files", "file_grep", "file_glob"}:
        return f"搜索文件：pattern={args.get('pattern', '')}，path={args.get('path', '.')}，include={args.get('include', '')}"
    if tool_name == "python_interpreter":
        return f"执行以下 Python 代码：\n{args.get('code', '')}"
    if tool_name == "execute_shell":
        return f"在当前项目中执行以下 Shell 命令：\n{args.get('command', '')}"
    if tool_name == "python_exec":
        return f"执行以下 Python 代码：\n{args.get('code', '')}"
    if tool_name == "grep":
        return (
            f"在目录 {args.get('path', '.')} 中搜索文本 {args.get('pattern', '')}，"
            f"文件匹配模式为 {args.get('file_pattern', '*')}。"
        )
    if tool_name.startswith("git_"):
        return f"在当前项目中执行 Git 操作 {tool_name[4:]}，参数：{_json_value(args)}"
    return f"执行兼容操作 {tool_name}，参数：{_json_value(args)}"


def adapt_dsh_call(tool_name: str, args: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """将旧执行入口转换为 ``mcp_dsh_execute`` 调用。"""

    canonical = canonical_tool_name(tool_name)
    if canonical != DSH_EXECUTE_TOOL or tool_name == DSH_EXECUTE_TOOL:
        return tool_name, dict(args)

    call_args: Dict[str, Any] = {
        "task": _compat_task(tool_name, args),
        "timeout": args.get("timeout", 30 if tool_name in {"execute_shell", "python_exec"} else 300),
    }
    working_dir = args.get("working_dir") or args.get("workspace")
    if working_dir:
        call_args["working_dir"] = working_dir
    return DSH_EXECUTE_TOOL, call_args


def dsh_tool_available(tool_subnet: Any) -> bool:
    """Return whether a ToolNet instance exposes the canonical DSH tool."""

    if tool_subnet is None:
        return False
    try:
        return bool(tool_subnet.registry.get_tool(DSH_EXECUTE_TOOL))
    except Exception:
        try:
            return DSH_EXECUTE_TOOL in tool_subnet.get_tool_names()
        except Exception:
            return False


def parse_dsh_result(result: Any) -> Dict[str, Any]:
    """Normalize the JSON boundary returned by the DSH MCP service.

    Older or mocked ToolNet implementations may return a plain string. Keeping
    the raw value here lets API callers preserve their existing response shape
    while still exposing DSH's structured fields when available.
    """

    if isinstance(result, dict):
        payload = dict(result)
    elif isinstance(result, str):
        try:
            decoded = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            decoded = None
        if isinstance(decoded, dict):
            envelope_keys = {
                "success",
                "status",
                "output",
                "error",
                "exit_code",
                "structured_output",
            }
            if envelope_keys.intersection(decoded):
                payload = decoded
            else:
                payload = {"output": result, "structured_output": decoded}
        elif isinstance(decoded, list):
            payload = {"output": result, "structured_output": decoded}
        else:
            failed = result.startswith(("MCP 调用失败:", "MCP 调用异常:", "❌"))
            payload = {"output": result, "success": not failed}
    else:
        payload = {"output": str(result)}

    output = payload.get("output")
    structured = payload.get("structured_output")
    if output is None and structured is not None:
        output = structured

    # Some MCP bridges expose a JSON document only through ``output``. Decode
    # it once so file/task callers can consume structured data consistently.
    if structured is None and isinstance(output, str):
        try:
            decoded_output = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            decoded_output = None
        if isinstance(decoded_output, (dict, list)):
            payload["structured_output"] = decoded_output

    payload.setdefault("output", output if output is not None else "")
    if "success" not in payload:
        status = payload.get("status")
        if status in {"failed", "timed_out", "cancelled", "rejected"} or payload.get("error"):
            payload["success"] = False
        else:
            payload["success"] = status in {None, "completed"}
    return payload


async def execute_dsh(
    tool_subnet: Any,
    task: str,
    *,
    timeout: int = 300,
    working_dir: Optional[str] = None,
    user_id: Any = None,
    group_id: Any = None,
    platform: Optional[str] = None,
    sender_name: Optional[str] = None,
    tool_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute a task through the canonical ToolNet DSH boundary."""

    if not dsh_tool_available(tool_subnet):
        return {"success": False, "status": "unavailable", "error": "DSH 工具未初始化"}

    args: Dict[str, Any] = {"task": task, "timeout": timeout}
    if working_dir:
        args["working_dir"] = working_dir
    raw = await tool_subnet.execute_tool(
        tool_name=DSH_EXECUTE_TOOL,
        args=args,
        user_id=user_id,
        group_id=group_id,
        platform=platform,
        sender_name=sender_name,
        tool_context=tool_context,
    )
    return parse_dsh_result(raw)

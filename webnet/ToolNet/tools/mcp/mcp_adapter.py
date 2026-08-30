"""
MCPNet 工具适配器

将 MCP 服务的每个 capability 包装为 ToolNet 格式塔 Agent 的一等工具。
AI 模型在 function-calling schema 中直接看到它们，全平台均可调用。
"""

import logging
from typing import Any, Dict, List

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


# ─── OpenAI Function Schema 类型映射 ───

_TYPE_MAP: Dict[str, str] = {
    "string": "string",
    "number": "integer",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
}

_MCP_KEYWORDS: Dict[str, List[str]] = {
    "code_executor": ["执行", "运行", "命令", "代码", "脚本"],
    "screen_vision": ["屏幕", "截图", "看到", "显示", "看下", "界面", "报错"],
    "web_search": ["搜索", "搜索", "查找", "百度", "谷歌", "查一下"],
    "filesystem": ["文件", "读写", "写入", "删除文件", "目录"],
    "dsh": [
        "电脑",
        "桌面",
        "打开软件",
        "浏览器",
        "键盘",
        "鼠标",
        "文件操作",
        "执行命令",
        "创建项目",
        "搭建",
        "重构",
        "多步骤",
        "安装依赖",
        "构建",
        "编译",
        "自动化任务",
        "生成代码",
        "批量操作",
        "初始化",
        "配置环境",
        "分析代码",
        "修复bug",
    ],
}


def _parse_param_type(raw) -> str:
    """将 manifest 中的参数类型描述转为 OpenAI 类型"""
    if isinstance(raw, dict):
        raw = raw.get("type", "string")
    if not isinstance(raw, str):
        return "string"
    raw_lower = raw.strip().lower()
    for key, oai_type in _TYPE_MAP.items():
        if key in raw_lower:
            return oai_type
    return "string"


def _parse_param_desc(raw) -> str:
    """从 manifest 参数描述中提取人类可读描述"""
    if isinstance(raw, dict):
        return raw.get("description", "")
    if not isinstance(raw, str):
        return str(raw)
    if " - " in raw:
        return raw.split(" - ", 1)[1].strip()
    return raw


def _build_tool_schema(service_name: str, tool_def: Dict[str, Any]) -> Dict[str, Any]:
    """从 MCP 工具定义构建 OpenAI Function Calling schema"""
    tool_name = tool_def["name"]
    full_name = f"mcp_{service_name}_{tool_name}"
    description = tool_def.get("description", f"{service_name} {tool_name}")
    display_name = f"MCP {service_name}"

    params_raw: Dict[str, str] = tool_def.get("parameters", {})
    properties: Dict[str, Any] = {}
    required: List[str] = []

    for param_name, param_spec in params_raw.items():
        param_type = _parse_param_type(param_spec)
        param_desc = _parse_param_desc(param_spec)

        is_optional = "可选" in param_desc or "optional" in param_desc.lower()
        if not is_optional and param_name not in ("session_key", "workspace"):
            required.append(param_name)

        prop: Dict[str, Any] = {"type": param_type, "description": param_desc}
        if param_type == "array":
            prop["items"] = {"type": "string"}
        properties[param_name] = prop

    # 注入触发关键词
    keywords = _MCP_KEYWORDS.get(service_name, [])
    if keywords:
        description += f"\n(当用户提到以下内容时优先调用: {', '.join(keywords)})"

    return {
        "name": full_name,
        "description": f"[{display_name}] {description}",
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


class MCPTool(BaseTool):
    """MCP 服务格式塔工具适配器

    每个实例对应 MCP 服务的一个 capability。
    """

    def __init__(
        self,
        service_name: str,
        tool_name: str,
        tool_def: Dict[str, Any],
    ):
        self._service_name = service_name
        self._tool_name = tool_name
        self._tool_def = tool_def
        self._full_name = f"mcp_{service_name}_{tool_name}"
        self._schema = _build_tool_schema(service_name, tool_def)

    @property
    def config(self) -> Dict[str, Any]:
        return self._schema

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """调用 MCP 服务"""
        try:
            from core.mcp_manager import get_mcp_manager

            manager = get_mcp_manager()
            result = await manager.call(
                service_name=self._service_name,
                tool_name=self._tool_name,
                **args,
            )

            if result.success:
                response = str(result.result) if result.result else "完成"
                logger.info(f"[MCPNet] {self._full_name} 成功 (耗时 {result.execution_time:.2f}s)")
                return response
            else:
                error_msg = result.error or "未知错误"
                logger.error(f"[MCPNet] {self._full_name} 失败: {error_msg}")
                return f"MCP 调用失败: {error_msg}"

        except Exception as e:
            logger.error(f"[MCPNet] {self._full_name} 异常: {e}", exc_info=True)
            return f"MCP 调用异常: {str(e)[:300]}"


def discover_mcp_tools() -> List[MCPTool]:
    tools: List[MCPTool] = []

    try:
        from core.mcp_manager import get_mcp_manager

        manager = get_mcp_manager()
        if not manager._initialized:
            logger.warning("[MCPNet] MCP 服务尚未初始化")
            return tools

        for service_name, service in manager._services.items():
            try:
                manifest = service.manifest
                capabilities = manifest.capabilities
                tool_list: List[Dict] = capabilities.get("tools", [])

                for tool_def in tool_list:
                    tool = MCPTool(
                        service_name=service_name,
                        tool_name=tool_def["name"],
                        tool_def=tool_def,
                    )
                    tools.append(tool)
                    logger.info(f"[MCPNet] 已创建格式塔工具: {tool._full_name} ({manifest.display_name})")
            except Exception as e:
                logger.warning(f"[MCPNet] 服务 {service_name} 工具发现失败: {e}")

    except Exception as e:
        logger.warning(f"[MCPNet] 工具发现失败: {e}")

    return tools


async def reload_mcp_tools(registry=None):
    """MCP 就绪后重新加载 MCP 工具到 ToolNet 注册表"""
    if registry is None:
        from webnet.ToolNet import get_tool_registry

        registry = get_tool_registry()

    from core.mcp_manager import get_mcp_manager

    manager = get_mcp_manager()
    if not manager._initialized:
        await manager.initialize()

    tools = discover_mcp_tools()
    for tool in tools:
        # 跳过已注册的工具
        if registry.get_tool(tool._full_name):
            continue
        registry.register(tool)

    if tools:
        logger.info(f"[MCPNet] MCP 工具重载完成，新增 {len(tools)} 个工具")
    return len(tools)

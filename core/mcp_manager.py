"""MCP管理器 - 弥娅统一MCP服务管理系统

整合NagaAgent的MCP能力，提供：
- 统一的服务注册和发现
- 工具调用路由
- 服务生命周期管理
- 动态manifest加载
"""

import asyncio
import json
import importlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from core.constants import Encoding

logger = logging.getLogger(__name__)


@dataclass
class MCPCallResult:
    """MCP调用结果"""
    success: bool
    service_name: str
    tool_name: str = ""
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class MCPServiceManifest:
    """MCP服务清单"""
    name: str
    display_name: str
    description: str
    agent_type: str = "mcp"
    entry_point: Dict[str, str] = field(default_factory=dict)
    capabilities: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"
    enabled: bool = True


class MCPServiceInstance:
    """MCP服务实例包装"""

    def __init__(self, name: str, instance: Any, manifest: MCPServiceManifest):
        self.name = name
        self.instance = instance
        self.manifest = manifest
        self.call_count = 0
        self.last_called = None
        self.error_count = 0

    async def handle_handoff(self, tool_call: Dict[str, Any]) -> str:
        """调用agent的handle_handoff方法"""
        try:
            result = await self.instance.handle_handoff(tool_call)
            self.call_count += 1
            self.last_called = asyncio.get_event_loop().time()
            return result
        except Exception as e:
            self.error_count += 1
            raise


class MCPManager:
    """MCP服务管理器 - 统一管理所有MCP服务"""

    def __init__(self, mcp_dir: Optional[str] = None, auto_register: bool = True):
        self.mcp_dir = mcp_dir or "mcpserver"
        self.auto_register = auto_register

        # 服务注册表
        self._services: Dict[str, MCPServiceInstance] = {}
        self._manifests: Dict[str, MCPServiceManifest] = {}

        # 钩子函数
        self._pre_call_hooks: List[Callable] = []
        self._post_call_hooks: List[Callable] = []

        # 初始化
        if self.auto_register:
            asyncio.create_task(self.initialize())

    async def initialize(self):
        """初始化MCP管理器"""
        try:
            logger.info("[MCP] 正在扫描并注册MCP服务...")
            registered = await self.scan_and_register()
            logger.info(f"[MCP] 初始化完成，已注册 {len(registered)} 个服务: {registered}")
        except Exception as e:
            logger.error(f"[MCP] 初始化失败: {e}")

    async def scan_and_register(self) -> List[str]:
        """扫描目录并注册所有MCP服务"""
        d = Path(self.mcp_dir)
        if not d.exists():
            logger.warning(f"[MCP] MCP目录不存在: {self.mcp_dir}")
            return []

        registered = []
        for manifest_file in d.glob("**/agent-manifest.json"):
            try:
                manifest = self._load_manifest(manifest_file)
                if not manifest:
                    continue

                if await self.register_service(manifest):
                    registered.append(manifest.name)
                    logger.info(f"[MCP] ✅ 注册服务: {manifest.name} ({manifest.display_name})")

            except Exception as e:
                logger.error(f"[MCP] 处理manifest失败 {manifest_file}: {e}")

        return registered

    def _load_manifest(self, manifest_path: Path) -> Optional[MCPServiceManifest]:
        """加载manifest文件"""
        try:
            with open(manifest_path, "r", encoding=Encoding.UTF8) as f:
                data = json.load(f)

            return MCPServiceManifest(
                name=data.get("name") or data.get("displayName", ""),
                display_name=data.get("displayName", ""),
                description=data.get("description", ""),
                agent_type=data.get("agentType", "mcp"),
                entry_point=data.get("entryPoint", {}),
                capabilities=data.get("capabilities", {}),
                version=data.get("version", "1.0.0"),
                enabled=data.get("enabled", True)
            )
        except Exception as e:
            logger.error(f"[MCP] 加载manifest失败 {manifest_path}: {e}")
            return None

    async def register_service(self, manifest: MCPServiceManifest) -> bool:
        """注册单个MCP服务"""
        if not manifest.enabled:
            logger.debug(f"[MCP] 服务已禁用，跳过注册: {manifest.name}")
            return False

        if manifest.name in self._services:
            logger.warning(f"[MCP] 服务已存在，跳过: {manifest.name}")
            return False

        try:
            # 创建实例
            instance = self._create_instance(manifest)
            if not instance:
                return False

            # 包装实例
            wrapper = MCPServiceInstance(manifest.name, instance, manifest)
            self._services[manifest.name] = wrapper
            self._manifests[manifest.name] = manifest

            return True
        except Exception as e:
            logger.error(f"[MCP] 注册服务失败 {manifest.name}: {e}")
            return False

    def _create_instance(self, manifest: MCPServiceManifest) -> Optional[Any]:
        """根据manifest创建agent实例"""
        try:
            entry_point = manifest.entry_point
            module_name = entry_point.get("module")
            class_name = entry_point.get("class")

            if not module_name or not class_name:
                logger.error(f"[MCP] manifest缺少entryPoint: {manifest.display_name}")
                return None

            module = importlib.import_module(module_name)
            agent_class = getattr(module, class_name)
            instance = agent_class()
            return instance

        except Exception as e:
            logger.error(f"[MCP] 创建实例失败 {manifest.name}: {e}")
            return None

    async def call(
        self,
        service_name: str,
        tool_name: str = "",
        message: str = "",
        **kwargs
    ) -> MCPCallResult:
        """
        调用MCP服务工具

        Args:
            service_name: 服务名称
            tool_name: 工具名称
            message: 消息内容
            **kwargs: 其他参数

        Returns:
            MCPCallResult: 调用结果
        """
        import time
        start_time = time.time()

        # 检查服务
        service = self._services.get(service_name)
        if not service:
            return MCPCallResult(
                success=False,
                service_name=service_name,
                tool_name=tool_name,
                error=f"服务不存在: {service_name}"
            )

        # 构造调用参数
        tool_call = {
            "service_name": service_name,
            "tool_name": tool_name,
            "message": message,
            **kwargs
        }

        # 执行前置钩子
        for hook in self._pre_call_hooks:
            try:
                await hook(service_name, tool_name, tool_call)
            except Exception as e:
                logger.warning(f"[MCP] 前置钩子执行失败: {e}")

        # 执行调用
        try:
            result = await service.handle_handoff(tool_call)
            execution_time = time.time() - start_time

            call_result = MCPCallResult(
                success=True,
                service_name=service_name,
                tool_name=tool_name,
                result=result,
                execution_time=execution_time
            )

            # 执行后置钩子
            for hook in self._post_call_hooks:
                try:
                    await hook(service_name, tool_name, call_result)
                except Exception as e:
                    logger.warning(f"[MCP] 后置钩子执行失败: {e}")

            return call_result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[MCP] 调用服务失败 {service_name}: {e}")

            return MCPCallResult(
                success=False,
                service_name=service_name,
                tool_name=tool_name,
                error=str(e),
                execution_time=execution_time
            )

    async def call_multiple(
        self,
        calls: List[Dict[str, Any]]
    ) -> List[MCPCallResult]:
        """
        并行调用多个MCP服务

        Args:
            calls: 调用列表，每个元素包含 service_name, tool_name, message 等

        Returns:
            List[MCPCallResult]: 调用结果列表
        """
        tasks = [
            self.call(
                service_name=call.get("service_name"),
                tool_name=call.get("tool_name", ""),
                message=call.get("message", ""),
                **{k: v for k, v in call.items() if k not in ["service_name", "tool_name", "message"]}
            )
            for call in calls
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(MCPCallResult(
                    success=False,
                    service_name=calls[i].get("service_name", "unknown"),
                    tool_name=calls[i].get("tool_name", ""),
                    error=str(result)
                ))
            else:
                processed_results.append(result)

        return processed_results

    def get_services(self) -> List[str]:
        """获取所有注册的服务名称"""
        return list(self._services.keys())

    def get_service_info(self, service_name: str) -> Optional[Dict[str, Any]]:
        """获取服务详细信息"""
        service = self._services.get(service_name)
        if not service:
            return None

        return {
            "name": service.name,
            "display_name": service.manifest.display_name,
            "description": service.manifest.description,
            "agent_type": service.manifest.agent_type,
            "version": service.manifest.version,
            "tools": self._get_service_tools(service),
            "statistics": {
                "call_count": service.call_count,
                "error_count": service.error_count,
                "last_called": service.last_called
            }
        }

    def _get_service_tools(self, service: MCPServiceInstance) -> List[Dict[str, Any]]:
        """获取服务工具列表"""
        return service.manifest.capabilities.get("invocationCommands", [])

    def search_services(self, keyword: str) -> List[str]:
        """按关键词搜索服务"""
        keyword_lower = keyword.lower()
        matched = []

        for name, manifest in self._manifests.items():
            if (keyword_lower in manifest.display_name.lower() or
                keyword_lower in manifest.description.lower() or
                keyword_lower in name.lower()):
                matched.append(name)

        return matched

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_tools = sum(
            len(self._get_service_tools(service))
            for service in self._services.values()
        )

        return {
            "total_services": len(self._services),
            "total_tools": total_tools,
            "service_names": list(self._services.keys()),
            "total_calls": sum(s.call_count for s in self._services.values()),
            "total_errors": sum(s.error_count for s in self._services.values())
        }

    def format_services(self, names: Optional[List[str]] = None) -> str:
        """
        格式化服务信息为字符串（用于prompt注入）

        Args:
            names: 服务名称列表，None表示所有服务
        """
        lines = []
        services = names if names else self._manifests.keys()

        for name in services:
            manifest = self._manifests.get(name)
            if not manifest:
                continue

            lines.append(f"- 服务名(service_name): {name}")
            lines.append(f"  显示名: {manifest.display_name}")
            lines.append(f"  描述: {manifest.description}")
            lines.append(f"  版本: {manifest.version}")

            tools = self._get_service_tools(self._services[name])
            for tool in tools:
                cmd = tool.get("command", "")
                desc = tool.get("description", "").split("\n")[0]
                example = tool.get("example", "")
                lines.append(f"  工具: {cmd} - {desc}")
                if example:
                    lines.append(f"  示例: {example}")

            lines.append("")

        return "\n".join(lines)

    def add_pre_call_hook(self, hook: Callable):
        """添加前置调用钩子"""
        self._pre_call_hooks.append(hook)

    def add_post_call_hook(self, hook: Callable):
        """添加后置调用钩子"""
        self._post_call_hooks.append(hook)

    async def cleanup(self):
        """清理资源"""
        logger.info("[MCP] 正在清理资源...")
        self._services.clear()
        self._manifests.clear()
        self._pre_call_hooks.clear()
        self._post_call_hooks.clear()
        logger.info("[MCP] 清理完成")


# 全局单例
_MCP_MANAGER: Optional[MCPManager] = None


def get_mcp_manager(mcp_dir: Optional[str] = None, auto_register: bool = True) -> MCPManager:
    """获取MCP管理器单例"""
    global _MCP_MANAGER

    if _MCP_MANAGER is None:
        _MCP_MANAGER = MCPManager(mcp_dir=mcp_dir, auto_register=auto_register)

    return _MCP_MANAGER


def reset_mcp_manager():
    """重置MCP管理器（主要用于测试）"""
    global _MCP_MANAGER
    _MCP_MANAGER = None

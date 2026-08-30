"""
MCP记忆服务器
基于MCP协议（Model Context Protocol），提供记忆检索和管理工具
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
from pathlib import Path
from core.constants import Encoding

logger = logging.getLogger(__name__)


class ToolType(Enum):
    """工具类型"""
    SEARCH_MEMORY = "search_memory"
    ADD_MEMORY = "add_memory"
    UPDATE_MEMORY = "update_memory"
    DELETE_MEMORY = "delete_memory"
    LIST_MEMORIES = "list_memories"
    GET_STATISTICS = "get_statistics"


@dataclass
class MCPTool:
    """MCP工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: callable


class MCPMemoryServer:
    """MCP记忆服务器"""

    def __init__(
        self,
        server_name: str = "miya_memory_server",
        version: str = "1.0.0"
    ):
        self.server_name = server_name
        self.version = version

        # 工具注册
        self.tools: Dict[str, MCPTool] = {}

        # 记忆存储（简化版）
        self.memories: Dict[str, Dict[str, Any]] = {}

        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'start_time': time.time()
        }

        # 注册默认工具
        self._register_default_tools()

    def _register_default_tools(self):
        """注册默认工具"""
        # 搜索记忆
        self.tools[ToolType.SEARCH_MEMORY.value] = MCPTool(
            name=ToolType.SEARCH_MEMORY.value,
            description="Search memories by query or metadata",
            parameters={
                'type': 'object',
                'properties': {
                    'query': {
                        'type': 'string',
                        'description': 'Search query text'
                    },
                    'limit': {
                        'type': 'integer',
                        'description': 'Maximum number of results',
                        'default': 10
                    }
                }
            },
            handler=self._handle_search_memory
        )

        # 添加记忆
        self.tools[ToolType.ADD_MEMORY.value] = MCPTool(
            name=ToolType.ADD_MEMORY.value,
            description="Add a new memory entry",
            parameters={
                'type': 'object',
                'properties': {
                    'content': {
                        'type': 'string',
                        'description': 'Memory content'
                    },
                    'metadata': {
                        'type': 'object',
                        'description': 'Optional metadata (tags, importance, etc.)'
                    }
                }
            },
            handler=self._handle_add_memory
        )

        # 更新记忆
        self.tools[ToolType.UPDATE_MEMORY.value] = MCPTool(
            name=ToolType.UPDATE_MEMORY.value,
            description="Update an existing memory entry",
            parameters={
                'type': 'object',
                'properties': {
                    'memory_id': {
                        'type': 'string',
                        'description': 'Memory ID to update'
                    },
                    'content': {
                        'type': 'string',
                        'description': 'New content (optional)'
                    },
                    'metadata': {
                        'type': 'object',
                        'description': 'New metadata (optional)'
                    }
                }
            },
            handler=self._handle_update_memory
        )

        # 删除记忆
        self.tools[ToolType.DELETE_MEMORY.value] = MCPTool(
            name=ToolType.DELETE_MEMORY.value,
            description="Delete a memory entry",
            parameters={
                'type': 'object',
                'properties': {
                    'memory_id': {
                        'type': 'string',
                        'description': 'Memory ID to delete'
                    }
                }
            },
            handler=self._handle_delete_memory
        )

        # 列出记忆
        self.tools[ToolType.LIST_MEMORIES.value] = MCPTool(
            name=ToolType.LIST_MEMORIES.value,
            description="List all memories with optional filtering",
            parameters={
                'type': 'object',
                'properties': {
                    'limit': {
                        'type': 'integer',
                        'description': 'Maximum number of results',
                        'default': 50
                    },
                    'offset': {
                        'type': 'integer',
                        'description': 'Offset for pagination',
                        'default': 0
                    }
                }
            },
            handler=self._handle_list_memories
        )

        # 获取统计
        self.tools[ToolType.GET_STATISTICS.value] = MCPTool(
            name=ToolType.GET_STATISTICS.value,
            description="Get memory statistics",
            parameters={
                'type': 'object',
                'properties': {}
            },
            handler=self._handle_get_statistics
        )

        logger.info(f"[MCP] 注册工具: {len(self.tools)}个")

    async def handle_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理工具调用

        Args:
            tool_name: 工具名称
            arguments: 参数

        Returns:
            响应结果
        """
        self.stats['total_requests'] += 1

        if tool_name not in self.tools:
            self.stats['failed_operations'] += 1

            return {
                'success': False,
                'error': f"Tool not found: {tool_name}",
                'timestamp': time.time()
            }

        tool = self.tools[tool_name]

        try:
            # 调用处理函数
            result = await tool.handler(arguments)

            self.stats['successful_operations'] += 1

            return {
                'success': True,
                'result': result,
                'tool': tool_name,
                'timestamp': time.time()
            }

        except Exception as e:
            self.stats['failed_operations'] += 1
            logger.error(f"[MCP] 工具执行失败: {tool_name}, 错误: {e}")

            return {
                'success': False,
                'error': str(e),
                'tool': tool_name,
                'timestamp': time.time()
            }

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        获取工具列表

        Returns:
            工具定义列表
        """
        return [
            {
                'name': tool.name,
                'description': tool.description,
                'parameters': tool.parameters
            }
            for tool in self.tools.values()
        ]

    def get_server_info(self) -> Dict[str, Any]:
        """
        获取服务器信息

        Returns:
            服务器信息
        """
        return {
            'name': self.server_name,
            'version': self.version,
            'capabilities': list(self.tools.keys()),
            'statistics': self.stats
        }

    async def _handle_search_memory(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """处理搜索记忆"""
        query = arguments.get('query', '')
        limit = arguments.get('limit', 10)

        results = []

        # 简单文本匹配
        for memory_id, memory in self.memories.items():
            if query.lower() in memory.get('content', '').lower():
                results.append({
                    'memory_id': memory_id,
                    'content': memory.get('content', ''),
                    'metadata': memory.get('metadata', {}),
                    'timestamp': memory.get('timestamp', time.time())
                })

                if len(results) >= limit:
                    break

        return {
            'query': query,
            'total_found': len(results),
            'results': results
        }

    async def _handle_add_memory(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """处理添加记忆"""
        content = arguments.get('content', '')
        metadata = arguments.get('metadata', {})

        if not content:
            raise ValueError("Content is required")

        memory_id = self._generate_memory_id()

        memory = {
            'memory_id': memory_id,
            'content': content,
            'metadata': metadata,
            'timestamp': time.time(),
            'access_count': 0
        }

        self.memories[memory_id] = memory

        logger.info(f"[MCP] 添加记忆: {memory_id}")

        return {
            'memory_id': memory_id,
            'created': True
        }

    async def _handle_update_memory(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """处理更新记忆"""
        memory_id = arguments.get('memory_id', '')

        if memory_id not in self.memories:
            raise ValueError(f"Memory not found: {memory_id}")

        memory = self.memories[memory_id]

        # 更新内容
        if 'content' in arguments:
            memory['content'] = arguments['content']

        # 更新元数据
        if 'metadata' in arguments:
            memory['metadata'].update(arguments['metadata'])

        memory['updated_at'] = time.time()

        logger.info(f"[MCP] 更新记忆: {memory_id}")

        return {
            'memory_id': memory_id,
            'updated': True
        }

    async def _handle_delete_memory(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """处理删除记忆"""
        memory_id = arguments.get('memory_id', '')

        if memory_id not in self.memories:
            raise ValueError(f"Memory not found: {memory_id}")

        del self.memories[memory_id]

        logger.info(f"[MCP] 删除记忆: {memory_id}")

        return {
            'memory_id': memory_id,
            'deleted': True
        }

    async def _handle_list_memories(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """处理列出记忆"""
        limit = arguments.get('limit', 50)
        offset = arguments.get('offset', 0)

        all_memories = list(self.memories.values())

        # 按时间倒序
        all_memories.sort(key=lambda m: m.get('timestamp', 0), reverse=True)

        # 分页
        end = offset + limit
        results = all_memories[offset:end]

        return {
            'total': len(all_memories),
            'offset': offset,
            'limit': limit,
            'results': results
        }

    async def _handle_get_statistics(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """处理获取统计"""
        uptime = time.time() - self.stats['start_time']

        return {
            'total_requests': self.stats['total_requests'],
            'successful_operations': self.stats['successful_operations'],
            'failed_operations': self.stats['failed_operations'],
            'success_rate': (
                self.stats['successful_operations'] /
                max(self.stats['total_requests'], 1)
            ) if self.stats['total_requests'] > 0 else 1.0,
            'total_memories': len(self.memories),
            'server_uptime': uptime
        }

    def _generate_memory_id(self) -> str:
        """生成记忆ID"""
        import uuid
        return f"mcp_{uuid.uuid4().hex[:12]}"

    def save_state(self, filepath: Optional[str] = None):
        """保存状态到磁盘"""
        if filepath is None:
            filepath = "data/mcp_memory_state.json"

        data = {
            'server_name': self.server_name,
            'version': self.version,
            'memories': self.memories,
            'statistics': self.stats,
            'saved_at': time.time()
        }

        with open(filepath, 'w', encoding=Encoding.UTF8) as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"[MCP] 保存状态: {len(self.memories)}个记忆")

    def load_state(self, filepath: Optional[str] = None) -> bool:
        """从磁盘加载状态"""
        if filepath is None:
            filepath = "data/mcp_memory_state.json"

        try:
            path = Path(filepath)
            if not path.exists():
                return False

            with open(filepath, 'r', encoding=Encoding.UTF8) as f:
                data = json.load(f)

            self.server_name = data.get('server_name', self.server_name)
            self.version = data.get('version', self.version)
            self.memories = data.get('memories', {})
            self.stats = data.get('statistics', {})

            logger.info(f"[MCP] 加载状态: {len(self.memories)}个记忆")
            return True

        except Exception as e:
            logger.error(f"[MCP] 加载状态失败: {e}")
            return False

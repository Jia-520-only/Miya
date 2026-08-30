# 弥娅 MCP 服务架构文档

弥娅系统中，**DSH（DeepSeek Harness）** 与 **Python 守护进程** 之间通过 MCP（Model Context Protocol）双向通信。本文档涵盖 MCP 协议规范、已有服务和模块的职责说明、消息格式示例及新模块开发指南。

---

## 1. 整体架构

```
.mcp.json (stdio MCP 服务端)           agent-manifest.json (MCPManager 自动发现)
─────────                              ────────────

┌─ miya-soul ──────────────────┐       ┌─ MCPManager ───────────────────────┐
│  mcp.server.Server           │       │  core/mcp_manager.py                │
│  @server.list_tools()        │       │  scans mcpserver/**/agent-manifest  │
│  @server.call_tool()         │◄──────│  importlib.import_module()          │
│  stdio JSON-RPC              │  DSH  │  instance.handle_handoff({...})     │
└──────────────────────────────┘       └─────────────────────────────────────┘
                                              │
                                       │      ↓                              │
                                       │  art_service  dsh  code_executor   │
                                       │  database  filesystem  game_play   │
                                       │  memory  naga_community  dsh        │
                                       │  screen_vision  web_search         │
┌─ miya-mineradio ─────────────┐       │  miya_mineradio                  │
│  mcp.server.Server           │       └────────────────────────────────────┘
│  → MiyaMineradioService      │
│    .get_tool_definitions()   │        所有通过 stdio JSON-RPC 与 DSH 通信
│    .handle_tool_call()       │
└──────────────────────────────┘
```

弥娅中存在 **两套 MCP 集成范式**：

| 范式 | 配置方式 | 服务数 | 使用场景 |
|------|----------|--------|----------|
| **原生 MCP SDK** | `.mcp.json` → `stdio` | 2 | DSH 终端直接调用的核心服务 |
| **MCPManager 自动发现** | `mcpserver/*/agent-manifest.json` | 13 | 通过 daemon 进程统一管理、ToolNet 注册 |


---

## 2. MCP 协议规范

弥娅使用标准的 [MCP (Model Context Protocol)](https://spec.modelcontextprotocol.io/) JSON-RPC 2.0 over stdio。

### 2.1 传输层

- **传输方式**：标准输入/输出（stdin/stdout）JSON-RPC 2.0
- **行协议**：每行一个完整的 JSON-RPC 消息，以 `\n` 分隔
- **日志通道**：`stderr` 用于服务端日志输出（不影响协议通信）

### 2.2 初始化握手

客户端发起 `initialize` 请求，服务端返回能力集：

```json
// 请求 (客户端 → 服务端)
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": { "name": "deepseek-harness", "version": "1.0.0" }
  }
}

// 响应 (服务端 → 客户端)
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": { "tools": {} },
    "serverInfo": { "name": "miya-soul", "version": "1.0.0" }
  }
}
```

### 2.3 工具发现

客户端调用 `tools/list` 获取服务端提供的工具：

```json
// 请求
{ "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {} }

// 响应
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "miya_get_emotion",
        "description": "获取弥娅当前情感状态和表情符号",
        "inputSchema": {
          "type": "object",
          "properties": {},
          "required": []
        }
      }
    ]
  }
}
```

### 2.4 工具调用

客户端调用 `tools/call` 执行具体工具：

```json
// 请求
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "miya_get_emotion",
    "arguments": {}
  }
}

// 响应
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"state\": {\"current\": \"joy\", \"intensity\": 0.7, ...}, \"expression\": \"😊\"}"
      }
    ]
  }
}
```

### 2.5 常用调用示例

#### miya-soul: 查询情感状态
```json
// 请求
{ "jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": { "name": "miya_get_emotion", "arguments": {} } }

// 响应 content[0].text
{
  "state": { "current": "joy", "intensity": 0.75, "emotions": { "joy": 0.75, "trust": 0.3, ... } },
  "expression": "😊"
}
```

#### miya-soul: 查询系统完整状态
```json
// 请求
{ "jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": { "name": "miya_get_system_status", "arguments": {} } }
```

#### miya-mineradio: 搜索歌曲
```json
{
  "jsonrpc": "2.0", "id": 4, "method": "tools/call",
  "params": {
    "name": "mineradio_search",
    "arguments": { "query": "晴天", "source": "netease" }
  }
}
```

---

## 3. 各服务模块职责详解

### 3.1 原生 MCP SDK 服务（`.mcp.json` 注册）

#### miya-soul (mcpserver/miya/)

**入口**：`python mcpserver/miya/server.py`  
**核心类**：`MiyaPersonality`, `MiayaMemory`, `MiayaEmotion`, `MiayaModelSelector`  
**职责**：DSH 终端感知弥娅"灵魂状态"的唯一窗口。暴露 17 个工具。

| 工具 | 说明 |
|------|------|
| `miya_get_personality` | 获取当前人格、可用人格列表 |
| `miya_switch_personality` | 运行时热切换人格 |
| `miya_get_memory` | 获取近期记忆与会话摘要 |
| `miya_save_memory` | 保存键值对记忆 |
| `miya_recall` | 按关键词回忆 |
| `miya_get_emotion` | 当前情感类型 + 强度 + 表情符号 |
| `miya_set_emotion` | 手动设置情感（7 种基本情绪） |
| `miya_get_status` | 人格 + 记忆 + 情感三者整合 |
| `miya_get_system_status` | 全量状态：人格 + 情感 + 记忆 + 脊柱 + 模型池 |
| `miya_list_models` | 列出模型池中所有可用模型 |
| `miya_select_model` | 按任务类型选择最佳模型 |
| `miya_classify_task` | 分类用户输入的任务类型 |
| `miya_get_task_types` | 获取所有支持的任务类型 |
| `miya_get_spine_status` | v8.0 脊柱神经：存活状态、生命阶段、器官在线等 |
| `miya_collaborate` | 经协作引擎处理消息（自动单模型/链式/并行/角色分工） |

**桥接能力**：
- `spine` — 桥接 v8.0 弥娅脊柱神经
- `collaboration_engine` — 包装 `ModelCollaborationEngine`
- `model_selector` — 包装 `core.model_pool_compat`

#### miya-mineradio (mcpserver/miya_mineradio/)

**入口**：`python mcpserver/miya_mineradio/server.py`  
**核心类**：`MiyaMineradioService`  
**职责**：通过 WebSocket 遥控 Mineradio 桌面音乐播放器（Netease/QQ 音源）。

| 分类 | 工具 |
|------|------|
| 播放控制 | `mineradio_play`, `mineradio_pause`, `mineradio_toggle_play`, `mineradio_next`, `mineradio_prev`, `mineradio_seek` |
| 状态查询 | `mineradio_get_status`, `mineradio_health`, `mineradio_get_queue` |
| 搜索/播放 | `mineradio_search`, `mineradio_play_song`, `mineradio_add_to_queue`, `mineradio_play_list` |
| 队列管理 | `mineradio_clear_queue`, `mineradio_shuffle_queue`, `mineradio_remove_from_queue` |
| 播放列表 | `mineradio_get_playlists`, `mineradio_get_playlist_tracks`, `mineradio_create_playlist` |
| 歌词/模式 | `mineradio_get_lyrics`, `mineradio_set_mode` |
| 音量 | `mineradio_set_volume`, `mineradio_toggle_mute` |
| 收藏 | `mineradio_like_song`, `mineradio_unlike_song` |
| 启动 | `mineradio_launch` |

### 3.2 MCPManager 自动发现模块（`agent-manifest.json` 注册）

所有模块遵循统一接口：通过 `handle_handoff(tool_call: dict) -> str` 处理工具调用，返回 JSON 字符串。

#### art_service — AI 绘画服务

调用 `webnet.artnet.ArtProviderManager` 生成 AI 图像。

| 工具 | 说明 |
|------|------|
| `generate_image` | 生成 AI 图像（ComfyUI/DALL·E/NovelAI/CogView/Tongyi） |
| `list_providers` | 列出可用画图引擎及可用状态 |
| `get_gallery` | 获取生成作品画廊 |

#### dsh — DeepSeek Harness 服务

子进程执行 `deepseek-harness/apps/cli/lib/bin.js --profile headless`，将自然语言任务委派给 DSH 的内置工具（文件读写/搜索、bash/pwsh、子代理、技能、工作流）。

| 工具 | 说明 |
|------|------|
| `execute` | 执行自然语言任务（文件操作、代码编写、系统命令） |
| `get_status` | 获取 DSH 可用性、版本、路径 |

#### code_executor — 代码执行服务

Python/JS/Shell 代码通过临时文件和子进程执行。

| 工具 | 说明 |
|------|------|
| `execute` | 执行 Python/JavaScript/Shell 代码（支持超时） |

#### database — 数据库服务

SQLite 操作，自动创建 `.miya/database.db`（含 `miya_data` 表）。

| 工具 | 说明 |
|------|------|
| `query` | SELECT 查询（最多 100 行） |
| `execute` | INSERT/UPDATE/DELETE |
| `schema` | 获取表结构 |

#### filesystem — 文件系统服务

标准文件 CRUD 操作。

| 工具 | 说明 |
|------|------|
| `read_file` | 读取文件（offset/limit） |
| `write_file` | 写入文件（自动创建父目录） |
| `delete_file` | 删除文件或目录（可选递归） |
| `list_files` | 按 glob 模式列出文件 |
| `search_files` | 正则搜索文件内容 |

#### game_play — 游戏伴侣服务

委托 `core.game_play.engine.GamePlayEngine`。

| 工具 | 说明 |
|------|------|
| `start_game` | 启动游戏伴侣模式（语音/视觉/控制选项） |
| `stop_game` | 停止游戏伴侣 |
| `get_status` | 获取引擎状态 |
| `list_games` | 列出支持的游戏配置 |

#### memory — 记忆服务

基于 JSON 文件的轻量记忆存储（`.miya/memory/`）。

| 工具 | 说明 |
|------|------|
| `store` | 存储记忆（key/value/tags/category） |
| `recall` | 按 query/key/id 检索 |
| `delete` | 按 ID 删除 |
| `list` | 列出记忆（可选按 category 过滤） |

#### naga_community — 社区论坛服务

NagaBusiness REST API 客户端（含双 token 认证、自动刷新、会话持久化）。

| 分类 | 工具 |
|------|------|
| 认证 | `get_captcha`, `login`, `register`, `send_verification`, `logout`, `get_me` |
| 帖子 | `get_posts`, `get_post_detail`, `create_post`, `delete_post`, `like_post` |
| 评论 | `comment_post`, `like_comment`, `delete_comment` |
| 私信 | `get_messages`, `send_message` |
| 好友 | `get_friend_requests`, `accept_friend`, `decline_friend`, `get_connections` |
| 通知 | `get_notifications`, `read_notification` |
| 资料 | `get_profile` |

#### dsh — DeepSeek Harness 执行服务

通过 DeepSeek Harness 执行自然语言电脑任务，统一覆盖文件操作、命令执行、浏览器自动化和复杂多步骤工作流。

| 工具 | 说明 |
|------|------|
| `execute` | 执行自然语言任务（可指定工作目录和超时） |
| `get_status` | 查询 DSH CLI、Node.js 和配置状态 |

#### screen_vision — 屏幕视觉服务

跨平台截图（mss/screencapture/grim）+ 视觉 LLM 分析（30-40x PIL 压缩优化）。

| 工具 | 说明 |
|------|------|
| `look_screen` | 截图 + 视觉 AI 分析 |
| `screenshot` | 仅截图（返回 data URL，不做 AI 分析） |

#### web_search — 网页搜索服务

通过 `curl` 子进程搜索 DuckDuckGo/Google/Bing。

| 工具 | 说明 |
|------|------|
| `search` | 网页搜索 |
| `fetch` | 抓取网页内容 |

#### agent_mcp — 按代理 MCP 注册中心（库模块）

**类型**：纯库模块，无 `agent-manifest.json` 和 `server.py`。  
**核心类**：`AgentMCPRegistry` — 可按 agent 名称注册外部 MCP JSON 配置文件，支持懒加载连接、工具名映射（`.` → `-_-`）、工具调用和缓存。

---

## 4. 开发新 MCP 模块

### 4.1 选择集成范式

| 场景 | 推荐模式 | 原因 |
|------|----------|------|
| 需 DSH 终端直接调用（如状态查询） | 原生 MCP SDK（`.mcp.json`） | 低延迟、无中间层 |
| 作为 daemon 可用能力池的一部分 | MCPManager 自动发现（`agent-manifest.json`） | 统一管理、ToolNet 注册 |
| 两者都需要 | 双端注册 | 灵活最大化 |

### 4.2 创建 MCPManager 模块（推荐入门）

这是最常用的模式，只需 2 个文件：

**步骤 1：创建 `mcpserver/<模块名>/service.py`**

```python
#!/usr/bin/env python3
"""
MCP <模块名> Service — <功能描述>
"""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class MyService:
    """MCP 服务类"""

    def __init__(self):
        self.name = "my_service"
        self.description = "服务描述"
        self.version = "1.0.0"

    async def handle_handoff(self, tool_call: Dict[str, Any]) -> str:
        """
        统一入口：根据 tool_name 分发到具体实现。

        tool_call 结构:
        {
            "service_name": "my_service",     # 服务名
            "tool_name": "do_something",      # 工具名
            "message": "",                     # 附加消息
            ...其他工具参数...
        }

        返回: JSON 字符串
        """
        tool_name = tool_call.get("tool_name", "")

        if tool_name == "do_something":
            return await self._do_something(tool_call)
        elif tool_name == "get_info":
            return await self._get_info(tool_call)
        else:
            return json.dumps(
                {"error": f"未知工具: {tool_name}"},
                ensure_ascii=False,
            )

    async def _do_something(self, tool_call: Dict[str, Any]) -> str:
        param = tool_call.get("param", "default_value")
        result = f"处理完成: {param}"
        return json.dumps(
            {"success": True, "result": result},
            ensure_ascii=False,
        )

    async def _get_info(self, tool_call: Dict[str, Any]) -> str:
        return json.dumps(
            {
                "name": self.name,
                "version": self.version,
                "status": "ok",
            },
            ensure_ascii=False,
        )


# 模块级单例
service = MyService()


if __name__ == "__main__":
    import asyncio

    async def test():
        result = await service.handle_handoff(
            {
                "tool_name": "do_something",
                "param": "hello",
            }
        )
        print(result)

    asyncio.run(test())
```

**步骤 2：创建 `mcpserver/<模块名>/agent-manifest.json`**

```json
{
  "name": "my_service",
  "displayName": "我的服务",
  "description": "自定义 MCP 服务",
  "agentType": "mcp",
  "entryPoint": {
    "module": "mcpserver.my_service.service",
    "class": "MyService"
  },
  "capabilities": {
    "tools": [
      {
        "name": "do_something",
        "description": "执行某操作",
        "parameters": {
          "param": "string"
        }
      },
      {
        "name": "get_info",
        "description": "获取服务信息",
        "parameters": {}
      }
    ]
  },
  "version": "1.0.0",
  "enabled": true
}
```

**关键约定**：
- `entryPoint.module` 使用 Python 点号路径（相对于项目根目录）
- `entryPoint.class` 即类名
- 服务类必须实现 `async handle_handoff(tool_call: dict) -> str`
- 返回值为 JSON 字符串（`json.dumps(..., ensure_ascii=False)`）
- `capabilities.tools` 描述了暴露给 AI 的工具签名
- 设置 `"enabled": false` 可禁用模块（无需删除文件）

### 4.3 创建原生 MCP SDK 服务

如果需要作为独立 stdio 服务：

**步骤 1：创建 `mcpserver/<模块名>/server.py`**

```python
"""
MCP Server 入口
"""

import asyncio
import json
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server

from .service import MyService

logger = logging.getLogger(__name__)


def create_server() -> Server:
    server = Server("my-service")
    svc = MyService()

    @server.list_tools()
    async def list_tools():
        return [
            {
                "name": "my_tool",
                "description": "工具描述",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "param": {"type": "string", "description": "参数说明"},
                    },
                    "required": ["param"],
                },
            },
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> str:
        # 委托给 handle_handoff 保持双端兼容
        result = await svc.handle_handoff({"tool_name": name, "arguments": arguments})
        return result

    return server


async def main():
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```

**步骤 2：在 `.mcp.json` 中注册**

```json
{
  "mcpServers": {
    "my-service": {
      "command": "python",
      "args": ["mcpserver/my_service/server.py"],
      "env": {},
      "disabled": false,
      "autoApprove": ["my_tool"]
    }
  }
}
```

### 4.4 常见陷阱

1. **路径**：`MCPManager` 的 `entryPoint.module` 从项目根目录导入，`mcp.server.Server` 的 `args` 也是从根目录执行。确保 Python path 正确。
2. **初始化时机**：`MCPManager` 使用懒初始化（检测 `asyncio.get_running_loop()`），确保不在同步上下文中调用 `asyncio.create_task`。
3. **IO 不阻塞**：`handle_handoff` 是 `async` 方法，内部不应使用 `time.sleep()` 等同步阻塞调用。
4. **日志**：服务日志输出到 `stderr`（原生 MCP SDK 的 stdin/stdout 不能混入日志）。
5. **错误处理**：捕获异常并返回 JSON 错误对象，避免未捕获异常导致整个 MCP 框架崩溃。
6. **与 miya-soul 交互**：如需访问弥娅的人格/记忆/情感状态，通过 `mcpserver/miya/server.py` 中的 MCP 工具调用，不要直接在自定义模块中导入 `core.*` 模块（避免循环依赖）。
7. **参数提取**：`handle_handoff` 接收的 `tool_call` 字典中，工具参数与 `service_name`, `tool_name`, `message` 同级。MCPManager 在 `call()` 方法中会自动展开 `**kwargs`。

---

## 5. MCPManager API 参考

位于 `core/mcp_manager.py:72`。

### 获取单例
```python
from core.mcp_manager import get_mcp_manager

manager = get_mcp_manager()
```

### 调用工具
```python
# 单个调用
result: MCPCallResult = await manager.call(
    service_name="memory",
    tool_name="store",
    key="username",
    value="张三",
    category="profile",
)

# 并行调用
results: list[MCPCallResult] = await manager.call_multiple(
    [
        {"service_name": "filesystem", "tool_name": "list_files", "pattern": "*.py"},
        {"service_name": "memory", "tool_name": "recall", "query": "配置"},
    ]
)
```

### 查询服务
```python
services = manager.get_services()  # ['art_service', 'dsh', ...]
info = manager.get_service_info("memory")  # 详细信息 + 统计
matched = manager.search_services("记忆")  # 搜索匹配
stats = manager.get_statistics()  # 全局统计
```

### 格式化（Prompt 注入）
```python
prompt_text = manager.format_services()  # 所有服务
prompt_text = manager.format_services(["dsh", "web_search"])  # 指定服务
```

### 钩子
```python
async def my_logger(service_name, tool_name, call_result):
    print(f"[HOOK] {service_name}.{tool_name}")


manager.add_post_call_hook(my_logger)
```

### MCPCallResult
```python
@dataclass
class MCPCallResult:
    success: bool  # 是否成功
    service_name: str  # 服务名
    tool_name: str  # 工具名
    result: Any  # 原始结果（JSON 字符串）
    error: Optional[str]  # 错误信息
    execution_time: float  # 执行耗时（秒）
```

---

## 6. `.mcp.json` 配置参考

```json
{
  "mcpServers": {
    "<服务标识>": {
      "command": "python",                      // 启动命令
      "args": ["mcpserver/xxx/server.py"],      // 启动参数（相对于项目根目录）
      "env": {},                                 // 环境变量（可覆盖 .env）
      "disabled": false,                         // true 则禁用该服务
      "autoApprove": ["tool_name_1", "tool_name_2"]  // 自动批准的工具列表（无需用户确认）
    }
  }
}
```

> **安全建议**：仅对只读/低风险工具设置 `autoApprove`。高危操作（如执行代码、沙箱命令）应保留用户确认流程。

---

## 7. 目录结构总览

```
mcpserver/
├── miya/                     # ★ miya-soul 原生 MCP 服务（17 工具）
│   └── server.py
├── miya_mineradio/           # ★ 音乐遥控（27 工具，双端注册）
│   ├── agent-manifest.json
│   ├── server.py
│   └── service.py
├── agent_mcp/                # 按代理 MCP 注册中心（库模块）
│   └── __init__.py
├── art_service/              # AI 绘画（3 工具）
│   ├── agent-manifest.json
│   └── service.py
├── dsh/                      # DSH 子进程执行（2 工具）
│   ├── agent-manifest.json
│   └── service.py
├── code_executor/            # 代码执行（1 工具）
│   ├── agent-manifest.json
│   └── service.py
├── database/                 # SQLite 数据库（3 工具）
│   ├── agent-manifest.json
│   └── service.py
├── filesystem/               # 文件系统（5 工具）
│   ├── agent-manifest.json
│   └── service.py
├── game_play/                # 游戏伴侣（4 工具）
│   ├── agent-manifest.json
│   └── service.py
├── memory/                   # 记忆存储（4 工具）
│   ├── agent-manifest.json
│   └── service.py
├── naga_community/           # 社区论坛（23+ 工具）
│   ├── agent-manifest.json
│   ├── service.py
│   ├── auth.py
│   └── forum.py
├── dsh/                      # DeepSeek Harness 执行（2 工具）
│   ├── agent-manifest.json
│   ├── service.py
│   └── config_bridge.py
├── screen_vision/            # 屏幕视觉分析（2 工具）
│   ├── agent-manifest.json
│   ├── service.py
│   └── screenshot_provider.py
└── web_search/               # 网页搜索（2 工具）
    ├── agent-manifest.json
    └── service.py
```

> `miya_core/` 为空目录，预留未来开发。

---

## 8. 索引

- MCPManager 实现：`core/mcp_manager.py:72`
- AgentMCPRegistry 实现：`mcpserver/agent_mcp/__init__.py`
- `.mcp.json` 根配置：`.mcp.json`
- 系统架构总览：`docs/MIYA_ARCHITECTURE.md`
- 配置文件说明：`config/text_config.json` / `config/qq_config.yaml`

# Undefined 工具系统集成指南

## 概述

弥娅框架现已集成 **Undefined** 的工具系统，为 QQ 机器人提供强大的功能扩展能力。

### 融合策略

采用**渐进式融合**策略：
- ✅ **核心工具层**：简化版工具适配器（`core/tool_adapter.py`）
- ✅ **Undefined 桥接器**：可按需加载 Undefined 高级工具
- ✅ **AI 工具调用**：支持 OpenAI Function Calling

---

## 架构设计

```
弥娅架构
├── core/
│   ├── ai_client.py          # AI 客户端（支持工具调用）
│   ├── tool_adapter.py       # 工具适配器（简化版）
│   └── prompt_manager.py     # 提示词管理器
│
├── Undefined/ (可选)
│   └── src/Undefined/
│       ├── skills/           # 高级工具系统
│       └── ai/              # AI 核心能力
│
└── run/qq_main.py           # QQ 机器人（集成点）
```

---

## 已集成功能

### 1. 默认工具

弥娅内置以下工具：

| 工具名 | 功能 | 状态 |
|--------|------|------|
| `web_search` | 网络搜索 | 🟡 开发中 |
| `get_current_time` | 获取当前时间 | ✅ 可用 |
| `send_message` | 发送消息 | ✅ 可用 |
| `bilibili_video` | B站视频下载 | 🟡 开发中 |

### 2. 工具调用机制

- 支持 OpenAI Function Calling
- 自动多轮迭代（最多 10 次）
- 异步工具执行
- 错误处理和降级

### 3. Undefined 桥接

- 可选加载 Undefined 工具
- 自动检测 Undefined 模块
- 热重载支持

---

## 使用方法

### 基础使用（无需 Undefined）

弥娅开箱即用，内置基础工具：

```python
# QQ 机器人自动初始化工具系统
bot = MiyaQQBot()

# 用户发送消息
# 弥娅自动决定是否调用工具
```

### 高级使用（加载 Undefined 工具）

如果 `Undefined/` 文件夹存在，弥娅会自动加载高级工具：

```bash
# 确保 Undefined 文件夹存在
Miya/
├── Undefined/
│   └── src/Undefined/
└── run/qq_main.py
```

启动时会自动检测并加载：

```
[INFO] Undefined模块检测成功
[INFO] 工具系统初始化成功，已加载 4 个工具
[INFO] 工具系统升级完成，共 20 个工具
```

---

## 配置说明

### AI 模型配置

需要支持工具调用的模型（推荐）：

```env
# config/.env

# OpenAI（推荐）
AI_PROVIDER=openai
AI_OPENAI_API_KEY=sk-xxxx
AI_OPENAI_MODEL=gpt-4o-mini

# DeepSeek（支持工具调用）
AI_PROVIDER=deepseek
AI_DEEPSEEK_API_KEY=sk-xxxx
AI_DEEPSEEK_MODEL=deepseek-chat
```

### 工具系统配置（可选）

```env
# 开启 Undefined 工具（默认自动检测）
ENABLE_UNDEFINED_TOOLS=true
```

---

## 开发自定义工具

### 方法 1：弥娅原生工具

在 `core/tool_adapter.py` 的 `_register_default_tools()` 中添加：

```python
self.register_tool(
    name="my_custom_tool",
    description="自定义工具描述",
    parameters={
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "description": "输入参数"
            }
        },
        "required": ["input"]
    },
    handler=self._handle_my_tool
)

async def _handle_my_tool(self, args: Dict, context: Dict) -> str:
    """自定义工具处理"""
    input_value = args.get("input", "")
    return f"处理结果: {input_value}"
```

### 方法 2：Undefined 风格工具

在 `Undefined/src/Undefined/skills/tools/` 下创建工具目录：

```
Undefined/src/Undefined/skills/tools/my_tool/
├── config.json      # 工具定义（OpenAI Function 格式）
└── handler.py      # 执行逻辑
```

弥娅会自动发现并加载。

---

## 工具调用示例

### 示例 1：获取时间

```
用户: 现在几点了？
弥娅: [调用工具 get_current_time]
     当前时间: 2026-02-28 14:30:00
```

### 示例 2：网络搜索（需实现）

```
用户: 搜索 Python 最新版本
弥娅: [调用工具 web_search]
     Python 3.14 是最新版本...
```

### 示例 3：多工具协作

```
用户: 帮我查天气并记录
弥娅: [调用工具 web_search]
     [调用工具 send_message]
     已发送天气信息...
```

---

## 故障排查

### 问题 1：工具未加载

```
[WARNING] Undefined模块检测失败
```

**解决方案**：
- 确保 `Undefined/` 文件夹在项目根目录
- 检查 `Undefined/src/` 结构是否完整

### 问题 2：工具调用失败

```
[ERROR] AI生成失败: 'PromptManager' object has no attribute 'system_prompt'
```

**已修复**：已删除重复的 `get_system_prompt()` 方法。

### 问题 3：模型不支持工具调用

某些旧模型不支持 Function Calling，会自动降级为普通对话。

**解决方案**：
- 使用支持工具调用的模型（GPT-4o-mini, DeepSeek-V3 等）

---

## 进阶功能

### 1. Agent 系统

Undefined 提供 6 个智能体：

- `info_agent` - 信息查询助手
- `web_agent` - 网络搜索助手
- `file_analysis_agent` - 文件分析助手
- `naga_code_analysis_agent` - 代码分析助手
- `entertainment_agent` - 娱乐助手
- `code_delivery_agent` - 代码交付助手

未来可选择性集成。

### 2. MCP (Model Context Protocol)

支持通过 MCP 协议扩展工具能力：

```json
// config/mcp.json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

### 3. 认知记忆系统

Undefined 的认知记忆系统可集成到弥娅的记忆引擎中：

- 事件检索
- 侧写管理
- 历史总结

---

## 性能优化

### 工具缓存

```python
# tool_adapter.py
class ToolAdapter:
    def __init__(self):
        self._tool_cache = {}  # 缓存工具结果
```

### 异步执行

所有工具处理函数都是 `async`，确保非阻塞。

---

## 安全建议

1. **权限控制**：工具执行前检查用户权限
2. **输入验证**：验证工具参数，防止注入攻击
3. **超时控制**：设置工具执行超时（默认 480 秒）
4. **速率限制**：避免工具被滥用

---

## 未来规划

- [ ] 完善 Undefined 高级工具集成
- [ ] 添加 Agent 系统
- [ ] 集成 MCP 协议
- [ ] 工具执行统计
- [ ] 工具热重载 UI

---

## 相关文档

- [QQ 机器人配置指南](./QQ_BOT_SETUP.md)
- [AI API 配置指南](./AI_API_SETUP.md)
- [弥娅架构文档](./ARCHITECTURE_OVERVIEW.md)
- [Undefined 原始文档](../Undefined/ARCHITECTURE.md)

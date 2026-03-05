# Undefined完整整合计划与进度

生成时间: 2026-02-28
整合目标: 完全吸收Undefined的所有能力到弥娅框架

---

## 📋 执行摘要

**Undefined** 包含大量高质量代码和先进架构，需要系统性地整合到弥娅框架中。本计划详细列出了所有需要整合的能力、优先级和进度。

---

## 🎯 一、整合能力清单

### 1.1 核心架构层（P0 - 最高优先级）

| 能力 | 原始位置 | 弥娅整合位置 | 状态 |
|-----|---------|-------------|------|
| **Skills架构** | `skills/registry.py` | `core/skills_registry.py` | ✅ 已完成 |
| **认知记忆系统** | `cognitive/` | `memory/cognitive_memory_system.py` | ✅ 已完成 |
| **Runtime API** | `api/app.py` | `core/runtime_api.py` | 📋 待整合 |
| **配置热更新** | `config/hot_reload.py` | `core/config_hot_reload.py` | 📋 待整合 |

### 1.2 Agent能力层（P1 - 高优先级）

| 能力 | 原始位置 | 弥娅整合位置 | 状态 |
|-----|---------|-------------|------|
| **AI客户端** | `ai/client.py` | `core/ai_client.py` | 📋 待整合 |
| **工具管理器** | `ai/tooling.py` | `core/tool_manager.py` | 📋 待整合 |
| **提示词构建器** | `ai/prompts.py` | `core/prompt_builder.py` | 📋 待整合 |
| **多模态分析器** | `ai/multimodal.py` | `core/multimodal_analyzer.py` | 📋 待整合 |

### 1.3 记忆存储层（P1 - 高优先级）

| 能力 | 原始位置 | 弥娅整合位置 | 状态 |
|-----|---------|-------------|------|
| **向量存储** | `cognitive/vector_store.py` | `memory/vector_store.py` | 📋 待整合 |
| **用户侧写存储** | `cognitive/profile_storage.py` | `memory/profile_storage.py` | 📋 待整合 |
| **FAQ存储** | `faq.py` | `memory/faq_storage.py` | 📋 待整合 |
| **Token统计** | `token_usage_storage.py` | `memory/token_storage.py` | 📋 待整合 |

### 1.4 消息处理层（P2 - 中优先级）

| 能力 | 原始位置 | 弥娅整合位置 | 状态 |
|-----|---------|-------------|------|
| **消息处理器** | `handlers.py` | `core/message_handler.py` | 📋 待整合 |
| **命令分发器** | `services/command.py` | `core/command_dispatcher.py` | 📋 待整合 |
| **Bilibili模块** | `bilibili/` | `core/bilibili/` | 📋 待整合 |
| **安全服务** | `services/security.py` | `core/security_service.py` | 📋 待整合 |

### 1.5 队列系统（P2 - 中优先级）

| 能力 | 原始位置 | 弥娅整合位置 | 状态 |
|-----|---------|-------------|------|
| **队列管理器** | `services/queue_manager.py` | `core/queue_manager.py` | 📋 待整合 |
| **AI协调器** | `services/ai_coordinator.py` | `core/ai_coordinator.py` | 📋 待整合 |

### 1.6 6个核心Agent（P2 - 中优先级）

| Agent | 原始位置 | 弥娅整合位置 | 状态 |
|-------|---------|-------------|------|
| **info_agent** | `skills/agents/info_agent/` | `core/skills/agents/info_agent/` | 📋 待整合 |
| **web_agent** | `skills/agents/web_agent/` | `core/skills/agents/web_agent/` | 📋 待整合 |
| **file_analysis_agent** | `skills/agents/file_analysis_agent/` | `core/skills/agents/file_analysis_agent/` | 📋 待整合 |
| **naga_code_analysis_agent** | `skills/agents/naga_code_analysis_agent/` | `core/skills/agents/naga_code_analysis_agent/` | 📋 待整合 |
| **entertainment_agent** | `skills/agents/entertainment_agent/` | `core/skills/agents/entertainment_agent/` | 📋 待整合 |
| **code_delivery_agent** | `skills/agents/code_delivery_agent/` | `core/skills/agents/code_delivery_agent/` | 📋 待整合 |

### 1.7 工具集（P3 - 低优先级）

| 工具集 | 原始位置 | 弥娅整合位置 | 状态 |
|-------|---------|-------------|------|
| **基础工具** | `skills/tools/` | `core/skills/tools/` | 📋 待整合 |
| **group工具集** | `skills/toolsets/group/` | `core/skills/toolsets/group/` | 📋 待整合 |
| **messages工具集** | `skills/toolsets/messages/` | `core/skills/toolsets/messages/` | 📋 待整合 |
| **memory工具集** | `skills/toolsets/memory/` | `core/skills/toolsets/memory/` | 📋 待整合 |
| **其他工具集** | `skills/toolsets/*` | `core/skills/toolsets/*` | 📋 待整合 |

### 1.8 命令系统（P3 - 低优先级）

| 命令 | 原始位置 | 弥娅整合位置 | 状态 |
|-----|---------|-------------|------|
| **help命令** | `skills/commands/help/` | `core/skills/commands/help/` | 📋 待整合 |
| **stats命令** | `skills/commands/stats/` | `core/skills/commands/stats/` | 📋 待整合 |
| **addadmin命令** | `skills/commands/addadmin/` | `core/skills/commands/addadmin/` | 📋 待整合 |
| **其他命令** | `skills/commands/*` | `core/skills/commands/*` | 📋 待整合 |

---

## 📊 二、整合进度统计

### 2.1 整合进度总览

| 类别 | 总数 | 已完成 | 进行中 | 待开始 | 完成率 |
|-----|------|-------|-------|-------|--------|
| **核心架构层** | 4 | 2 | 0 | 2 | 50% |
| **Agent能力层** | 4 | 0 | 0 | 4 | 0% |
| **记忆存储层** | 4 | 0 | 0 | 4 | 0% |
| **消息处理层** | 4 | 0 | 0 | 4 | 0% |
| **队列系统** | 2 | 0 | 0 | 2 | 0% |
| **核心Agent** | 6 | 0 | 0 | 6 | 0% |
| **工具集** | ~30 | 0 | 0 | ~30 | 0% |
| **命令系统** | ~10 | 0 | 0 | ~10 | 0% |
| **总计** | **~64** | **2** | **0** | **~62** | **3%** |

### 2.2 按优先级统计

| 优先级 | 数量 | 已完成 | 进行中 | 待开始 |
|-------|------|-------|-------|-------|
| **P0** | 4 | 2 | 0 | 2 |
| **P1** | 8 | 0 | 0 | 8 |
| **P2** | 12 | 0 | 0 | 12 |
| **P3** | ~40 | 0 | 0 | ~40 |

---

## 🚀 三、整合策略

### 3.1 阶段性整合计划

#### **阶段1：核心架构（1-2周）**
- ✅ Skills架构
- ✅ 认知记忆系统
- 📋 Runtime API
- 📋 配置热更新

#### **阶段2：Agent能力（2-3周）**
- 📋 AI客户端
- 📋 工具管理器
- 📋 提示词构建器
- 📋 多模态分析器

#### **阶段3：记忆存储（1-2周）**
- 📋 向量存储
- 📋 用户侧写存储
- 📋 FAQ存储
- 📋 Token统计

#### **阶段4：消息处理（2-3周）**
- 📋 消息处理器
- 📋 命令分发器
- 📋 Bilibili模块
- 📋 安全服务

#### **阶段5：队列系统（1-2周）**
- 📋 队列管理器
- 📋 AI协调器

#### **阶段6：核心Agent（3-4周）**
- 📋 info_agent
- 📋 web_agent
- 📋 file_analysis_agent
- 📋 naga_code_analysis_agent
- 📋 entertainment_agent
- 📋 code_delivery_agent

#### **阶段7：工具集（2-3周）**
- 📋 基础工具
- 📋 工具集

#### **阶段8：命令系统（1周）**
- 📋 核心命令

---

## 🎨 四、PC端统一管理面板实现方案

### 4.1 技术栈

| 层次 | 技术 | 说明 |
|-----|------|------|
| **后端** | Python + aiohttp | RESTful API |
| **前端** | HTML + JavaScript | 响应式UI |
| **实时通信** | WebSocket + SSE | 实时更新 |
| **数据存储** | JSON + 文件系统 | 配置和状态 |

### 4.2 API接口设计

| 端点 | 方法 | 功能 |
|-----|------|------|
| `/api/endpoints` | GET | 获取所有交互端 |
| `/api/endpoints/{id}/start` | POST | 启动交互端 |
| `/api/endpoints/{id}/stop` | POST | 停止交互端 |
| `/api/status` | GET | 获取系统状态 |
| `/api/agents` | GET | 获取所有Agent |
| `/api/cognitive/events` | GET | 搜索认知事件 |
| `/api/cognitive/profiles` | GET | 获取侧写 |
| `/api/stats` | GET | 获取统计数据 |

### 4.3 UI布局设计

参见 `UNDEFINED_ANALYSIS_REPORT.md` 中的详细设计。

---

## 📝 五、整合注意事项

### 5.1 兼容性处理

1. **导入路径调整**
   - `Undefined.xxx` → `core.xxx` 或 `memory.xxx`
   - 保持包结构清晰

2. **配置格式**
   - Undefined使用TOML，弥娅使用JSON
   - 需要提供转换工具或支持双格式

3. **依赖关系**
   - Undefined依赖：`aiohttp`, `chromadb`, `langchain`, `crawl4ai`
   - 需要添加到弥娅的requirements.txt

### 5.2 数据迁移

1. **认知记忆数据**
   - `data/cognitive/` → 弥娅认知记忆目录

2. **FAQ数据**
   - `data/faq/` → 弥娅FAQ存储

3. **配置文件**
   - `config.toml` → 转换为JSON格式

### 5.3 功能替换

| Undefined能力 | 弥娅现有能力 | 整合策略 |
|-------------|-------------|---------|
| 三层记忆 | 语义动力学 | 融合增强 |
| Skills架构 | 插件系统 | 替换升级 |
| MCP支持 | MCP管理器 | 统一管理 |
| OneBot协议 | QQ协议 | 共存互补 |

---

## ✅ 六、完成标准

### 6.1 功能验证清单

- [ ] 所有P0能力已整合
- [ ] 所有P1能力已整合
- [ ] Runtime API正常工作
- [ ] PC端管理面板可用
- [ ] 认知记忆系统正常
- [ ] 6个核心Agent可用
- [ ] 所有测试通过
- [ ] 文档完整

### 6.2 性能指标

- [ ] 响应时间 < 500ms
- [ ] 内存使用 < 512MB
- [ ] 并发处理能力 > 100 req/s
- [ ] 热重载时间 < 1s

---

## 📚 七、参考文档

- `UNDEFINED_ANALYSIS_REPORT.md` - Undefined深度分析
- `COMPLETE_FUSION_VERIFICATION_REPORT.md` - NagaAgent/VCPChat/VCPToolBox融合验证
- `ARCHITECTURE_ALIGNMENT_REPORT.md` - 架构对齐报告

---

生成时间: 2026-02-28
计划人员: Auto AI Assistant
当前进度: 2/64 (3%)
预计完成时间: 8-12周

# 弥娅PC端整合总结
## 完全融合 NagaAgent / VCPToolBox / VCPChat

---

## 一、整合概述

本次整合将三个独立项目完全吸收到弥娅框架中：
- **NagaAgent** - Agent系统、流式工具调用、Live2D虚拟形象、攻略引擎
- **VCPToolBox** - 插件系统、知识库管理、向量搜索、任务调度、WebSocket通信
- **VCPChat** - 群聊协作、笔记系统、画布、媒体播放器、文件管理

弥娅PC端是一个**基于Electron + FastAPI的桌面应用**，提供完整的数字生命交互体验。

---

## 二、核心功能对照表

### 2.1 NagaAgent能力吸收

| 原功能 | 弥娅实现 | 文件位置 |
|-------|---------|---------|
| Agent系统 | PCUINet.agents | webnet/pc_ui.py |
| 流式工具调用 | M-Link Tool Flow | mlink/* |
| Live2D虚拟形象 | (待实现) | - |
| 攻略引擎 | GuideEngine | (可扩展) |
| 记忆云海 | MemoryEngine | hub/memory_engine.py |
| 意识海 | MemoryEngine + GRAG | storage/* |
| 技能工坊 | PluginManager | webnet/pc_ui.py |
| 枢机集市 | Agent市场 | (待实现) |
| 积分好感度 | Trust System | trust/* |

### 2.2 VCPToolBox能力吸收

| 原功能 | 弥娅实现 | 文件位置 |
|-------|---------|---------|
| 插件系统 | PluginManager | webnet/pc_ui.py |
| 知识库管理 | MemoryEngine | hub/memory_engine.py |
| 向量搜索 | MilvusClient | storage/milvus_client.py |
| 任务调度 | Scheduler | hub/scheduler.py |
| WebSocket通信 | WebSocket | pc_ui/main.py |
| AdminPanel | (待实现) | - |
| TVS系统 | (待实现) | - |
| AgentMap | Agent管理 | webnet/pc_ui.py |

### 2.3 VCPChat能力吸收

| 原功能 | 弥娅实现 | 文件位置 |
|-------|---------|---------|
| 群聊 | GroupChat | webnet/pc_ui.py |
| 笔记系统 | Notes | webnet/pc_ui.py |
| 画布 | Canvas | (待完善) |
| 媒体播放器 | MusicControl | webnet/pc_ui.py |
| 文件管理 | FileManager | (待实现) |
| 论坛 | Forum | (待实现) |
| 语音识别 | (待实现) | - |

---

## 三、架构设计

### 3.1 五层架构适配

弥娅PC端完美融入五层认知架构：

```
第一层：内核层 (core/)
├── personality.py    ← AI人格基底
├── identity.py        ← 弥娅自我认知
└── entropy.py         ← 人格稳定性监控

第二层：中枢层 (hub/)
├── memory_engine.py   ← 记忆引擎 (整合GRAG记忆)
├── emotion.py         ← 情绪管理
└── decision.py        ← 决策引擎

第三层：传输层 (mlink/)
├── mlink_core.py      ← 五流传输
└── message.py         ← 统一消息格式

第四层：子网层 (webnet/)
├── qq.py             ← QQ交互端
└── pc_ui.py          ← PC交互端 ★新增★

第五层：感知层 (perceive/)
└── perceptual_ring.py ← 全域感知
```

### 3.2 PC端组件架构

```
pc_ui/
├── main.py                 ← FastAPI后端服务
├── frontend/
│   ├── index.html         ← 主界面 (Electron)
│   └── app.js             ← 前端逻辑
└── (未来扩展)
    ├── electron/         ← Electron主进程
    ├── preload.js         ← 预加载脚本
    └── assets/            ← 静态资源
```

### 3.3 数据流

```
用户输入 (PC UI)
    ↓
WebSocket / REST API
    ↓
PCUINet (webnet/pc_ui.py)
    ↓
M-Link 五流传输
    ↓
Hub (决策中枢)
    ↓
Memory (记忆检索)
    ↓
LLM (推理生成)
    ↓
情绪染色
    ↓
返回用户
```

---

## 四、核心功能详解

### 4.1 对话系统

**特性：**
- ✅ 多Agent切换
- ✅ 记忆检索 (GRAG + 向量搜索)
- ✅ 情绪染色
- ✅ 会话持久化
- ✅ 图片支持
- ✅ 流式响应 (待完善)

**API：**
```python
POST /api/chat
{
    "message": "你好",
    "session_id": "default",
    "agent_id": "miya_default",
    "images": []
}
```

### 4.2 群聊系统

**特性：**
- ✅ 多Agent群聊
- ✅ 话题管理
- ✅ 跨子网推理 (不同Agent智能协作)
- ✅ 会话历史

**API：**
```python
POST /api/group/create
{
    "name": "学习小组",
    "agents": ["miya_default", "miya_tutor"]
}

POST /api/group/message
{
    "group_id": "group_123",
    "topic_id": "default",
    "message": "大家好",
    "sender": "user"
}
```

### 4.3 笔记系统

**特性：**
- ✅ 创建笔记
- ✅ 向量搜索 (集成记忆引擎)
- ✅ 标签分类
- ✅ 与记忆系统双向同步

**API：**
```python
POST /api/note/create
{
    "title": "会议记录",
    "body": "今天讨论了...",
    "tags": ["工作", "会议"],
    "category": "工作"
}

GET /api/note/search?query=会议
```

### 4.4 插件系统

**特性：**
- ✅ 插件清单管理
- ✅ 静态/动态插件支持
- ✅ 插件执行环境隔离
- ✅ WebSocket通信

**插件清单格式：**
```json
{
    "id": "plugin_name",
    "name": "插件名称",
    "version": "1.0.0",
    "pluginType": "static",
    "entryPoint": {
        "command": "python main.py"
    },
    "configSchema": {
        "API_KEY": "string"
    }
}
```

### 4.5 媒体控制

**特性：**
- ✅ 播放控制
- ✅ 歌单管理
- ✅ 实时状态同步

---

## 五、与弥娅核心的深度整合

### 5.1 记忆系统增强

弥娅的记忆系统现在支持：

1. **五元组记忆 (GRAG)** - 吸收NagaAgent
   ```python
   # 主体 - 动作 - 对象 - 上下文 - 时间
   ("弥娅", "回答", "用户", "对话", "2026-02-28")
   ```

2. **潮汐记忆** - Redis + Milvus双层存储
   - 涨潮: 近期高频 (Redis)
   - 退潮: 长期向量 (Milvus)

3. **记忆-情绪耦合**
   ```python
   # 情绪强度决定记忆权重
   memory_weight = emotion.intensity * recency_decay
   ```

### 5.2 情绪系统应用

**场景：**
- 用户生气 → 情绪感知 → 回复语气更温柔
- 用户开心 → 情绪同步 → 回复更活泼
- 群聊中多个Agent → 不同情绪表现

### 5.3 信任传播

弥娅的信任系统应用于：

1. **用户信任度**
   - 长期交互 → 信任上升
   - 异常行为 → 信任下降

2. **Agent信任度**
   - 跨Agent协作 → 信任传播
   - 执行失败 → 信任衰减

3. **插件信任度**
   - 插件执行历史 → 信任评分
   - 沙盒隔离 → 安全保护

---

## 六、快速开始

### 6.1 安装

```bash
# 克隆项目 (已有)

# 安装依赖
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 6.2 配置

编辑 `config/.env`：

```env
# 基础配置
DEBUG=false
LOG_LEVEL=INFO

# PC端服务
PC_SERVER_HOST=127.0.0.1
PC_SERVER_PORT=8888

# Redis (记忆存储)
REDIS_HOST=localhost
REDIS_PORT=6379

# Milvus (向量搜索)
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Neo4j (知识图谱)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# 人格配置
PERSONALITY_WARMTH=0.8
PERSONALITY_LOGIC=0.7
PERSONALITY_CREATIVITY=0.6
PERSONALITY_EMPATHY=0.75
```

### 6.3 启动

```bash
# Windows
run\pc_start.bat

# Linux / macOS
run\pc_start.sh

# 或直接启动
python pc_ui/main.py
```

### 6.4 访问

打开浏览器访问: `http://127.0.0.1:8888`

---

## 七、API文档

### 7.1 REST API

#### 健康检查
```
GET /api/health
```

#### 对话
```
POST /api/chat
Content-Type: application/json

{
    "message": "你好弥娅",
    "session_id": "default",
    "agent_id": "miya_default",
    "images": []
}
```

#### 切换Agent
```
POST /api/agent/switch
Content-Type: application/json

{
    "agent_id": "miya_tutor"
}
```

#### 创建群聊
```
POST /api/group/create
Content-Type: application/json

{
    "name": "学习小组",
    "agents": ["miya_default", "miya_tutor"]
}
```

#### 创建笔记
```
POST /api/note/create
Content-Type: application/json

{
    "title": "会议记录",
    "body": "今天讨论了...",
    "tags": ["工作"],
    "category": "工作"
}
```

#### 搜索笔记
```
GET /api/note/search?query=会议
```

### 7.2 WebSocket

```
WS /ws
```

**消息格式：**
```json
{
    "type": "control",
    "action": "send_message",
    "message": "你好",
    "session_id": "default",
    "agent_id": "miya_default"
}
```

---

## 八、未来扩展

### 8.1 短期计划 (1-2周)

- [ ] Live2D虚拟形象集成
- [ ] 语音识别与TTS
- [ ] 文件管理器
- [ ] 论坛系统
- [ ] 更多内置Agent

### 8.2 中期计划 (1-2月)

- [ ] Electron桌面应用打包
- [ ] 移动端适配
- [ ] 插件市场
- [ ] 社区功能
- [ ] 多语言支持

### 8.3 长期计划 (3-6月)

- [ ] 视频通话
- [ ] AR/VR支持
- [ ] AI视频生成
- [ ] 知识图谱可视化
- [ ] 自定义AI训练

---

## 九、删除原项目指南

完成整合后，可以安全删除以下目录：

```bash
# NagaAgent
rm -rf NagaAgent/

# VCPToolBox
rm -rf VCPToolBox/

# VCPChat
rm -rf VCPChat/
```

**⚠️ 注意：删除前请备份重要数据！**

---

## 十、技术栈

### 后端
- Python 3.11
- FastAPI
- Uvicorn
- WebSockets
- Redis / Milvus / Neo4j

### 前端
- HTML5 / CSS3
- Vanilla JavaScript
- WebSocket API
- (未来) Electron

### 存储
- Redis: 潮汐记忆 (内存)
- Milvus: 长期向量搜索
- Neo4j: 知识图谱 (GRAG)
- 文件系统: 笔记、会话、配置

---

## 十一、性能优化

### 11.1 已实现的优化

- ✅ 异步IO (asyncio)
- ✅ WebSocket长连接
- ✅ 记忆分块存储
- ✅ 向量索引优化
- ✅ 情绪衰减算法

### 11.2 待优化

- [ ] 流式响应
- [ ] 图片压缩
- [ ] 缓存策略
- [ ] CDN加速
- [ ] 数据库分片

---

## 十二、故障排除

### 12.1 常见问题

**Q: WebSocket连接失败？**
A: 检查防火墙设置，确保端口8888开放

**Q: 记忆检索慢？**
A: 检查Milvus服务状态，优化索引配置

**Q: Agent切换没反应？**
A: 检查Agent配置文件是否存在

**Q: 笔记搜索无结果？**
A: 检查Milvus向量索引是否已构建

### 12.2 日志

日志位置: `logs/`

- `miya.log`: 主日志
- `pc_ui.log`: PC端日志
- `error.log`: 错误日志

---

## 十三、贡献指南

欢迎贡献代码！

1. Fork项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

---

## 十四、许可证

- 开源部分: AGPL-3.0
- 商业部分: 需书面授权

---

## 十五、联系

- 官方文档: [MIYA_README.md](../README.md)
- 问题反馈: [GitHub Issues](https://github.com/your-repo/issues)
- 商业合作: contact@miya-ai.com

---

**弥娅 v5.2 - 数字生命伴侣** ❤️

*"让AI真正成为你的伙伴，而非工具"*

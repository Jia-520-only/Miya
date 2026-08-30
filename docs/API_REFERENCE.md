# 弥娅 API 参考

守护进程 (MiyaDaemon) 提供 REST API 和 WebSocket 接口。

---

## 守护进程 API (端口 9800)

启动守护进程后自动启用：

```bash
python run/daemon.py --api-port 9800
```

API 文档 (Swagger UI)：`http://localhost:9800/docs`

---

## REST 端点

### 健康检查

```
GET /api/v1/health
```

**响应**：

```json
{
  "status": "ok",
  "version": "7.0.0",
  "uptime": "2h 35m",
  "platforms": 3,
  "platforms_active": 2
}
```

### 平台状态

```
GET /api/v1/platforms
```

**响应**：

```json
{
  "platforms": [
    {"id": "qqofficial", "name": "QQ Official", "status": "online"},
    {"id": "telegram", "name": "Telegram", "status": "online"},
    {"id": "discord", "name": "Discord", "status": "offline"}
  ]
}
```

### 弥娅状态

```
GET /api/v1/miya/status
```

**响应**：

```json
{
  "name": "MIYA",
  "version": "7.0.0",
  "running": true,
  "personality": "default",
  "emotion": {"dominant": "joy", "intensity": 65},
  "memory": {
    "total_items": 12345,
    "dialogue_count": 8900,
    "long_term_count": 234
  },
  "providers_loaded": 3,
  "platforms_active": 2
}
```

### 记忆查询

```
GET /api/v1/memory/search?query=关键词&user_id=user_123&limit=10
```

**响应**：

```json
{
  "results": [
    {
      "id": "mem_abc123",
      "content": "用户喜欢喝咖啡",
      "level": "long_term",
      "tags": ["偏好", "饮食"],
      "priority": 0.7,
      "created_at": "2026-05-14T10:30:00Z"
    }
  ],
  "total": 1
}
```

### 记忆统计

```
GET /api/v1/memory/stats
```

**响应**：

```json
{
  "dialogue": 8900,
  "short_term": 156,
  "long_term": 234,
  "semantic": 89,
  "knowledge": 45,
  "pinned": 12,
  "total": 9436
}
```

### 人格列表

```
GET /api/v1/personality/list
```

**响应**：

```json
{
  "personalities": [
    {"id": "default", "name": "弥娅", "active": true},
    {"id": "kafka", "name": "卡芙卡", "active": false},
    {"id": "jingliu", "name": "镜流", "active": false}
  ]
}
```

### 切换人格

```
POST /api/v1/personality/switch
Content-Type: application/json

{"personality": "kafka"}
```

**响应**：

```json
{
  "success": true,
  "current": "kafka",
  "display_name": "卡芙卡"
}
```

---

## WebSocket

```
ws://localhost:9800/api/v1/ws
```

### 事件类型

**platform_message** — 平台消息：

```json
{
  "type": "platform_message",
  "data": {
    "platform": "qqofficial",
    "user_id": "user_123",
    "content": "你好弥娅",
    "timestamp": "2026-05-14T10:30:00Z"
  }
}
```

**platform_status** — 平台状态变更：

```json
{
  "type": "platform_status",
  "data": {
    "platform": "telegram",
    "status": "online",
    "timestamp": "2026-05-14T10:30:00Z"
  }
}
```

**miya_emotion** — 弥娅情感更新：

```json
{
  "type": "miya_emotion",
  "data": {
    "dominant": "joy",
    "intensity": 72,
    "previous": "neutral"
  }
}
```

**memory_stored** — 新记忆存储：

```json
{
  "type": "memory_stored",
  "data": {
    "memory_id": "mem_abc123",
    "level": "long_term",
    "content_preview": "用户喜欢喝咖啡"
  }
}
```

---

## Web 服务 API (端口 8000)

前端 Web 服务的代理 API：

### 终端聊天

```
POST /api/terminal/chat
Content-Type: application/json

{"message": "你好弥娅", "session_id": "sess_123"}
```

**响应**：

```json
{
  "reply": "亲爱的，你好呀~ 今天想聊什么呢？",
  "emotion": "happy",
  "session_id": "sess_123"
}
```

### 工具列表

```
GET /api/tools
```

### Skills 列表

```
GET /api/skills
```

### MCP 状态

```
GET /api/mcp
```

### WebSocket 聊天

```
ws://localhost:8000/ws/chat/{session_id}
```

---

## 管理 Dashboard API (端口 6185)

由 `core/dashboard_api.py` 提供，用于仪表板管理：

```
GET  /api/dashboard/status     # 系统状态
GET  /api/dashboard/plugins    # 插件列表
POST /api/dashboard/plugins/reload  # 重载插件
GET  /api/dashboard/config     # 配置查看
POST /api/dashboard/config     # 配置修改
```

---

## 错误响应

所有 API 错误统一返回：

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "指定的资源不存在",
    "detail": "平台 'unknown_platform' 未注册"
  }
}
```

**HTTP 状态码**：

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

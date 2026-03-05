# QQ机器人配置指南

> 本指南详细说明如何配置和启动弥娅QQ机器人

---

## 前置要求

弥娅QQ机器人需要以下组件：

1. **OneBot协议实现**（任选其一）
   - [NapCat](https://github.com/NapNeko/NapCatQQ) - 推荐（基于NTQQ）
   - [go-cqhttp](https://github.com/Mrs4s/go-cqhttp) - 经典选择
   - [LLOneBot](https://github.com/LLOneBot/LLOneBot) - 另一个基于NTQQ的选择

2. **QQ账号** - 机器人使用的QQ号

3. **配置文件** - `.env` 配置

---

## 快速开始

### 步骤1：安装OneBot实现

#### 推荐使用 NapCat（基于NTQQ）

1. 下载 [NapCat](https://github.com/NapNeko/NapCatQQ/releases)
2. 解压并运行
3. 配置WebSocket端口（默认：3001）

#### 或使用 go-cqhttp

1. 下载 [go-cqhttp](https://github.com/Mrs4s/go-cqhttp/releases)
2. 解压并运行
3. 配置WebSocket端口（默认：3001）

### 步骤2：配置弥娅

编辑 `config/.env` 文件：

```env
# QQ机器人配置
QQ_ONEBOT_WS_URL=ws://localhost:3001
QQ_ONEBOT_TOKEN=
QQ_BOT_QQ=你的机器人QQ号
QQ_SUPERADMIN_QQ=你的管理员QQ号
```

### 步骤3：启动OneBot

**NapCat:**
```bash
# 运行NapCat
NapCat.exe
```

**go-cqhttp:**
```bash
# 运行go-cqhttp
go-cqhttp.exe
```

### 步骤4：启动弥娅QQ机器人

```batch
# Windows
run\qq_start.bat

# 或使用启动菜单选择 2
```

---

## 详细配置

### OneBot配置

#### NapCat配置示例

```json
{
  "ws": {
    "enable": true,
    "host": "0.0.0.0",
    "port": 3001
  },
  "http": {
    "enable": true,
    "host": "127.0.0.1",
    "port": 3000
  }
}
```

#### go-cqhttp配置示例

```yaml
servers:
  - ws-reverse:
      universal: ws://127.0.0.1:3001/ws
  - ws:
      address: 0.0.0.0:3001
```

### 弥娅配置

编辑 `config/.env`：

```env
# ========================================
# QQ机器人配置
# ========================================

# OneBot WebSocket地址
QQ_ONEBOT_WS_URL=ws://localhost:3001

# OneBot访问令牌（如果OneBot配置了token）
QQ_ONEBOT_TOKEN=your_token_here

# 机器人QQ号
QQ_BOT_QQ=123456789

# 超级管理员QQ号（可多个，逗号分隔）
QQ_SUPERADMIN_QQ=987654321

# 群聊白名单（可选，逗号分隔，空则允许所有群）
QQ_GROUP_WHITELIST=

# 群聊黑名单（可选，逗号分隔）
QQ_GROUP_BLACKLIST=

# 用户白名单（可选，逗号分隔，空则允许所有用户）
QQ_USER_WHITELIST=

# 用户黑名单（可选，逗号分隔）
QQ_USER_BLACKLIST=

# 消息前缀（可选）
QQ_MESSAGE_PREFIX=

# 是否仅响应@机器人（true/false）
QQ_ONLY_AT=false

# 自动加好友（true/false）
QQ_AUTO_FRIEND=false

# 自动加群（true/false）
QQ_AUTO_GROUP=false
```

---

## 功能说明

### 基础功能

- ✅ 私聊对话
- ✅ 群聊对话
- ✅ @机器人触发
- ✅ 消息前缀触发
- ✅ 图片消息支持
- ✅ 表情消息支持

### 管理功能

- 📊 系统状态查询（管理员）
- 🔄 重启机器人（管理员）
- 📤 发送公告（管理员）
- 🎨 调整人格（管理员）

### 命令列表

#### 用户命令

| 命令 | 说明 | 示例 |
|-----|------|------|
| `/help` | 帮助信息 | `/help` |
| `/status` | 查看状态 | `/status` |
| `/memory` | 查看记忆 | `/memory 5` |

#### 管理员命令

| 命令 | 说明 | 示例 |
|-----|------|------|
| `/admin:status` | 系统状态 | `/admin:status` |
| `/admin:restart` | 重启机器人 | `/admin:restart` |
| `/admin:personality` | 调整人格 | `/admin:personality warmth +0.1` |
| `/admin:announce` | 发送公告 | `/admin:announce 测试公告` |

---

## 故障排查

### 错误1：远程计算机拒绝网络连接

**错误信息：**
```
[QQ] WebSocket连接失败: [WinError 1225] 远程计算机拒绝网络连接。
```

**原因：**
OneBot服务未启动或端口错误

**解决：**
1. 确认OneBot已启动
2. 检查OneBot的WebSocket端口
3. 检查 `.env` 中的 `QQ_ONEBOT_WS_URL`

```bash
# 测试OneBot是否运行
curl http://localhost:3000  # go-cqhttp
# 或
curl http://localhost:6099  # NapCat
```

### 错误2：认证失败

**错误信息：**
```
[QQ] WebSocket连接失败: Token认证失败
```

**原因：**
Token配置不匹配

**解决：**
1. 检查OneBot的token配置
2. 确保 `.env` 中的 `QQ_ONEBOT_TOKEN` 正确
3. 或者移除token（如果OneBot未配置）

### 错误3：无法发送消息

**原因：**
- 机器人QQ号未配置
- 账号被封禁

**解决：**
1. 检查 `.env` 中的 `QQ_BOT_QQ`
2. 确认QQ账号正常

### 错误4：群聊无响应

**原因：**
- 群聊在黑名单
- 配置了白名单但群不在其中

**解决：**
```env
# 允许所有群
QQ_GROUP_WHITELIST=
QQ_GROUP_BLACKLIST=

# 或添加特定群
QQ_GROUP_WHITELIST=123456789,987654321
```

---

## 高级功能

### 1. 多账号支持

通过复制 `config/.env` 为 `config/.env.qq2` 并创建新的启动脚本：

```batch
@echo off
set MIYA_ENV_FILE=config\.env.qq2
python run\qq_main.py
```

### 2. 自定义消息处理器

修改 `webnet/qq.py` 中的消息处理逻辑：

```python
async def _handle_message(self, msg: QQMessage):
    # 自定义处理逻辑
    if msg.message.startswith("!"):
        await self._handle_command(msg)
    else:
        await self._handle_chat(msg)
```

### 3. 插件集成

弥娅的插件系统与QQ机器人完全集成：

```python
from plugin import PluginManager

# 在QQNet中集成插件
class QQNet:
    def __init__(self, miya):
        self.plugin_manager = PluginManager()
        self.plugin_manager.load_all()
```

---

## 安全建议

1. **设置超级管理员**
   ```env
   QQ_SUPERADMIN_QQ=你的QQ号
   ```

2. **使用Token**
   ```env
   QQ_ONEBOT_TOKEN=随机生成的强密码
   ```

3. **限制群聊范围**
   ```env
   QQ_GROUP_WHITELIST=允许的群号
   ```

4. **定期检查日志**
   ```bash
   logs/miya_qq.log
   ```

---

## 常见问题

### Q: OneBot选哪个？

**A:** 推荐 NapCat（基于NTQQ），因为：
- 稳定性好
- 功能完整
- 支持最新QQ功能
- 活跃维护

### Q: 可以同时运行多个QQ机器人吗？

**A:** 可以。需要：
- 多个QQ账号
- 多个OneBot实例（不同端口）
- 多个配置文件

### Q: 机器人会被封号吗？

**A:** 可能。建议：
- 不要频繁发送消息
- 不要发送垃圾信息
- 遵守QQ使用规范

### Q: 如何更新机器人？

**A:**
```bash
git pull
pip install -r requirements.txt --upgrade
```

---

## 相关链接

- [NapCat GitHub](https://github.com/NapNeko/NapCatQQ)
- [go-cqhttp GitHub](https://github.com/Mrs4s/go-cqhttp)
- [OneBot协议文档](https://11.onebot.dev/)
- [弥娅文档](../README.md)

---

**最后更新：2026-02-28**

# QQ机器人快速参考卡片

> 📋 快速配置和启动弥娅QQ机器人

---

## ⚡ 3分钟快速配置

### 1. 安装OneBot（选一个）

**推荐：NapCat**
```
下载: https://github.com/NapNeko/NapCatQQ/releases
运行: NapCat.exe
```

**或：go-cqhttp**
```
下载: https://github.com/Mrs4s/go-cqhttp/releases
运行: go-cqhttp.exe
```

### 2. 配置弥娅

编辑 `config/.env`：
```env
QQ_ONEBOT_WS_URL=ws://localhost:3001
QQ_BOT_QQ=123456789
QQ_SUPERADMIN_QQ=987654321
```

### 3. 启动

1. 启动OneBot（保持运行）
2. 启动弥娅：
```batch
run\qq_start.bat
```

---

## 📋 常用命令

### 用户命令

| 命令 | 说明 |
|-----|------|
| `/help` | 帮助信息 |
| `/status` | 查看状态 |
| `/memory` | 查看记忆 |

### 管理员命令

| 命令 | 说明 |
|-----|------|
| `/admin:status` | 系统状态 |
| `/admin:personality warmth +0.1` | 调整人格 |
| `/admin:announce 公告内容` | 发送公告 |

---

## ❓ 故障排查

### 连接失败

```
[WinError 1225] 远程计算机拒绝网络连接
```

**解决：**
1. ✅ 检查OneBot是否启动
2. ✅ 检查端口是否正确（默认3001）
3. ✅ 检查 `QQ_BOT_QQ` 是否配置

### 认证失败

```
Token认证失败
```

**解决：**
1. 检查OneBot的token配置
2. 确保 `.env` 中 `QQ_ONEBOT_TOKEN` 正确
3. 或移除token（如果OneBot未配置）

---

## 🔗 相关链接

- 详细配置: [QQ_BOT_SETUP.md](QQ_BOT_SETUP.md)
- NapCat: https://github.com/NapNeko/NapCatQQ
- go-cqhttp: https://github.com/Mrs4s/go-cqhttp
- OneBot协议: https://11.onebot.dev/

---

**提示**: 首次启动会进行配置检查，请确保OneBot服务已运行。

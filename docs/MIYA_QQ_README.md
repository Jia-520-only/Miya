# 弥娅 QQ 机器人

弥娅AI系统的QQ交互端，完整吸收了Undefined项目的QQ机器人能力，并集成到弥娅的五层认知架构中。

## 特性

### 核心能力（完全吸收Undefined）
- ✅ OneBot v11 WebSocket协议支持
- ✅ 群聊和私聊消息处理
- ✅ @机器人和拍一拍响应
- ✅ 消息历史记录
- ✅ 图片、语音、文件等多媒体支持
- ✅ 合并转发消息处理
- ✅ 群成员信息获取
- ✅ 访问控制（黑白名单）
- ✅ 自动重连机制

### 弥娅增强能力
- 🧠 人格恒定系统：确保回复风格一致
- 📝 记忆-情绪耦合：根据互动调整人格
- 🔍 情绪染色：基于当前情绪状态影响回复
- 📊 全域感知：QQ消息集成到感知环
- 🤖 M-Link路由：QQ消息通过五流传输
- 🛡️ 信任系统：与用户的信任值管理

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

编辑 `config/.env` 文件：

```env
# QQ机器人配置
QQ_ONEBOT_WS_URL=ws://localhost:3001
QQ_ONEBOT_TOKEN=
QQ_BOT_QQ=123456789
QQ_SUPERADMIN_QQ=987654321

# 可选：访问控制
QQ_GROUP_WHITELIST=123456,789012
QQ_GROUP_BLACKLIST=
QQ_USER_WHITELIST=
QQ_USER_BLACKLIST=
```

## 启动

### Windows
```bash
run/qq_start.bat
```

### Linux/Mac
```bash
chmod +x run/qq_start.sh
./run/qq_start.sh
```

### 直接运行
```bash
python run/qq_main.py
```

## 使用示例

### 群聊
```
用户: @弥娅 你好
弥娅: 用户你好呀~我是弥娅，很高兴认识你！
```

### 私聊
```
用户: 你好
弥娅: 你好呀~我是弥娅，很高兴认识你！
```

### 拍一拍
```
用户 拍了拍你
弥娅: 被用户拍了呢~
```

### 查询状态
```
用户: @弥娅 状态
弥娅: 当前情绪状态: joy，强度: 0.80
      记忆数量: 15
```

## 架构说明

### QQ子网在弥娅中的位置

```
第三层：弹性分支子网集群
├── LifeNet (生活子网)
├── HealthNet (健康子网)
├── FinanceNet (财务子网)
├── SocialNet (社交节点)  ← QQNet在此层
├── IoTNet (IoT控制节点)
├── ToolNet (工具执行节点)
├── SecurityNet (安全审计节点)
└── QQNet (QQ交互子网)    ← 新增
```

### 消息流程

```
QQ消息
  ↓
QQOneBotClient (接收)
  ↓
QQNet (访问控制、历史记录)
  ↓
弥娅感知环 (全域感知)
  ↓
弥娅中枢 (决策引擎 + 记忆-情绪耦合)
  ↓
弥娅内核 (人格、伦理、仲裁)
  ↓
响应生成 (情绪染色)
  ↓
QQOneBotClient (发送)
  ↓
QQ消息 (输出)
```

## 核心模块

### QQOneBotClient
OneBot WebSocket客户端实现，提供完整的API调用能力：
- 发送群/私聊消息
- 获取消息历史
- 获取群/用户信息
- 拍一拍
- 转发消息
- 文件上传
- 等等...

### QQNet
QQ交互子网，弥娅架构的一部分：
- 消息路由和分发
- 访问控制
- 历史记录管理
- 与弥娅核心的集成

### MiyaQQBot
主程序类，整合弥娅核心和QQ子网：
- 初始化弥娅核心层
- 初始化中枢层
- 配置QQ子网
- 消息处理循环

## 与Undefined的对应关系

| Undefined模块 | 弥娅实现 | 位置 |
|--------------|---------|------|
| onebot.py | QQOneBotClient | webnet/qq.py |
| handlers.py | QQNet._handle_* | webnet/qq.py |
| ai_coordinator.py | MiyaQQBot._generate_response | run/qq_main.py |
| main.py | MiyaQQBot.main | run/qq_main.py |

## 高级功能

### 自定义人格

弥娅的人格可以通过代码调整：

```python
from core import Personality

personality = Personality()
personality.update_vector('warmth', 0.1)  # 增加温暖度
personality.update_vector('logic', -0.1)  # 降低逻辑性
```

### 情绪染色

```python
from hub import Emotion

emotion = Emotion()
emotion.apply_coloring('joy', 0.8)  # 应用开心染色
response = emotion.influence_response("你好！")
# 输出可能包含表情符号
```

### 记忆管理

```python
from hub import MemoryEngine

memory = MemoryEngine()
memory.store_tide(
    memory_id="msg_123",
    content={"text": "用户的消息", "emotion": "happy"}
)
```

## Docker部署

```yaml
# docker-compose.yml
services:
  miya-qq:
    build: .
    command: python run/qq_main.py
    environment:
      - QQ_ONEBOT_WS_URL=ws://onebot:3001
      - QQ_BOT_QQ=123456789
    depends_on:
      - onebot

  onebot:
    image: mrs4s/go-cqhttp
    # ... onebot配置
```

## 常见问题

### 1. 连接失败
检查 `QQ_ONEBOT_WS_URL` 配置是否正确，确保OneBot服务已启动。

### 2. 消息无响应
- 检查访问控制设置
- 查看日志确认消息是否被接收
- 确认机器人QQ号配置正确

### 3. 人格漂移
弥娅内置人格熵监控，会自动检测并防止人格过度变化。

## 开发

### 添加自定义命令

在 `MiyaQQBot._generate_response` 中添加：

```python
if '自定义命令' in content:
    return "自定义响应"
```

### 集成其他子网

```python
# 在响应中调用其他子网
result = await self.life_net.process_request({
    'type': 'add_schedule',
    'data': {...}
})
```

## 许可证

MIT License

## 致谢

感谢 [Undefined](https://github.com/69gg/Undefined) 项目提供的优秀QQ机器人实现。

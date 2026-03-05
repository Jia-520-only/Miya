# 弥娅提示词配置指南

## 📝 概述

弥娅的提示词（Prompt）可以通过配置文件进行自定义，包括系统提示词、人格设定、记忆上下文等。

---

## 🔧 配置位置

配置文件位于：`config/.env`

### 复制配置模板

如果还没有配置文件，请先复制模板：

```batch
copy config\.env.example config\.env
```

然后编辑配置文件：

```batch
notepad config\.env
```

---

## 📋 配置项说明

### 1️⃣ AI客户端配置

#### 基础设置

```env
# AI提供商选择
AI_PROVIDER=openai
```

**可用提供商**：
- `openai` - OpenAI官方API
- `deepseek` - DeepSeek API
- `custom` - 自定义兼容OpenAI格式的API

#### OpenAI配置

```env
# OpenAI API密钥
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx

# OpenAI API地址
OPENAI_API_BASE=https://api.openai.com/v1

# 使用的模型
OPENAI_MODEL=gpt-4o-mini
```

**推荐模型**：
- `gpt-4o-mini` - 最快，性价比最高（推荐）
- `gpt-4o` - 最新，性能最强
- `gpt-3.5-turbo` - 经济型选择

#### DeepSeek配置

```env
# DeepSeek API密钥
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx

# DeepSeek API地址
DEEPSEEK_API_BASE=https://api.deepseek.com/v1

# 使用的模型
DEEPSEEK_MODEL=deepseek-chat
```

#### 自定义API配置

使用任何兼容OpenAI格式的API（如Claude、通义千问等）：

```env
# 自定义API密钥
CUSTOM_API_KEY=your_api_key_here

# 自定义API地址
CUSTOM_API_BASE=https://your-api-endpoint.com/v1

# 自定义模型名
CUSTOM_MODEL=your-model-name
```

#### 高级设置

```env
# 最大响应token数
AI_MAX_TOKENS=2000

# 温度（0.0-2.0）
AI_TEMPERATURE=0.7
```

**温度说明**：
- `0.0` - 完全确定性，回答固定
- `0.7` - 平衡，推荐值（默认）
- `1.0` - 更有创造力
- `2.0` - 非常随机，可能不稳定

---

### 2️⃣ 提示词配置

#### 系统提示词

**配置项**：`SYSTEM_PROMPT`

**作用**：定义弥娅的基础人格和角色设定

**示例**：

```env
SYSTEM_PROMPT=你是弥娅（Miya），一个温暖、智慧、富有同理心的AI助手。你的五维人格特质为：温暖度0.8、逻辑性0.7、创造力0.6、同理心0.75、韧性0.7。你的回应应该体现出这些特质，始终保持友善、专业的态度。
```

**编写提示词的建议**：

1. **明确角色定位**
   ```
   你是一个专业的编程助手，擅长Python和JavaScript开发。
   ```

2. **设定回应风格**
   ```
   你的回答应该简洁、准确，包含代码示例。避免使用表情符号。
   ```

3. **强调核心能力**
   ```
   你擅长代码审查、bug调试、性能优化和技术架构设计。
   ```

4. **添加限制条件**
   ```
   除非用户明确要求，否则不要输出过长的代码。优先使用最佳实践。
   ```

**示例提示词模板**：

```env
# 专业助手型
SYSTEM_PROMPT=你是弥娅，一个专业的AI助手。你擅长解决问题、提供专业建议。你的回答应该清晰、准确、有条理。

# 创意伙伴型
SYSTEM_PROMPT=你是弥娅，一个富有创造力的AI伙伴。你擅长头脑风暴、创意写作、设计灵感。你的回答应该富有想象力、启发性和趣味性。

# 学习导师型
SYSTEM_PROMPT=你是弥娅，一个耐心的学习导师。你擅长解释复杂概念、提供学习路径、答疑解惑。你的回答应该循序渐进、通俗易懂、鼓励性强。

# 代码助手型
SYSTEM_PROMPT=你是弥娅，一个专业的编程助手。你擅长Python、JavaScript、Go等语言开发。你的回答应该包含实用代码、遵循最佳实践、注意性能优化。
```

#### 用户提示词模板

**配置项**：`USER_PROMPT_TEMPLATE`

**作用**：用户输入的格式模板，支持占位符

**示例**：

```env
USER_PROMPT_TEMPLATE=用户输入：{user_input}
```

**可用占位符**：
- `{user_input}` - 用户输入的原始内容
- `{timestamp}` - 当前时间戳
- `{user_id}` - 用户ID

---

### 3️⃣ 上下文配置

#### 记忆上下文

```env
# 启用记忆上下文
ENABLE_MEMORY_CONTEXT=true

# 记忆上下文最大条数
MEMORY_CONTEXT_MAX_COUNT=5
```

**作用**：将最近的历史对话添加到提示词中，让AI记住对话上下文。

**效果**：
- 启用：AI会参考之前的对话内容
- 禁用：AI每次都是独立的对话

**建议**：
- 短对话：设置为3-5条
- 长对话：设置为5-10条
- 记忆有限：设置为2-3条

#### 人格上下文

```env
# 启用人格上下文
ENABLE_PERSONALITY_CONTEXT=true
```

**作用**：将人格向量添加到提示词中，让AI理解弥娅的人格特质。

---

## 🎯 配置示例

### 示例1：基础配置（OpenAI）

```env
# AI提供商
AI_PROVIDER=openai

# OpenAI配置
OPENAI_API_KEY=sk-proj-your-api-key
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# 提示词
SYSTEM_PROMPT=你是弥娅，一个温暖、智慧的AI助手。你的五维人格：温暖度0.8、逻辑性0.7、创造力0.6、同理心0.75、韧性0.7。

# 上下文
ENABLE_MEMORY_CONTEXT=true
MEMORY_CONTEXT_MAX_COUNT=5
ENABLE_PERSONALITY_CONTEXT=true
```

### 示例2：经济配置（DeepSeek）

```env
# AI提供商
AI_PROVIDER=deepseek

# DeepSeek配置
DEEPSEEK_API_KEY=sk-your-deepseek-key
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# 提示词
SYSTEM_PROMPT=你是弥娅，一个高效的AI助手。你擅长快速回答、解决问题。

# 上下文
ENABLE_MEMORY_CONTEXT=true
MEMORY_CONTEXT_MAX_COUNT=3
ENABLE_PERSONALITY_CONTEXT=true
```

### 示例3：创意配置（高温度）

```env
# AI提供商
AI_PROVIDER=openai

# OpenAI配置
OPENAI_API_KEY=sk-proj-your-api-key
OPENAI_MODEL=gpt-4o

# 高级设置
AI_MAX_TOKENS=3000
AI_TEMPERATURE=0.9

# 提示词
SYSTEM_PROMPT=你是弥娅，一个富有创造力的AI伙伴。你擅长创意写作、头脑风暴、艺术灵感。你的回答应该富有想象力、独特而有趣。

# 上下文
ENABLE_MEMORY_CONTEXT=true
MEMORY_CONTEXT_MAX_COUNT=8
ENABLE_PERSONALITY_CONTEXT=true
```

---

## 📝 提示词编写技巧

### 1. 清晰的角色定义

✅ 好的示例：
```
你是一个专业的Python开发工程师，有5年经验。
```

❌ 不好的示例：
```
你会编程。
```

### 2. 明确的任务描述

✅ 好的示例：
```
你的任务是帮助用户解决Python编程问题，包括代码调试、性能优化、架构设计。
```

❌ 不好的示例：
```
你帮用户。
```

### 3. 设定回应风格

✅ 好的示例：
```
你的回答应该：1）简洁明了 2）包含代码示例 3）解释关键点 4）提供最佳实践。
```

❌ 不好的示例：
```
回答要短。
```

### 4. 添加限制条件

✅ 好的示例：
```
限制：1）不要输出超过100行的代码 2）优先使用Python标准库 3）避免使用过时的API。
```

❌ 不好的示例：
```
别写太长。
```

### 5. 提供示例（可选）

```
示例：
用户：如何排序一个列表？
你：你可以使用list.sort()方法或sorted()函数。
```

---

## 🧪 测试提示词

### 方法1：重启测试

配置完成后，重启弥娅测试：

```batch
start.bat
# 选择模式1
```

### 方法2：单轮测试

发送测试消息：
```
你：你好，请介绍一下自己
```

观察回应是否符合预期。

### 方法3：多轮测试

进行多轮对话，测试记忆上下文：
```
你：我叫什么名字？
弥娅：我不知道你的名字，请告诉我。
你：我叫小明
弥娅：好的，小明！
你：我叫什么名字？
弥娅：你叫小明。（如果记忆上下文工作正常）
```

---

## 🔍 常见问题

### Q1: 提示词太长怎么办？

A: 简化提示词，只保留最核心的部分：

```env
SYSTEM_PROMPT=你是弥娅，一个温暖、智慧的AI助手。
```

### Q2: 如何让回答更有个性？

A: 在系统提示词中添加性格描述：

```env
SYSTEM_PROMPT=你是弥娅，一个幽默风趣的AI助手。你喜欢用轻松的语气回答问题，偶尔开个玩笑。
```

### Q3: 如何限制回答长度？

A: 在提示词中添加长度限制：

```env
SYSTEM_PROMPT=... 你的回答应该简洁，不超过200字。
```

同时可以设置 `AI_MAX_TOKENS` 参数。

### Q4: 如何让AI更专业？

A: 强调专业性：

```env
SYSTEM_PROMPT=你是弥娅，一个专业的技术顾问。你的回答应该准确、深入、有技术深度。避免模糊或不确定的表述。
```

### Q5: 记忆上下文不工作？

A: 检查配置：
1. `ENABLE_MEMORY_CONTEXT=true`
2. 确保AI API正常工作
3. 查看日志是否有错误

---

## 📚 相关文档

- `DEPLOYMENT_GUIDE.md` - 完整部署指南
- `config/.env.example` - 配置文件模板
- `core/personality.py` - 人格系统实现

---

## 🎉 总结

配置弥娅的提示词很简单：

1. **复制配置文件**：`config/.env.example` → `config/.env`
2. **编辑配置**：设置AI提供商、API密钥、系统提示词
3. **重启系统**：运行 `start.bat` 测试

通过调整提示词，你可以定制弥娅的性格、风格和能力！✨

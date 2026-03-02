# 大模型API接入指南

> 本指南详细说明如何配置弥娅的大模型API接入

---

## 支持的AI提供商

弥娅目前支持以下AI提供商：

| 提供商 | 标识符 | 推荐模型 | 优势 |
|-------|---------|---------|------|
| OpenAI | `openai` | GPT-4o, GPT-4o-mini | 能力最强，生态完善 |
| DeepSeek | `deepseek` | deepseek-chat | 国产模型，性价比高 |
| Anthropic | `anthropic` | Claude 3 Sonnet | 长文本能力强 |
| 智谱AI | `zhipu` | GLM-4 | 国产模型，中文友好 |

---

## 快速开始（5分钟配置）

### 1. 选择AI提供商

**新手推荐**：DeepSeek（免费额度多，质量好）
- 注册：https://platform.deepseek.com/
- 获取API Key

**追求质量**：OpenAI
- 注册：https://platform.openai.com/
- 获取API Key

**长文本需求**：Anthropic (Claude)
- 注册：https://console.anthropic.com/
- 获取API Key

### 2. 配置弥娅

编辑 `config/.env` 文件：

```env
# 选择提供商
AI_PROVIDER=openai

# OpenAI配置
AI_OPENAI_API_KEY=sk-your-api-key-here
AI_OPENAI_MODEL=gpt-4o

# 生成参数（可选）
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=2000
```

或使用DeepSeek：
```env
AI_PROVIDER=deepseek

AI_DEEPSEEK_API_KEY=sk-your-api-key-here
AI_DEEPSEEK_MODEL=deepseek-chat
```

### 3. 安装依赖

根据选择的提供商安装对应库：

```bash
# OpenAI / DeepSeek（都使用openai库）
pip install openai

# Anthropic
pip install anthropic

# 智谱AI
pip install zhipuai
```

### 4. 重启弥娅

```batch
# 重新启动QQ机器人
run\qq_start.bat
```

---

## 详细配置

### OpenAI

#### 配置项

```env
# ========================================
# AI大模型配置
# ========================================
# AI提供商：openai, deepseek, anthropic, zhipu
AI_PROVIDER=openai

# OpenAI API密钥
AI_OPENAI_API_KEY=sk-your-openai-api-key

# OpenAI API基础URL（可选，用于代理或兼容接口）
AI_OPENAI_BASE_URL=

# OpenAI模型名称
AI_OPENAI_MODEL=gpt-4o
```

#### 推荐模型

| 模型 | 价格 | 速度 | 推荐用途 |
|-----|------|------|---------|
| gpt-4o | 较高 | 快 | 综合能力强 |
| gpt-4o-mini | 较低 | 很快 | 日常对话 |
| gpt-4-turbo | 中等 | 快 | 性价比 |

#### 代理配置

如果需要使用代理：

```env
# 国内兼容API（如中转服务）
AI_OPENAI_BASE_URL=https://your-proxy.com/v1
```

### DeepSeek

#### 配置项

```env
AI_PROVIDER=deepseek

# DeepSeek API密钥
AI_DEEPSEEK_API_KEY=sk-your-deepseek-api-key

# DeepSeek API基础URL（可选）
AI_DEEPSEEK_BASE_URL=

# DeepSeek模型名称
AI_DEEPSEEK_MODEL=deepseek-chat
```

#### 推荐模型

| 模型 | 价格 | 优势 |
|-----|------|------|
| deepseek-chat | 便宜 | 中文优秀，逻辑强 |
| deepseek-coder | 便宜 | 编程能力强 |

#### 注册获取API Key

1. 访问 https://platform.deepseek.com/
2. 注册/登录
3. 进入 API Keys 页面
4. 创建新Key

### Anthropic (Claude)

#### 配置项

```env
AI_PROVIDER=anthropic

# Anthropic API密钥
AI_ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key

# Anthropic模型名称
AI_ANTHROPIC_MODEL=claude-3-sonnet-20240229
```

#### 推荐模型

| 模型 | 价格 | 优势 |
|-----|------|------|
| claude-3-sonnet-20240229 | 较高 | 综合最强 |
| claude-3-haiku-20240307 | 较低 | 速度快 |

#### 注册获取API Key

1. 访问 https://console.anthropic.com/
2. 注册/登录
3. 进入 API Keys 页面
4. 创建新Key

### 智谱AI (GLM)

#### 配置项

```env
AI_PROVIDER=zhipu

# 智谱AI API密钥
AI_ZHIPU_API_KEY=your-zhipu-api-key

# 智谱AI模型名称
AI_ZHIPU_MODEL=glm-4
```

#### 推荐模型

| 模型 | 优势 |
|-----|------|
| glm-4 | 综合能力强，中文优秀 |
| glm-3-turbo | 速度快，便宜 |

#### 注册获取API Key

1. 访问 https://open.bigmodel.cn/
2. 注册/登录
3. 进入 API Keys 页面
4. 创建新Key

---

## 生成参数

### Temperature（温度）

控制回复的随机性：

```env
AI_TEMPERATURE=0.7
```

| 值 | 效果 | 适用场景 |
|-----|------|---------|
| 0.0-0.3 | 稳定、一致 | 代码、数学 |
| 0.4-0.7 | 平衡 | 日常对话 |
| 0.8-1.0 | 创意、多样 | 创作、头脑风暴 |

### Max Tokens（最大长度）

控制回复的最大长度：

```env
AI_MAX_TOKENS=2000
```

| 值 | 适用场景 |
|-----|---------|
| 500 | 简短回答 |
| 2000 | 中等长度 |
| 4000 | 详细回答 |

---

## 故障排查

### 错误1：API Key未配置

**错误信息：**
```
未配置AI API密钥，将使用简化回复
```

**解决：**
1. 编辑 `config/.env`
2. 添加对应的API Key：
   ```env
   AI_OPENAI_API_KEY=sk-your-key
   ```
3. 重启弥娅

### 错误2：库未安装

**错误信息：**
```
OpenAI库未安装，请运行: pip install openai
```

**解决：**
```bash
# OpenAI / DeepSeek
pip install openai

# Anthropic
pip install anthropic

# 智谱AI
pip install zhipuai
```

### 错误3：API调用失败

**错误信息：**
```
OpenAI API调用失败: Invalid API key
```

**原因：**
- API Key错误
- 账号额度不足
- 网络问题

**解决：**
1. 检查API Key是否正确
2. 确认账号有足够额度
3. 检查网络连接

### 错误4：模型不存在

**错误信息：**
```
Model not found: xxx
```

**解决：**
检查模型名称是否正确：

```env
# 正确
AI_OPENAI_MODEL=gpt-4o

# 错误
AI_OPENAI_MODEL=gpt-4
```

### 错误5：超时

**错误信息：**
```
Connection timeout
```

**解决：**
1. 检查网络连接
2. 如果在国内，使用代理或中转API
3. 或使用国产模型（DeepSeek、智谱AI）

---

## 高级功能

### 切换提供商

运行时切换提供商：

1. 编辑 `config/.env`：
   ```env
   AI_PROVIDER=deepseek
   AI_DEEPSEEK_API_KEY=sk-new-key
   ```
2. 重启弥娅

### 自定义模型

使用自定义模型或微调模型：

```env
AI_PROVIDER=openai
AI_OPENAI_BASE_URL=https://your-custom-api.com/v1
AI_OPENAI_MODEL=your-custom-model
```

### 降级机制

当AI API不可用时，弥娅会自动降级到简化回复模式，确保基本功能可用。

---

## 成本估算

### OpenAI (GPT-4o)

| 模型 | 输入价格 | 输出价格 |
|-----|---------|---------|
| gpt-4o | $5/1M tokens | $15/1M tokens |
| gpt-4o-mini | $0.15/1M tokens | $0.6/1M tokens |

**估算：**
- 1000条消息 ≈ $0.01-0.05

### DeepSeek

| 模型 | 输入价格 | 输出价格 |
|-----|---------|---------|
| deepseek-chat | ¥1/1M tokens | ¥2/1M tokens |

**估算：**
- 1000条消息 ≈ ¥0.003-0.01

### Anthropic (Claude)

| 模型 | 输入价格 | 输出价格 |
|-----|---------|---------|
| claude-3-sonnet | $3/1M tokens | $15/1M tokens |
| claude-3-haiku | $0.25/1M tokens | $1.25/1M tokens |

---

## 最佳实践

1. **新手推荐**：先用DeepSeek测试，免费额度多
2. **追求质量**：OpenAI GPT-4o
3. **长文本**：Anthropic Claude 3
4. **成本控制**：调整`AI_MAX_TOKENS`，减少输出长度
5. **稳定性**：使用多个提供商做备份

---

## 相关链接

- [OpenAI Platform](https://platform.openai.com/)
- [DeepSeek Platform](https://platform.deepseek.com/)
- [Anthropic Console](https://console.anthropic.com/)
- [智谱AI开放平台](https://open.bigmodel.cn/)
- [弥娅主README](../README.md)
- [QQ机器人配置](QQ_BOT_SETUP.md)

---

## Q&A

### Q: 可以同时使用多个提供商吗？

**A:** 当前不支持同时使用，但可以通过修改配置快速切换。

### Q: 如何监控API用量？

**A:** 登录各提供商的控制台查看用量统计。

### Q: 国内使用哪个最好？

**A:** 推荐 DeepSeek（便宜、中文好）或智谱AI。

### Q: API Key泄露怎么办？

**A:** 立即在控制台删除旧Key，创建新Key。

---

**最后更新：2026-02-28**

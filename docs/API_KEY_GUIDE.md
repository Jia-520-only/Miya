# API Key 使用说明

## 核心答案

### ❌ 错误理解
```
每个模型都需要一个独立的 API Key
```

### ✅ 正确理解
```
同一个厂商的 API Key 可以同时用于该厂商下的多个模型
```

## 📝 详细说明

### API Key 的作用

API Key 是**验证身份的凭证**，而不是**绑定特定模型的钥匙**。

- **API Key** = 用户的账号凭证
- **模型** = 账号下可使用的服务

### 类比理解

想象一个**健身房会员卡**：

```
❌ 错误理解：
每个健身器械都需要办一张卡
- 跑步机卡、哑铃卡、动感单车卡...

✅ 正确理解：
办一张会员卡，可以使用所有器械
- 一张会员卡 = 所有器械都可用
```

**API Key 就像健身会员卡**：
- 一张卡 = 该提供商的所有模型都能用
- 不同厂商 = 不同健身房 = 需要不同的卡

## 🔑 实际示例

### 示例 1: 硅基流动

**注册地址**: https://cloud.siliconflow.cn/i/pEXepR3y

```
你的硅基流动 API Key: sk-xxxxxxxxxxxx

这个 Key 可以同时使用：
✅ Qwen/Qwen2.5-7B-Instruct
✅ Qwen/Qwen2.5-72B-Instruct
✅ THUDM/glm-4-9b-chat
✅ internlm/internlm2_5-7b-chat
✅ deepseek-ai/DeepSeek-R1-Distill-Qwen-7B
✅ deepseek-ai/DeepSeek-V3
✅ meta-llama/Llama-3.1-8B-Instruct
✅ google/gemma-2-9b-it
...以及硅基流动提供的所有其他模型

只需配置: 1 个 API Key
```

### 示例 2: DeepSeek 官方

**注册地址**: https://platform.deepseek.com/

```
你的 DeepSeek API Key: sk-yyyyyyyyyyyy

这个 Key 可以同时使用：
✅ deepseek-chat (DeepSeek V3)
✅ deepseek-reasoner (DeepSeek R1)

只需配置: 1 个 API Key
```

### 示例 3: Groq

**注册地址**: https://console.groq.com/

```
你的 Groq API Key: gsk_zzzzzzzzzzz

这个 Key 可以同时使用：
✅ llama-3.1-8b-instant
✅ llama-3.1-70b-versatile
✅ mixtral-8x7b-32768
...以及 Groq 提供的所有模型

只需配置: 1 个 API Key
```

## 📊 API Key 需求总结

### 最小配置：1 个 API Key ✅

```
DeepSeek 官方 API Key: sk-xxxx

可使用模型:
✅ deepseek_v3_official
✅ deepseek_r1_official

配置状态: 已有 ✅
```

### 推荐配置：2 个 API Keys

```
1. DeepSeek 官方 API Key: sk-xxxx
   可使用: deepseek_v3_official, deepseek_r1_official

2. 硅基流动 API Key: sk-yyyy
   可使用: qwen_7b, qwen_72b, glm_4_9b, internlm_7b,
          deepseek_r1_distill_7b, llama_3_1_8b, gemma_2_9b

总计: 2 个 API Keys
覆盖: 所有 10 个模型槽位
```

### 高级配置：3-4 个 API Keys

```
1. DeepSeek API Key
   → deepseek_v3_official, deepseek_r1_official

2. 硅基流动 API Key
   → qwen_7b, qwen_72b, glm_4_9b, internlm_7b,
     deepseek_r1_distill_7b, llama_3_1_8b, gemma_2_9b

3. Groq API Key（可选）
   → llama_3_1_8b（超高速版本）

4. OpenRouter API Key（可选）
   → GPT-4, Claude 3.5, Gemma 免费版等
```

## 🎯 配置助手的使用

运行配置助手：

```bash
python setup_multi_model.py
```

选择 **选项 5**（快速配置硅基流动）时：

```
正在将所有模型槽位配置到: 硅基流动 SiliconFlow
请输入硅基流动 API Key: sk-your-siliconflow-key-here

✅ 已更新 7 个模型槽位
  ✓ qwen_7b → Qwen/Qwen2.5-7B-Instruct
  ✓ qwen_72b → Qwen/Qwen2.5-72B-Instruct
  ✓ glm_4_9b → THUDM/glm-4-9b-chat
  ✓ internlm_7b → internlm/internlm2_5-7b-chat
  ✓ deepseek_r1_distill_7b → deepseek-ai/DeepSeek-R1-Distill-Qwen-7B
  ✓ llama_3_1_8b → meta-llama/Llama-3.1-8B-Instruct
  ✓ gemma_2_9b → google/gemma-2-9b-it
```

**注意**：这 7 个模型使用的是**同一个**硅基流动 API Key！

## 💡 常见误区

### 误区 1: 每个模型都要注册账号

❌ 错误：
```
硅基流动注册账号1 → 用于 qwen_7b
硅基流动注册账号2 → 用于 qwen_72b
硅基流动注册账号3 → 用于 glm_4_9b
...
```

✅ 正确：
```
硅基流动注册 1 个账号 → 用于所有硅基流动模型
```

### 误区 2: API Key 和模型一一对应

❌ 错误：
```
qwen_7b 的 API Key: sk-xxx
qwen_72b 的 API Key: sk-yyy
glm_4_9b 的 API Key: sk-zzz
```

✅ 正确：
```
硅基流动 API Key: sk-xxx
qwen_7b 使用: sk-xxx
qwen_72b 使用: sk-xxx
glm_4_9b 使用: sk-xxx
```

### 误区 3: 必须配置所有模型的 Key

❌ 错误：
"不配置所有 10 个模型槽位，系统无法运行"

✅ 正确：
```
只配置 1-2 个厂商的 API Key 即可
- DeepSeek（已有）→ 覆盖 2 个模型
- DeepSeek + 硅基流动 → 覆盖所有 10 个模型
```

## 🔄 配置文件中的重复配置

### 原配置的问题

```json
{
  "models": {
    "qwen_7b": {
      "api_key": "YOUR_SILICONFLOW_API_KEY"
    },
    "qwen_72b": {
      "api_key": "YOUR_SILICONFLOW_API_KEY"
    },
    "glm_4_9b": {
      "api_key": "YOUR_SILICONFLOW_API_KEY"
    }
    ...
  }
}
```

**问题**：每个模型都有 `api_key` 字段，看起来像需要多个 Key

### 实际使用方式

配置助手会自动将**同一个** API Key 填充到所有硅基流动模型：

```bash
python setup_multi_model.py
# 选择选项 5
# 输入: sk-your-siliconflow-key

结果：
✅ qwen_7b.api_key = sk-your-siliconflow-key
✅ qwen_72b.api_key = sk-your-siliconflow-key
✅ glm_4_9b.api_key = sk-your-siliconflow-key
...
```

**实际上它们使用的是同一个 Key！**

## ✅ 总结

| 问题 | 答案 |
|------|------|
| 每个模型需要单独的 API Key 吗？ | ❌ 不需要 |
| 同一个厂商的 API Key 可以用于多个模型吗？ | ✅ 可以 |
| 需要为每个模型注册账号吗？ | ❌ 不需要 |
| 1 个厂商的 API Key 覆盖多少模型？ | 该厂商提供的所有模型 |
| 弥娅系统最少需要几个 API Key？ | 1 个（DeepSeek 已有） |
| 推荐配置几个 API Key？ | 2 个（DeepSeek + 硅基流动）|

## 🎁 实际配置示例

```json
{
  "models": {
    "deepseek_v3_official": {
      "api_key": "sk-15346aa170c442c69d726d8e95cabca3"
    },
    "deepseek_r1_official": {
      "api_key": "sk-15346aa170c442c69d726d8e95cabca3"  // 同一个 DeepSeek Key
    },
    "qwen_7b": {
      "api_key": "sk-your-siliconflow-key"
    },
    "qwen_72b": {
      "api_key": "sk-your-siliconflow-key"  // 同一个硅基流动 Key
    },
    "glm_4_9b": {
      "api_key": "sk-your-siliconflow-key"  // 同一个硅基流动 Key
    }
    ...
  }
}
```

看到！DeepSeek 的两个模型用同一个 Key，硅基流动的多个模型也用同一个 Key！

## 🚀 行动建议

1. **注册硅基流动**：https://cloud.siliconflow.cn/i/pEXepR3y
2. **获取 1 个 API Key**
3. **运行配置助手**：
   ```bash
   python setup_multi_model.py
   选择选项 5
   ```
4. **输入你的 1 个硅基流动 API Key**
5. **完成！** - 所有 7 个硅基流动模型都会使用这 1 个 Key

**总计需要：2 个 API Keys**
- 1 个 DeepSeek（已有 ✅）
- 1 个 硅基流动（待配置 ⚠️）

就这么简单！🎉

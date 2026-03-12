# 弥娅多模型配置完成

## ✅ 已配置的模型槽位

总计 **10 个模型槽位**已配置到弥娅系统中。

### DeepSeek 官方（2个）
- ✅ `deepseek_v3` - DeepSeek Chat（通用模型）
- ✅ `deepseek_r1` - DeepSeek Reasoner（推理模型）

### 硅基流动 SiliconFlow（8个）
- ⚠️ `siliconflow_qwen_7b` - Qwen 2.5 7B（免费）
- ⚠️ `siliconflow_qwen_72b` - Qwen 2.5 72B（高性能）
- ⚠️ `siliconflow_glm_4` - GLM-4 9B（代码专家）
- ⚠️ `siliconflow_internlm` - InternLM 2.5 7B（中文理解）
- ⚠️ `siliconflow_deepseek_r1_distill_7b` - DeepSeek R1 蒸馏版（轻量推理）
- ⚠️ `siliconflow_deepseek_v3` - DeepSeek V3 满血版（高性能）
- ⚠️ `siliconflow_llama_3_1_8b` - Llama 3.1 8B（Meta开源，免费）
- ⚠️ `siliconflow_gemma_2_9b` - Gemma 2 9B（Google开源）

**说明**:
- ✅ = 已配置 API Key，可直接使用
- ⚠️ = 需要配置 API Key

## 🚀 快速配置

### 方法 1: 使用配置助手（推荐）

```bash
python setup_multi_model.py
```

按照提示选择：
1. 查看当前配置状态
2. 配置 DeepSeek API Key
3. 配置硅基流动 API Key
4. 同时配置两个 API Key

### 方法 2: 手动配置

#### 配置 DeepSeek API Key

编辑 `config/.env`：
```bash
AI_API_KEY=sk-your-deepseek-api-key-here
```

#### 配置硅基流动 API Key

1. 注册获取 API Key: https://cloud.siliconflow.cn/i/pEXepR3y
2. 新用户免费获得 **2000 万 Tokens**

编辑 `config/.env`：
```bash
SILICONFLOW_API_KEY=sk-your-siliconflow-api-key-here
```

编辑 `config/multi_model_config.json`，将所有硅基流动模型的 `api_key` 替换为实际值。

## 📊 智能路由策略

系统会根据任务类型自动选择最优模型：

| 任务类型 | 主模型 | 次选 | 回退 |
|---------|--------|------|------|
| 简单对话 | Qwen 7B（免费） | Llama 8B（免费） | DeepSeek V3 |
| 复杂推理 | DeepSeek R1 | R1 Distill 7B | Qwen 72B |
| 代码分析 | GLM-4 9B | DeepSeek V3 | R1 Distill 7B |
| 代码生成 | GLM-4 9B | DeepSeek V3 | Gemma 2 9B |
| 工具调用 | DeepSeek V3 | DeepSeek V3（硅基） | Qwen 72B |

## 💰 成本优化

### 免费模型推荐
- **Qwen 2.5 7B**: 日常对话、简单任务
- **InternLM 2.5 7B**: 中文理解
- **DeepSeek R1 Distill 7B**: 轻量推理
- **Llama 3.1 8B**: 摘要、分类

### 付费模型优势
- **Qwen 2.5 72B**: 复杂任务性能更佳
- **DeepSeek R1**: 深度推理能力强
- **GLM-4 9B**: 代码生成质量高

## 📝 配置文件位置

- **多模型配置**: `config/multi_model_config.json`
- **环境变量**: `config/.env`
- **配置助手**: `setup_multi_model.py`
- **详细文档**: `MULTI_MODEL_SETUP_GUIDE.md`

## 🔗 快速链接

- 硅基流动注册: https://cloud.siliconflow.cn/i/pEXepR3y
- DeepSeek 注册: https://platform.deepseek.com/
- 详细配置指南: `MULTI_MODEL_SETUP_GUIDE.md`

## ✨ 下一步

1. 运行 `python setup_multi_model.py` 配置 API Keys
2. 重启弥娅系统: `start.bat` 或 `./start.sh`
3. 系统会自动加载所有已配置的模型
4. 根据任务类型，系统会智能选择最优模型

## 📞 常见问题

**Q: 硅基流动的免费额度能用多久？**
A: 新用户免费 2000 万 Tokens，按照正常使用频率，可以持续使用数月到数年。

**Q: 是否必须配置所有模型？**
A: 不是。只配置 DeepSeek 也可以正常运行，但建议至少配置硅基流动的免费模型以获得更好的路由选择。

**Q: 如何查看使用了哪个模型？**
A: 查看日志文件 `logs/miya.log`，会记录每次请求使用的模型。

**Q: 超出免费额度后怎么办？**
A: 系统会自动切换到 DeepSeek 官方模型，你也可以在硅基流动控制台充值继续使用。

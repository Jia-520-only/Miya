# 弥娅多模型配置指南

## 概述

弥娅系统现已支持多模型配置，可以同时使用多个AI服务提供商的模型，根据任务类型自动选择最优模型。

## 已配置的模型槽位

### 1. DeepSeek 官方模型（2个槽位）

| 模型键 | 模型名称 | 描述 | 主要用途 | API Key |
|-------|---------|------|---------|---------|
| `deepseek_v3` | `deepseek-chat` | DeepSeek V3 - 快速响应的通用模型 | 简单对话、工具调用、中文理解 | 已配置 ✓ |
| `deepseek_r1` | `deepseek-reasoner` | DeepSeek R1 - 深度推理模型 | 复杂推理、代码分析、创意写作 | 已配置 ✓ |

**注册地址**: https://platform.deepseek.com/

### 2. 硅基流动（SiliconFlow）模型（8个槽位）

| 模型键 | 模型名称 | 描述 | 主要用途 | 费用 | API Key |
|-------|---------|------|---------|------|---------|
| `siliconflow_qwen_7b` | `Qwen/Qwen2.5-7B-Instruct` | Qwen 2.5 7B - 快速通用模型 | 简单对话、摘要、分类 | **免费** | ⚠️ 待配置 |
| `siliconflow_qwen_72b` | `Qwen/Qwen2.5-72B-Instruct` | Qwen 2.5 72B - 高性能模型 | 复杂推理、创意写作 | 付费 | ⚠️ 待配置 |
| `siliconflow_glm_4` | `THUDM/glm-4-9b-chat` | GLM-4 9B - 清华智谱 | 代码生成、代码分析 | 付费 | ⚠️ 待配置 |
| `siliconflow_internlm` | `internlm/internlm2_5-7b-chat` | InternLM 2.5 7B - 书生浦语 | 简单对话、中文理解 | **免费** | ⚠️ 待配置 |
| `siliconflow_deepseek_r1_distill_7b` | `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B` | DeepSeek R1 蒸馏 7B | 轻量级推理、代码分析 | **免费** | ⚠️ 待配置 |
| `siliconflow_deepseek_v3` | `deepseek-ai/DeepSeek-V3` | DeepSeek V3 满血版 | 工具调用、代码分析 | 付费 | ⚠️ 待配置 |
| `siliconflow_llama_3_1_8b` | `meta-llama/Llama-3.1-8B-Instruct` | Llama 3.1 8B - Meta开源 | 简单对话、摘要 | **免费** | ⚠️ 待配置 |
| `siliconflow_gemma_2_9b` | `google/gemma-2-9b-it` | Gemma 2 9B - Google开源 | 代码分析、创意写作 | **免费** | ⚠️ 待配置 |

**注册地址**: https://cloud.siliconflow.cn/i/pEXepR3y
**新用户福利**: 免费获得 2000 万 Tokens（约 ¥200 价值）

## 配置步骤

### 步骤 1: 获取硅基流动 API Key

1. 访问 https://cloud.siliconflow.cn/i/pEXepR3y
2. 注册账号并登录
3. 进入控制台 → API Keys
4. 点击"创建新密钥"
5. 复制生成的 API Key（格式：`sk-xxxxx`）

### 步骤 2: 配置 `.env` 文件

编辑 `config/.env` 文件，找到以下行并填入你的 API Key：

```bash
# 硅基流动 API Key
SILICONFLOW_API_KEY=sk-your-actual-api-key-here
```

### 步骤 3: 更新 `multi_model_config.json`

编辑 `config/multi_model_config.json`，将所有硅基流动模型的 `api_key` 字段从 `YOUR_SILICONFLOW_API_KEY` 替换为实际的 API Key。

**注意**: 你需要替换以下 8 个模型配置中的 `api_key`：
- `siliconflow_qwen_7b`
- `siliconflow_qwen_72b`
- `siliconflow_glm_4`
- `siliconflow_internlm`
- `siliconflow_deepseek_r1_distill_7b`
- `siliconflow_deepseek_v3`
- `siliconflow_llama_3_1_8b`
- `siliconflow_gemma_2_9b`

### 步骤 4: 重启弥娅系统

```bash
# Windows
start.bat

# Linux/Mac
./start.sh
```

启动时会显示已加载的模型列表，确认所有模型都已成功加载。

## 模型路由策略

系统会根据任务类型自动选择最优模型：

| 任务类型 | 主模型 | 次选模型 | 回退模型 |
|---------|--------|---------|---------|
| 简单对话 | Qwen 2.5 7B（免费） | Llama 3.1 8B（免费） | DeepSeek V3 |
| 复杂推理 | DeepSeek R1 | DeepSeek R1 Distill 7B | Qwen 2.5 72B |
| 代码分析 | GLM-4 9B | DeepSeek V3 | DeepSeek R1 Distill 7B |
| 代码生成 | GLM-4 9B | DeepSeek V3 | Gemma 2 9B |
| 工具调用 | DeepSeek V3 | DeepSeek V3（硅基流动） | Qwen 2.5 72B |
| 创意写作 | DeepSeek R1 | Qwen 2.5 72B | DeepSeek V3 |
| 中文理解 | Qwen 2.5 7B | InternLM 2.5 7B | DeepSeek V3 |
| 摘要总结 | Llama 3.1 8B | Qwen 2.5 7B | DeepSeek V3 |
| 多模态 | DeepSeek V3 | DeepSeek V3（硅基流动） | Qwen 2.5 72B |
| 任务规划 | DeepSeek V3 | Qwen 2.5 72B | DeepSeek R1 |

## 免费模型推荐

如果希望最小化成本，系统会优先使用以下免费模型：

### 硅基流动免费模型
- **Qwen 2.5 7B**: 适合日常对话、简单任务
- **InternLM 2.5 7B**: 适合中文理解
- **DeepSeek R1 Distill 7B**: 适合轻量级推理
- **Llama 3.1 8B**: 适合摘要、分类

### 付费模型优势
- **Qwen 2.5 72B**: 复杂任务性能更佳
- **DeepSeek R1**: 深度推理能力强
- **GLM-4 9B**: 代码生成质量高

## 预算控制

系统支持预算控制，可在 `multi_model_config.json` 中配置：

```json
"budget_control": {
  "daily_budget_usd": 10.0,      // 日预算 $10
  "monthly_budget_usd": 300.0,    // 月预算 $300
  "alert_threshold": 0.8,          // 80% 时警告
  "stop_threshold": 0.95           // 95% 时停止
}
```

## 成本参考

| 模型 | 输入成本/1K tokens | 输出成本/1K tokens | 备注 |
|-----|-------------------|-------------------|------|
| DeepSeek V3 | $0.00014 | $0.00028 | 极低 |
| DeepSeek R1 | $0.00028 | $0.00056 | 中等 |
| Qwen 2.5 7B | $0.0001 | $0.0002 | 极低 |
| Qwen 2.5 72B | $0.0015 | $0.0020 | 中等 |
| GLM-4 9B | $0.00015 | $0.00030 | 极低 |
| Llama 3.1 8B | $0.00008 | $0.00016 | 极低 |

## 性能优化

### 启用缓存
```json
"performance_settings": {
  "enable_caching": true,
  "cache_ttl_seconds": 3600
}
```

### 并行执行
```json
"performance_settings": {
  "enable_parallel_execution": true,
  "max_parallel_models": 3
}
```

## 测试验证

启动后，在终端中输入以下测试命令：

1. **测试简单对话**（应使用免费模型 Qwen 7B）
   ```
   你好
   ```

2. **测试工具调用**（应使用 DeepSeek V3）
   ```
   创建一个PowerShell终端
   ```

3. **测试复杂推理**（应使用 DeepSeek R1）
   ```
   解释量子纠缠的原理
   ```

4. **测试代码生成**（应使用 GLM-4）
   ```
   写一个Python快速排序函数
   ```

## 故障排查

### 问题：模型加载失败
**检查**:
1. API Key 是否正确填写
2. 网络连接是否正常
3. 查看日志文件 `logs/miya.log`

### 问题：总是使用同一个模型
**原因**: 路由策略配置问题
**解决**: 检查 `multi_model_config.json` 中的 `routing_strategy` 配置

### 问题：硅基流动 API 调用失败
**检查**:
1. API Key 是否有效
2. 是否超出免费额度
3. 模型名称是否正确

## 更新日志

### 2025-03-12
- ✅ 配置了 10 个模型槽位（2个 DeepSeek + 8个 硅基流动）
- ✅ 添加了智能路由策略
- ✅ 支持预算控制
- ✅ 支持性能优化配置

## 支持与帮助

- 硅基流动文档: https://docs.siliconflow.cn/
- DeepSeek 文档: https://platform.deepseek.com/api-docs/
- 弥娅文档: https://github.com/your-repo/docs

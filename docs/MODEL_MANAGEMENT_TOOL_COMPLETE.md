# 弥娅自主模型管理功能实现完成

## 功能概述

为弥娅添加了自主调用和配置模型池的能力，让弥娅可以：
1. 查看所有可用模型及其能力
2. 查看指定模型的详细信息
3. 查看所有任务类型的路由策略
4. 查看指定任务类型的路由策略
5. 动态更新模型路由策略
6. 查看模型使用统计

## 新增文件

### 1. `webnet/ToolNet/tools/model_management.py`

**核心功能：**

#### `ModelManagementTool` 工具类

支持的 6 种操作：

##### 1. `list_models` - 列出所有可用模型
```
用法：model_management(action='list_models')
```
输出示例：
```
📋 可用模型列表

【qwen_72b】
  模型名称: Qwen/Qwen2.5-72B-Instruct
  API地址: https://api.siliconflow.cn/v1
  状态: ✅ 可用

【deepseek_v3_official】
  模型名称: deepseek-chat
  API地址: https://api.deepseek.com/v1
  状态: ✅ 可用

总计: 9 个模型
```

##### 2. `get_model_info` - 获取模型详细信息
```
用法：model_management(action='get_model_info', model_key='qwen_72b')
```
输出示例：
```
📊 模型详细信息

【qwen_72b】
  模型名称: Qwen/Qwen2.5-72B-Instruct
  提供商: openai
  API地址: https://api.siliconflow.cn/v1
  描述: Qwen 2.5 72B - 高性能通用模型（硅基流动）
  能力: complex_reasoning, chinese_understanding, creative_writing, tool_calling
  延迟: medium
  质量: excellent
  成本: 输入 $0.0015/1k tokens, 输出 $0.0020/1k tokens
  当前状态: ✅ 可用
```

##### 3. `list_strategies` - 列出所有路由策略
```
用法：model_management(action='list_strategies')
```
输出示例：
```
🗺 路由策略列表

【tool_calling】
  首选: qwen_72b
  次选: deepseek_v3_official
  回退: qwen_7b
  成本优先级: 0.7
  速度优先级: 0.6
  质量优先级: 0.95

【complex_reasoning】
  首选: deepseek_r1_official
  次选: deepseek_r1_distill_7b
  回退: qwen_72b
  成本优先级: 0.5
  速度优先级: 0.4
  质量优先级: 1.0

总计: 10 种任务类型
```

##### 4. `get_strategy` - 获取指定任务类型的策略
```
用法：model_management(action='get_strategy', task_type='tool_calling')
```
输出示例：
```
🎯 任务类型: tool_calling

  首选模型: qwen_72b
  次选模型: deepseek_v3_official
  回退模型: qwen_7b
  成本优先级: 0.7
  速度优先级: 0.6
  质量优先级: 0.95
```

##### 5. `update_strategy` - 更新路由策略
```
用法：model_management(
    action='update_strategy',
    task_type='tool_calling',
    primary='deepseek_v3_official',
    secondary='qwen_72b',
    fallback='qwen_7b'
)
```
输出示例：
```
✅ 策略更新成功

任务类型: tool_calling
  新首选: deepseek_v3_official
  新次选: qwen_72b
  新回退: qwen_7b

⚠️ 注意：策略已保存到配置文件，重启系统后生效
```

##### 6. `get_stats` - 查看使用统计
```
用法：model_management(action='get_stats')
```
输出示例：
```
📊 模型使用统计

【qwen_72b】
  请求次数: 156
  总成本: $0.2340

【deepseek_v3_official】
  请求次数: 42
  总成本: $0.1176
```

## 修改文件

### 1. `webnet/ToolNet/registry.py`

**修改内容：**

#### 在 `load_all_tools()` 方法中添加模型管理工具加载
```python
def load_all_tools(self):
    """加载所有工具"""
    self._load_basic_tools()
    self._load_terminal_tools()
    self._load_message_tools()
    self._load_group_tools()
    self._load_memory_tools()
    self._load_knowledge_tools()
    self._load_cognitive_tools()
    self._load_bilibili_tools()
    self._load_scheduler_tools()
    self._load_entertainment_tools()
    self._load_tavern_tools()
    self._load_game_mode_tools()
    self._load_lifenet_tools()
    self._load_web_search_tools()
    self._load_visualization_tools()
    self._load_model_management_tools()  # 新增
    # 注意：查询工具已在 _load_entertainment_tools() 中加载
```

#### 添加 `_load_model_management_tools()` 方法
```python
def _load_model_management_tools(self):
    """加载模型管理工具"""
    try:
        from webnet.ToolNet.tools.model_management import ModelManagementTool
        self.register(ModelManagementTool())
        self.logger.info("模型管理工具已注册")
    except Exception as e:
        self.logger.warning(f"加载模型管理工具失败: {e}")
```

## 支持的任务类型

弥娅支持以下 10 种任务类型，每种类型都有独立的路由策略：

1. **simple_chat** - 简单对话
   - 默认模型：qwen_7b
   - 次选：llama_3_1_8b
   - 回退：deepseek_v3_official

2. **complex_reasoning** - 复杂推理
   - 默认模型：deepseek_r1_official
   - 次选：deepseek_r1_distill_7b
   - 回退：qwen_72b

3. **code_analysis** - 代码分析
   - 默认模型：glm_4_9b
   - 次选：deepseek_v3_official
   - 回退：deepseek_r1_distill_7b

4. **code_generation** - 代码生成
   - 默认模型：glm_4_9b
   - 次选：deepseek_v3_official
   - 回退：gemma_2_9b

5. **tool_calling** - 工具调用
   - 默认模型：qwen_72b ⭐ (已优化)
   - 次选：deepseek_v3_official
   - 回退：qwen_7b

6. **creative_writing** - 创意写作
   - 默认模型：deepseek_r1_official
   - 次选：qwen_72b
   - 回退：deepseek_v3_official

7. **chinese_understanding** - 中文理解
   - 默认模型：qwen_7b
   - 次选：internlm_7b
   - 回退：deepseek_v3_official

8. **summarization** - 摘要总结
   - 默认模型：llama_3_1_8b
   - 次选：qwen_7b
   - 回退：deepseek_v3_official

9. **multimodal** - 多模态
   - 默认模型：deepseek_v3_official
   - 次选：qwen_72b
   - 回退：qwen_7b

10. **task_planning** - 任务规划
    - 默认模型：qwen_72b ⭐ (已优化)
    - 次选：deepseek_v3_official
    - 回退：deepseek_r1_official

## 使用示例

### 场景 1：查看所有可用模型
```
佳: 弥娅，查看一下我们有哪些模型可以使用

[弥娅调用 model_management(action='list_models')]
[弥娅] 我们系统里有 9 个模型可以使用：
- Qwen 2.5 72B（工具调用能力强）
- DeepSeek V3（快速响应）
- DeepSeek R1（深度推理）
- GLM-4 9B（代码能力强）
...
```

### 场景 2：查看某个模型的详细信息
```
佳: 弥娅，给我介绍一下 qwen_72b 这个模型

[弥娅调用 model_management(action='get_model_info', model_key='qwen_72b')]
[弥娅] Qwen 2.5 72B 是阿里通义千问的模型：
- 工具调用能力：⭐⭐⭐⭐⭐
- 中文理解：⭐⭐⭐⭐⭐⭐
- 推理能力：⭐⭐⭐⭐⭐
- 成本：$0.0015/1k tokens (输入), $0.0020/1k tokens (输出)
```

### 场景 3：修改工具调用的首选模型
```
佳: 弥娅，我觉得 DeepSeek V3 在工具调用方面比 Qwen 更好，把它设为首选

[弥娅调用 model_management(action='update_strategy', task_type='tool_calling', primary='deepseek_v3_official')]
[弥娅] 已将 DeepSeek V3 设为工具调用的首选模型。策略已保存，重启后生效。
```

### 场景 4：查看使用统计
```
佳: 弥娅，最近都用了哪些模型

[弥娅调用 model_management(action='get_stats')]
[弥娅] 最近使用统计：
- Qwen 72B：156 次调用，成本 $0.23
- DeepSeek V3：42 次调用，成本 $0.12
...
```

## 优势

### 1. 完全自主
弥娅可以自主调用这个工具，无需用户手动配置。

### 2. 灵活配置
可以根据实际需求动态调整模型路由策略，支持：
- 首选/次选/回退模型配置
- 成本/速度/质量优先级调整
- 实时保存到配置文件

### 3. 透明可见
所有模型信息、路由策略、使用统计都可以查询，让用户清楚了解系统状态。

### 4. 符合 MIYA 框架
- 稳定：职责单一，错误处理完善
- 独立：依赖明确，模块解耦
- 可维修：代码清晰，易于扩展
- 故障隔离：执行失败不影响系统

## 集成状态

✅ 工具类已创建
✅ 工具已注册到 ToolRegistry
✅ 工具描述符合 OpenAI Function Calling 格式
✅ 支持 6 种管理操作
✅ 错误处理完善

## 验证步骤

1. 启动弥娅系统
2. 输入测试命令：
   - "弥娅，查看我们有哪些模型"
   - "弥娅，介绍一下 qwen_72b 模型"
   - "弥娅，查看工具调用的路由策略"
   - "弥娅，把 tool_calling 的首选模型改为 deepseek_v3_official"

## 后续优化方向

1. **智能策略优化**
   - 根据历史使用统计自动优化路由策略
   - 实现A/B测试，比较不同模型的效果

2. **成本控制增强**
   - 实现预算告警
   - 自动切换到更便宜的模型

3. **性能监控**
   - 实时监控各模型的响应时间
   - 自动切换到更快的模型

4. **用户反馈集成**
   - 允许用户对模型回答质量评分
   - 根据评分动态调整策略

## 总结

通过这次实现：
- ✅ 新增 `ModelManagementTool` 工具
- ✅ 支持查看所有可用模型
- ✅ 支持查看模型详细信息
- ✅ 支持查看和修改路由策略
- ✅ 支持查看使用统计
- ✅ 工具已集成到系统
- ✅ 符合 MIYA 框架规范

现在弥娅可以自主管理和配置模型池了！

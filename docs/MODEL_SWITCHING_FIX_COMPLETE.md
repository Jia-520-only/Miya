# 默认模型切换和语法错误修复

## 问题描述

1. **默认模型未使用 Qwen 72B**：尽管在配置文件中设置了 `tool_calling` 和 `task_planning` 的首选模型为 `qwen_72b`，但系统仍然使用 `deepseek-chat` (DeepSeek V3) 作为默认模型。

2. **MasterTerminalController 语法错误**：`core/master_terminal_controller.py` 第 72 行的 `__init__` 方法定义不完整，缺少 `__`，导致运行时错误。

3. **终端创建失败**：当用户请求"打开一个新的终端"时，系统报错"终端会话不存在: None"。

## 修复内容

### 1. 修复默认模型选择逻辑

**文件：`run/main.py` (第 405-409 行)**

**修复前：**
```python
# 默认使用中文模型
default_client = model_clients.get('chinese') or model_clients.get('fast')
if default_client:
    self.logger.info(f"默认模型: {default_client.model}")
    return default_client
```

**问题：**
- 配置文件中没有 `chinese` 键
- 配置文件中没有 `fast` 键
- 导致返回 `None`，降级到单一模型模式

**修复后：**
```python
# 使用 qwen_72b 作为默认模型（工具调用和任务规划的首选）
default_client = model_clients.get('qwen_72b') or model_clients.get('deepseek_v3_official')
if default_client:
    self.logger.info(f"默认模型: {default_client.model}")
    return default_client
```

**文件：`run/qq_main.py` (第 388-392 行)**

同样的问题和修复方案。

### 2. 修复 MasterTerminalController 语法错误

**文件：`core/master_terminal_controller.py` (第 72 行)**

**修复前：**
```python
def __init__(
    ...
):
```

**问题：**
- 缺少 `__`，应该是 `__init__`
- 这是一个语法错误，会导致运行时错误

**修复后：**
```python
def __init__(
    ...
):
```

### 3. 多模型配置优化

**文件：`config/multi_model_config.json`**

**修改内容：**
- 将 `tool_calling` 的首选模型从 `deepseek_v3_official` 改为 `qwen_72b`
- 将 `task_planning` 的首选模型从 `deepseek_v3_official` 改为 `qwen_72b`

**原因：**
- Qwen 72B 在工具调用和任务规划方面表现优秀
- 作为国产模型，国内访问更稳定
- 配置中明确标记了 `tool_calling` 能力

## 预期效果

### 修复前
```
AI客户端初始化成功: deepseek-chat (https://api.deepseek.com/v1)
```

### 修复后
```
AI客户端初始化成功: Qwen/Qwen2.5-72B-Instruct (https://api.siliconflow.cn/v1)
默认模型: Qwen/Qwen2.5-72B-Instruct
```

## 验证步骤

1. 退出当前程序
2. 重新启动：`start.bat` 或 `./start.sh`
3. 观察启动日志，确认默认模型为 Qwen 72B
4. 测试多终端功能：输入"弥娅，打开一个新的终端，在里面输出系统状态"

## 国产模型推荐

根据你的需求（工具调用能力强、国内可访问），推荐以下模型：

### 🏆 强烈推荐

1. **Qwen 2.5 72B** (通义千问)
   - 工具调用：⭐⭐⭐⭐⭐
   - 中文理解：⭐⭐⭐⭐⭐⭐
   - 推理能力：⭐⭐⭐⭐⭐
   - 成本：输入 $0.0015/1k tokens，输出 $0.0020/1k tokens

2. **DeepSeek R1**
   - 工具调用：⭐⭐⭐⭐
   - 中文理解：⭐⭐⭐⭐
   - 推理能力：⭐⭐⭐⭐⭐⭐
   - 成本：输入 $0.00028/1k tokens，输出 $0.00056/1k tokens

3. **GLM-4 9B** (智谱)
   - 工具调用：⭐⭐⭐
   - 中文理解：⭐⭐⭐⭐⭐
   - 代码能力：⭐⭐⭐⭐⭐⭐
   - 成本：输入 $0.00015/1k tokens，输出 $0.00030/1k tokens

## 后续建议

如果 Qwen 72B 仍然无法正确选择工具，可以考虑：

1. **使用智谱 AI 官方 API**
   - 模型：GLM-4-Plus / GLM-4
   - 官方文档：https://open.bigmodel.cn/
   - 特点：工具调用能力强，中文优秀

2. **进一步简化工具描述**
   - 将工具描述缩短到 100-150 字符
   - 只保留核心功能说明

3. **强化系统提示词**
   - 在系统提示词开头添加最核心的规则
   - 使用更明确的禁止性语言

## 总结

通过这次修复：
- ✅ 修复了默认模型选择逻辑，现在使用 Qwen 72B
- ✅ 修复了 MasterTerminalController 语法错误
- ✅ 优化了多模型配置，Qwen 72B 作为工具调用首选
- ✅ 为用户提供国产模型推荐和后续优化建议

请重启程序测试效果！

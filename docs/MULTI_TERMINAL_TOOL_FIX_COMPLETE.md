# 多终端工具选择问题修复完成

## 问题描述

用户输入"弥娅，打开一个新的终端，在里面输出系统状态"时，系统调用了 `terminal_command` 工具执行系统状态命令，但没有调用 `multi_terminal` 工具创建新终端。

## 根本原因分析

1. **工具描述过于复杂冗长**
   - `multi_terminal` 工具描述超过 1000 字符
   - `terminal_command` 工具描述包含大量示例和使用说明
   - DeepSeek模型难以从长描述中准确理解工具调用时机

2. **系统提示词过于详细**
   - 包含大量错误案例对比
   - 嵌套多层次的优先级说明
   - AI难以快速抓住关键区分点

3. **工具调用时机不够明确**
   - 两个工具的调用场景有重叠
   - 缺少明确的"禁止"说明

## 修复方案

### 1. 简化工具描述

**multi_terminal 工具描述（优化前）**
- 描述长度：> 1000 字符
- 包含：当前环境信息、何时必须调用（7点）、可用操作（6个）、终端类型说明、使用建议
- 问题：信息过多，AI难以快速理解核心功能

**multi_terminal 工具描述（优化后）**
```
管理多个终端窗口的创建、切换和关闭。仅当用户明确要求"创建终端"、"打开终端"、"新建窗口"、"切换终端"、"关闭终端"时调用。

当前环境：Windows系统，PowerShell shell，当前目录：d:\AI_MIYA_Facyory\MIYA\Miya

操作类型：
- create_terminal: 创建新终端（需要参数：name, terminal_type）
- list_terminals: 列出所有终端
- switch_terminal: 切换到指定终端（需要参数：session_id）
- close_terminal: 关闭指定终端（需要参数：session_id）
- execute_parallel: 在多个终端并行执行命令（需要参数：commands）
- execute_sequence: 在指定终端顺序执行命令（需要参数：session_id, sequence_commands）

终端类型：cmd(仅Windows), powershell(仅Windows), bash, zsh, sh
```
- 描述长度：472 字符（减少 50%+）
- 核心改进：
  - 明确调用时机："仅当用户明确要求...时调用"
  - 简化操作说明，只保留必要的参数说明
  - 移除冗余的环境信息和使用建议

**terminal_command 工具描述（优化后）**
```
执行单个系统命令。仅当用户要求执行明确的系统命令（如ls、cd、pwd、git、python等）或查看系统信息时调用。

当前环境：Windows系统，PowerShell shell，当前目录：d:\AI_MIYA_Facyory\MIYA\Miya

重要：如果用户要求"创建终端"、"打开终端"或"新建窗口"，必须调用multi_terminal工具，而不是此工具！
```
- 描述长度：186 字符（减少 80%+）
- 核心改进：
  - 明确调用时机："仅当用户要求执行明确的系统命令时"
  - 添加"禁止"说明，明确不应处理的场景
  - 强调与 multi_terminal 的区分

### 2. 优化系统提示词

**优化前**：包含大量错误案例对比、多层级优先级说明、详细操作示例

**优化后**：简化为清晰的规则说明

```
【工具调用规则 - 最重要】

当用户请求涉及"终端"、"窗口"时，必须正确选择工具：

✅ 如果用户要求创建、打开、新建终端 → 调用 multi_terminal(action='create_terminal', ...)
   例如："打开一个终端"、"创建新终端"、"开个PowerShell"、"建个bash终端"

✅ 如果用户要求列出、查看终端 → 调用 multi_terminal(action='list_terminals')
   例如："列出所有终端"、"看看开了几个终端"、"查看终端状态"

✅ 如果用户要求切换终端 → 调用 multi_terminal(action='switch_terminal', session_id='...')
   例如："切换到终端2"、"换到后端终端"

✅ 如果用户要求关闭终端 → 调用 multi_terminal(action='close_terminal', session_id='...')
   例如："关闭终端1"、"把测试终端关了"

✅ 如果用户要求执行系统命令（但不涉及创建终端） → 调用 terminal_command(command='...')
   例如："ls"、"pwd"、"git status"、"查看当前目录"、"列出文件"

❌ 严重错误：当用户说"打开一个终端"时，调用 terminal_command(command='echo 你好')

✅ 正确做法：当用户说"打开一个终端"时，调用 multi_terminal(action='create_terminal', name='新终端', terminal_type='powershell')
```

### 3. 工具描述规范化

在 `ToolRegistry.get_tools_schema()` 中已添加增强逻辑，确保工具描述包含明确的调用时机说明：
- 如果描述中不包含"当"、"调用"、"如果"等关键词，自动添加提示
- 确保每个工具都有清晰的调用说明

## 修复文件清单

### 修改的文件
1. `webnet/TerminalNet/tools/multi_terminal.py` - 简化工具描述
2. `webnet/TerminalNet/tools/terminal_command.py` - 简化工具描述并添加区分说明
3. `prompts/miya_terminal.json` - 优化系统提示词

### 测试验证
- 工具描述长度验证：multi_terminal (472字符)、terminal_command (186字符)
- 描述内容验证：包含明确调用时机、操作说明、区分说明
- 工具加载验证：成功加载 91 个工具

## 预期效果

修复后，当用户输入"弥娅，打开一个新的终端，在里面输出系统状态"时：

1. AI 应该识别到关键关键词："打开"、"终端"
2. AI 应该选择 `multi_terminal` 工具，action 为 `create_terminal`
3. 创建终端后，AI 再选择 `terminal_command` 工具执行系统状态命令

## 后续建议

如果 DeepSeek 模型仍然无法正确选择工具，可以考虑：

1. **切换到更强的模型**：使用 Claude 模型替代 DeepSeek
   - Claude 在工具调用和自然语言理解方面表现更好
   - 可以更准确地理解复杂的提示词和工具描述

2. **进一步简化工具描述**
   - 将工具描述缩短到 100-150 字符以内
   - 只保留核心功能说明，移除所有示例

3. **强化系统提示词**
   - 在系统提示词开头添加最核心的规则
   - 使用更明确的禁止性语言

4. **添加工具调用日志**
   - 记录每次工具选择的原因
   - 分析为什么选择错误工具

## 总结

通过简化工具描述和系统提示词，我们已经：
- ✅ 将 multi_terminal 描述长度从 >1000 字符减少到 472 字符
- ✅ 将 terminal_command 描述长度从 >900 字符减少到 186 字符
- ✅ 添加了明确的工具调用时机说明
- ✅ 添加了工具之间的区分说明
- ✅ 优化了系统提示词，使其更清晰简洁

这些改进应该显著提高 AI 正确选择工具的能力。如果问题仍然存在，建议考虑切换到更强的模型（如 Claude）。

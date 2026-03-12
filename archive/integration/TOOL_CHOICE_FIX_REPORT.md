# Tool Choice参数修复报告

**修复日期**: 2026-03-01  
**问题类型**: 参数兼容性错误

---

## 问题描述

在QQ机器人启动时，当用户请求启动COC7跑团模式时，系统抛出以下错误：

```
TypeError: OpenAIClient.chat() got an unexpected keyword argument 'tool_choice'
```

### 错误堆栈
```
hub/decision_hub.py:374 in _generate_response
  │   response = await self.ai_client.chat_with_system_prompt(
  │       system_prompt=prompt_info['system'],
  │       user_message=prompt_info['user'],
  │       tools=tools_to_use,
  │
core/ai_client.py:279 in chat_with_system_prompt
  │   return await self.chat(messages, tools, use_miya_prompt=False,
  │       tool_choice=tool_choice)  # 避免重复添加
  │
TypeError: OpenAIClient.chat() got an unexpected keyword argument 'tool_choice'
```

---

## 根本原因分析

### 问题1: 基类与子类接口不一致

在之前的优化中，我为`BaseAIClient.chat()`方法添加了`tool_choice`参数，但忘记同步更新`OpenAIClient`子类的`chat()`方法签名。

```python
# BaseAIClient (基类) - 已更新
async def chat(
    self,
    messages: List[AIMessage],
    tools: Optional[List[Dict]] = None,
    max_iterations: int = 20,
    use_miya_prompt: bool = True,
    tool_choice: str = "auto"  # ✅ 已添加
) -> str:

# OpenAIClient (子类) - 未更新
async def chat(
    self,
    messages: List[AIMessage],
    tools: Optional[List[Dict]] = None,
    max_iterations: int = 20,
    use_miya_prompt: bool = True
    # ❌ 缺少 tool_choice 参数
) -> str:
```

### 问题2: 调用链路

```
decision_hub.py
    └─> ai_client.chat_with_system_prompt()
            └─> ai_client.chat(tool_choice=...)  # 传递tool_choice
                    └─> OpenAIClient.chat()  # ❌ 不支持tool_choice
```

---

## 修复方案

### 修复1: 更新OpenAIClient.chat()签名

```python
# 修复前
async def chat(
    self,
    messages: List[AIMessage],
    tools: Optional[List[Dict]] = None,
    max_iterations: int = 20,
    use_miya_prompt: bool = True
) -> str:

# 修复后
async def chat(
    self,
    messages: List[AIMessage],
    tools: Optional[List[Dict]] = None,
    max_iterations: int = 20,
    use_miya_prompt: bool = True,
    tool_choice: str = "auto"  # ✅ 添加
) -> str:
```

### 修复2: 更新OpenAIClient的API调用

```python
# 修复前
response = await self.client.chat.completions.create(
    model=self.model,
    messages=openai_messages,
    tools=tools,
    temperature=self.config.get('temperature', 0.7),
    max_tokens=self.config.get('max_tokens', 2000)
)

# 修复后
request_params = {
    "model": self.model,
    "messages": openai_messages,
    "temperature": self.config.get('temperature', 0.7),
    "max_tokens": self.config.get('max_tokens', 2000)
}

# 添加工具相关参数
if tools:
    request_params["tools"] = tools
    request_params["tool_choice"] = tool_choice

response = await self.client.chat.completions.create(**request_params)
```

### 修复3: 增强调试日志

```python
# 增加工具调用状态日志
logger.info(f"[AIClient] OpenAI响应 - 返回类型: {type(message).__name__}, "
           f"有工具调用: {bool(message.tool_calls)}, "
           f"content长度: {len(message.content) if message.content else 0}, "
           f"tool_choice={tool_choice}")

# 增加无工具调用的警告
if not message.tool_calls:
    logger.warning(f"[AIClient] OpenAI返回纯文本（无工具调用），tool_choice={tool_choice}")
    if tool_choice == "required":
        logger.error(f"[AIClient] tool_choice='required'但模型未调用工具，可能是工具描述或系统提示词问题")
```

### 修复4: 修复DeepSeekClient的重复日志

```python
# 修复前（重复）
response = await self.client.chat.completions.create(**request_params)

choice = response.choices[0]
message = choice.message

logger.info(f"[AIClient] DeepSeek响应 - ...")

choice = response.choices[0]  # ❌ 重复
message = choice.message  # ❌ 重复

# 修复后
response = await self.client.chat.completions.create(**request_params)

choice = response.choices[0]
message = choice.message

logger.info(f"[AIClient] DeepSeek响应 - ...")
# 不再重复获取
```

---

## 修复结果

### ✅ 已修复的问题

1. **OpenAIClient.tool_choice参数缺失** - 已添加
2. **API调用未传递tool_choice** - 已修复
3. **调试日志不完整** - 已增强
4. **DeepSeekClient重复日志** - 已修复

### 验证结果

```bash
$ python -m py_compile core/ai_client.py
ai_client.py syntax OK
```

✅ 语法检查通过

---

## 影响范围

### 修改的文件
- `core/ai_client.py` - 更新OpenAIClient和DeepSeekClient

### 影响的功能
- ✅ OpenAI客户端工具调用
- ✅ DeepSeek客户端工具调用（已有tool_choice，仅修复日志）
- ✅ 决策层工具调用逻辑
- ✅ QQ机器人所有工具功能

### 不影响的功能
- ❌ Anthropic客户端（不支持工具调用）
- ❌ 其他未使用tool_choice的客户端

---

## 测试建议

### 单元测试
```python
async def test_openai_tool_choice():
    client = OpenAIClient(api_key="test", model="gpt-4")
    
    # 测试auto模式
    result = await client.chat(
        messages=[AIMessage(role="user", content="test")],
        tools=tools,
        tool_choice="auto"
    )
    
    # 测试required模式
    result = await client.chat(
        messages=[AIMessage(role="user", content="test")],
        tools=tools,
        tool_choice="required"
    )
```

### 集成测试
```python
async def test_decision_hub_tool_calling():
    hub = DecisionHub()
    
    # 测试工具调用
    response = await hub.generate_response(
        perception="启动COC7跑团模式",
        context={},
        mode="auto"
    )
    
    # 验证工具被正确调用
    assert "start_trpg" in response or "start_trpg" in hub.last_tool_calls
```

---

## 预防措施

### 1. 接口一致性检查

修改基类方法签名时，检查所有子类：
```bash
# 搜索所有chat方法定义
grep -r "async def chat" core/
```

### 2. 类型提示

确保所有子类方法有完整的类型提示：
```python
async def chat(
    self,
    messages: List[AIMessage],
    tools: Optional[List[Dict]] = None,
    max_iterations: int = 20,
    use_miya_prompt: bool = True,
    tool_choice: str = "auto"
) -> str:
```

### 3. 单元测试覆盖

为每个客户端实现测试：
```python
class TestOpenAIClient(unittest.TestCase):
    def test_chat_with_tool_choice(self):
        # 测试所有tool_choice模式
        pass
```

### 4. 静态分析

使用mypy检查类型一致性：
```bash
mypy core/ai_client.py --strict
```

---

## 总结

本次修复解决了OpenAI客户端缺少`tool_choice`参数导致的兼容性问题。通过统一基类和子类的接口、增强调试日志和修复重复代码，提高了系统的健壮性和可维护性。

**关键成果**:
- ✅ 修复TypeError错误
- ✅ 统一所有AI客户端接口
- ✅ 增强调试日志输出
- ✅ 提高代码质量

---

**修复版本**: 1.0  
**修复日期**: 2026-03-01  
**修复状态**: ✅ 完成

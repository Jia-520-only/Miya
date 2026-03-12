# 游戏模式智能性问题分析与解决方案

## 问题分析

### 当前问题
1. **无法记住上下文** - AI重复询问相同信息（如威廉的QQ号）
2. **过度依赖工具** - 总是调用查询工具而不是直接进行对话
3. **对话历史缺失** - 每次请求都是独立的，没有历史记录
4. **提示词模板未渲染** - Jinja2模板语法没有被正确处理

### 根本原因

#### 1. 提示词模板渲染问题
**问题位置**：`core/prompt_manager.py:225-234`

**问题描述**：
- 游戏模式提示词（`trpg_kp.txt`、`tavern_miya.txt`）使用Jinja2模板语法
- 但 `prompt_manager.py` 只做简单的字符串替换，不支持 `{% if %}` 等Jinja2语法
- 导致游戏记忆信息（`game_memory`）无法正确插入到提示词中

**已修复**：
```python
# 添加了Jinja2模板支持
from jinja2 import Template

# 修改了占位符替换逻辑，支持Jinja2模板渲染
if '{%' in system_prompt or '{{' in system_prompt:
    template = Template(system_prompt)
    system_prompt = template.render(**additional_context)
```

#### 2. 对话历史缺失问题
**问题位置**：
- `core/ai_client.py:195-198` - `chat_with_system_prompt` 方法
- `hub/decision_hub.py` - 调用AI客户端时没有传递历史消息

**问题描述**：
```python
# 每次都创建新的消息列表，没有历史
messages = [
    AIMessage(role="system", content=system_prompt),
    AIMessage(role="user", content=user_message)  # 只有当前消息
]
```

这导致AI无法记住之前的对话内容。

#### 3. 游戏模式对话管理缺失
**问题**：
- 游戏模式没有维护独立的对话历史
- 无法区分游戏内对话和普通对话
- 存档时只保存游戏状态，不保存对话历史

## 解决方案

### 方案1：修复对话历史传递（推荐）

#### 实施步骤

1. **修改 `ai_client.py` 添加历史消息参数**

```python
# 在 chat_with_system_prompt 中添加 history 参数
async def chat_with_system_prompt(
    self,
    system_prompt: str,
    user_message: str,
    tools: Optional[List[Dict]] = None,
    use_miya_prompt: bool = True,
    history: Optional[List[AIMessage]] = None  # 新增
) -> str:
    """
    使用系统提示词聊天
    
    Args:
        history: 历史消息列表（可选）
    """
    # 构建完整消息列表
    messages = [AIMessage(role="system", content=system_prompt)]
    
    # 添加历史消息
    if history:
        messages.extend(history)
    
    # 添加当前用户消息
    messages.append(AIMessage(role="user", content=user_message))
    
    return await self.chat(messages, tools, use_miya_prompt=False)
```

2. **修改 `decision_hub.py` 传递历史消息**

在 `_generate_response` 方法中：
```python
# 获取游戏模式的对话历史
if game_mode and game_mode_manager:
    game_memory_context = game_mode_manager.load_game_memory(chat_id)
    
    # 获取游戏对话历史
    game_history = game_mode_manager.get_game_history(chat_id)
    
    # 传递给AI客户端
    response = await self.ai_client.chat_with_system_prompt(
        system_prompt=prompt_info['system'],
        user_message=prompt_info['user'],
        tools=tools_to_use,
        use_miya_prompt=True,
        history=game_history  # 新增
    )
```

3. **在 `mode_manager.py` 中添加对话历史管理**

```python
def get_game_history(self, chat_id: str, limit: int = 10) -> List[AIMessage]:
    """
    获取游戏对话历史
    
    Args:
        chat_id: 聊天ID
        limit: 获取消息数量
    
    Returns:
        历史消息列表
    """
    mode = self.get_mode(chat_id)
    if mode and mode.game_id:
        return self.game_memory_manager.get_game_history(
            mode.game_id, 
            limit
        )
    return []
```

4. **在 `game_memory_manager.py` 中添加对话历史存储**

```python
def add_game_message(
    self, 
    game_id: str, 
    role: str, 
    content: str
):
    """添加游戏对话消息"""
    game = self.games.get(game_id)
    if game:
        if 'messages' not in game:
            game['messages'] = []
        
        game['messages'].append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        
        # 限制历史消息数量
        if len(game['messages']) > 50:
            game['messages'] = game['messages'][-50:]
        
        self._save_game(game_id)

def get_game_history(
    self, 
    game_id: str, 
    limit: int = 10
) -> List[AIMessage]:
    """获取游戏对话历史"""
    game = self.games.get(game_id)
    if game and 'messages' in game:
        messages = game['messages'][-limit:]
        return [
            AIMessage(role=msg['role'], content=msg['content'])
            for msg in messages
        ]
    return []
```

### 方案2：优化提示词内容（辅助）

在游戏模式提示词中添加更明确的指令：

```markdown
## 重要：上下文理解

你当前处于游戏模式中，请记住：

1. **对话历史**: 系统会提供最近的对话历史，请基于历史继续对话
2. **避免重复**: 如果信息已经在历史中提到，不要重复询问
3. **自然对话**: 优先进行角色扮演和对话，减少不必要的工具调用
4. **智能推断**: 从上下文中推断信息，而不是总是要求用户明确提供

## 游戏状态记忆
{% if game_memory %}
- 游戏ID: {{ game_memory.game_id }}
- 存档名称: {{ game_memory.save_name }}
- 角色卡数量: {{ game_memory.characters|length }}
- 故事进度: {{ game_memory.story_progress }}
{% endif %}
```

### 方案3：改进工具调用策略

在提示词中添加工具调用优先级说明：

```markdown
## 工具调用优先级

请按以下优先级处理：

1. **高优先级（角色扮演）**: 直接进行对话和剧情描述
2. **中优先级（游戏操作）**: 骰子检定、技能检查等
3. **低优先级（信息查询）**: 查询角色卡、存档等

**重要原则**:
- 不要在对话中频繁查询角色卡
- 如果信息已知，不要重复查询
- 优先推进剧情而不是收集信息
```

## 实施建议

### 立即可实施（已完成）
1. ✅ 修复Jinja2模板渲染问题
2. ✅ 添加游戏存档工具到工具白名单

### 短期实施（推荐）
1. 添加对话历史管理功能
2. 修改AI客户端支持历史消息传递
3. 优化游戏模式提示词内容

### 长期优化
1. 实现游戏状态自动持久化
2. 添加游戏进度可视化
3. 支持多玩家协作模式

## 测试验证

修复后需要测试的场景：

1. **上下文记忆测试**
   - 创建角色"威廉"
   - 对话中再次提到"威廉"
   - 验证AI不会重复查询

2. **连续对话测试**
   - 开始跑团游戏
   - 进行多轮对话
   - 验证AI记住剧情进度

3. **工具调用优化**
   - 进行游戏对话
   - 观察工具调用频率
   - 验证不必要的查询减少

## 总结

游戏模式智能性问题的核心是**对话历史缺失**。通过修复Jinja2模板渲染和添加对话历史管理，可以显著提升AI的游戏体验。

关键点：
1. ✅ 已修复：Jinja2模板渲染
2. ⏳ 待实施：对话历史管理
3. ⏳ 待优化：提示词内容和工具调用策略

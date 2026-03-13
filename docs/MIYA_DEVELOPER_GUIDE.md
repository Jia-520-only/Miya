# 弥娅(MIYA)系统深度解析与开发指南

## 目录
1. [系统认知篇 - 理解系统架构](#1-系统认知篇---理解系统架构)
2. [核心代码篇 - 逐行解析关键代码](#2-核心代码篇---逐行解析关键代码)
3. [改造篇 - 如何修改系统](#3-改造篇---如何修改系统)
4. [拓展篇 - 添加新功能](#4-拓展篇---添加新功能)
5. [实战篇 - 完整示例](#5-实战篇---完整示例)

---

# 第一部分：系统认知篇 - 理解系统架构

## 1.1 整体架构鸟瞰

弥娅系统就像一个"大脑"，有以下组成部分：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           用户层（你）                                   │
│    终端输入 ←→ Web界面 ←→ QQ消息 ←→ 桌面应用                          │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         M-Link 消息路由层                               │
│     (就像大脑的神经，把用户说的话传给正确的处理部门)                       │
│     - 消息分发、队列管理、协议转换                                        │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
┌───────────────┐        ┌───────────────┐        ┌───────────────┐
│   感知层       │        │   决策层       │        │   执行层       │
│  Perceive    │        │    Hub        │        │   ToolNet    │
│              │        │               │        │              │
│ - 听/看输入  │        │ - 理解意图    │        │ - 执行命令    │
│ - 注意力分配 │        │ - 决定回复    │        │ - 调用工具    │
│ - 内容分类   │        │ - 情感处理    │        │ - 返回结果    │
└───────────────┘        └───────┬───────┘        └───────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
┌───────────────┐        ┌───────────────┐        ┌───────────────┐
│   记忆层       │        │   核心层       │        │   演化层       │
│   Memory     │        │    Core        │        │   Evolve     │
│              │        │               │        │              │
│ - 短期记忆   │        │ - 人格设定    │        │ - 自我学习   │
│ - 长期记忆   │        │ - 伦理规范    │        │ - 性格进化   │
│ - 知识图谱   │        │ - AI模型调用  │        │ - 问题修复   │
└───────────────┘        └───────────────┘        └───────────────┘
```

## 1.2 核心模块功能一览

| 模块 | 目录 | 功能 | 类比 |
|------|------|------|------|
| **core** | `core/` | 灵魂内核：人格、伦理、AI客户端 | 大脑皮层 |
| **hub** | `hub/` | 认知中枢：记忆、情感、决策 | 丘脑 |
| **memory** | `memory/` | 记忆存储：短期/向量/图谱 | 海马体 |
| **webnet** | `webnet/` | 多平台接入：QQ/Web/Desktop | 神经 |
| **tools** | `tools/` | 工具集：搜索、终端、分析 | 手和脚 |
| **mlink** | `mlink/` | 消息通信：路由、队列 | 神经纤维 |
| **perceive** | `perceive/` | 感知处理：注意力、分类 | 感觉器官 |
| **evolve** | `evolve/` | 演化学习：自我优化 | 学习能力 |

## 1.3 启动流程全解析

当你运行 `python run/main.py` 时，系统按以下顺序启动：

```python
# ============================================================
# run/main.py - 主程序入口
# ============================================================

# 第1步：系统环境检测
system_detector = get_system_detector()  # 检测操作系统、Python版本等

# 第2步：核心层初始化（灵魂）
personality = Personality()      # 加载人格设定
ethics = Ethics()               # 加载伦理规范
identity = Identity()            # 加载身份信息
arbitrator = Arbitrator(...)    # 决策仲裁器
entropy = Entropy()             # 熵值系统
prompt_manager = PromptManager() # 提示词管理器

# 第3步：中枢层初始化（认知）
memory_emotion = MemoryEmotion()     # 情感记忆
memory_engine = MemoryEngine()       # 记忆引擎
emotion = Emotion()                  # 情绪系统
decision = Decision(...)             # 决策系统
scheduler = Scheduler()              # 任务调度

# 第4步：网络层初始化（接入）
mlink = MLinkCore(...)              # 消息核心
memory_net = MemoryNet(...)         # 记忆子网
tool_subnet = ToolNet(...)          # 工具子网
auth_subnet = AuthNet(...)          # 鉴权子网

# 第5步：AI客户端初始化
ai_client = create_ai_client()     # 创建AI客户端
multi_model_manager = MultiModelManager()  # 多模型管理

# 第6步：终端系统初始化
terminal_orchestrator = IntelligentTerminalOrchestrator()  # 终端编排

# 第7步：API服务器启动
web_api = create_web_api()          # Web API服务
# 服务器运行在 http://0.0.0.0:8000

# 第8步：进入交互循环
while True:
    user_input = input("你: ")      # 等待用户输入
    response = miya.process(user_input)  # 处理并回复
```

---

# 第二部分：核心代码篇 - 逐行解析关键代码

## 2.1 决策核心 - decision_hub.py

这是系统最大的文件（65KB），负责处理所有输入并生成回复。

### 核心流程图

```
用户消息 ──► 权限检查 ──► 历史获取 ──► AI生成 ──► 记忆存储 ──► 返回回复
                │            │            │           │
                ▼            ▼            ▼           ▼
           是否被允许?   上下文    调用大模型    保存到Redis
```

### 关键代码解析

```python
# hub/decision_hub.py - 第200-250行

class DecisionHub:
    """决策中心 - 处理所有跨平台输入"""
    
    async def process_perception_cross_platform(self, message):
        """
        处理感知输入（跨平台统一入口）
        
        这是系统的"总调度员"，所有类型的输入都会经过这里
        """
        # ====== 第1步：提取信息 ======
        content = message.get('content', '')      # 用户说了什么
        user_id = message.get('user_id', 'unknown')  # 谁说的
        platform = message.get('platform', 'terminal') # 从哪来的
        sender_name = message.get('sender_name', '用户')  # 用户名
        
        # ====== 第2步：权限检查 ======
        # 就像安检门，检查用户有没有权限使用系统
        if not check_permission(user_id, 'api.access'):
            return "抱歉，您没有权限使用此功能。"
        
        # ====== 第3步：获取对话历史 ======
        # 就像翻阅之前的聊天记录，了解上下文
        session_id = f"{platform}_{user_id}"  # 拼出会话ID，如 "terminal_佳"
        history = await self._get_conversation_context(session_id)
        
        # ====== 第4步：构建提示词 ======
        # 把所有信息打包成AI能理解的格式
        prompt = self.prompt_manager.build_full_prompt(
            user_input=content,
            memory_context=history,  # 加入历史上下文
            additional_context={
                'platform': platform,  # 告诉AI是什么平台
                'user_id': user_id,
                'sender_name': sender_name,
            }
        )
        
        # ====== 第5步：调用AI ======
        # 真正的AI生成环节！
        response = await self.ai_client.chat_with_system_prompt(
            system_prompt=prompt['system'],  # 系统提示词（人格设定）
            user_message=prompt['user']       # 用户的问题
        )
        
        # ====== 第6步：存储记忆 ======
        # 重要！把这次对话存到记忆系统
        await self._store_unified_memory(
            content=content,
            response=response,
            user_id=user_id,
            platform=platform
        )
        
        # ====== 第7步：返回结果 ======
        return response
```

## 2.2 记忆系统 - memory_engine.py

记忆系统有四层，每层负责不同类型的数据：

```python
# memory/memory_engine.py - 记忆系统核心

class MemoryEngine:
    """
    四层记忆架构
    
    Layer 1: Redis (短期/活跃记忆)
             - 快速的、临时的
             - 如：当前对话内容
             
    Layer 2: Milvus (向量记忆)
             - 语义相似度搜索
             - 如：曾经讨论过类似的话题
             
    Layer 3: Neo4j (知识图谱)
             - 关系网络
             - 如：用户A认识用户B
             
    Layer 4: JSON文件 (持久记忆)
             - 手动保存的重要信息
             - 如：用户的个人设置
    """
    
    async def store_memory(self, content, memory_type='tide'):
        """
        存储记忆
        
        参数:
            content: 要存储的内容
            memory_type: 记忆类型
                - 'tide': 潮汐记忆 → Redis
                - 'vector': 向量记忆 → Milvus
                - 'graph': 知识图谱 → Neo4j
                - 'manual': 手动记忆 → JSON文件
        """
        if memory_type == 'tide':
            # 存到Redis（短期记忆）
            await self.redis.set(f"tide:{content_hash}", content)
            
        elif memory_type == 'vector':
            # 存到Milvus（向量记忆）
            # 先把文字转成向量
            vector = self.embedding_model.encode(content)
            await self.milvus.insert(vector, content)
            
        elif memory_type == 'graph':
            # 存到Neo4j（图谱）
            await self.neo4j.create_entity(content)
            
        elif memory_type == 'manual':
            # 存到JSON文件
            with open('data/memory/manual.json', 'a') as f:
                f.write(json.dumps(content))
    
    async def retrieve_memory(self, query, memory_type='all'):
        """
        检索记忆
        """
        results = []
        
        if memory_type in ['tide', 'all']:
            # 从Redis查询
            tide_result = await self.redis.get(f"tide:{hash(query)}")
            if tide_result:
                results.append(tide_result)
        
        if memory_type in ['vector', 'all']:
            # 从Milvus语义搜索
            query_vector = self.embedding_model.encode(query)
            vector_results = await self.milvus.search(query_vector)
            results.extend(vector_results)
        
        if memory_type in ['graph', 'all']:
            # 从Neo4j查询关系
            graph_results = await self.neo4j.find_related(query)
            results.extend(graph_results)
        
        return results
```

## 2.3 AI客户端 - ai_client.py

这是弥娅与AI模型通信的桥梁：

```python
# core/ai_client.py - AI客户端

class AIClient:
    """
    AI客户端 - 与各种大语言模型通信
    
    支持的模型：
    - OpenAI (GPT-4, GPT-3.5)
    - DeepSeek (DeepSeek Chat, DeepSeek Reasoner)
    - 硅基流动 (Qwen, Llama, GLM等)
    """
    
    def __init__(self, model_name, api_key, base_url):
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        
        # 创建HTTP会话（复用连接，提高性能）
        self.session = aiohttp.ClientSession()
    
    async def chat_with_system_prompt(self, system_prompt, user_message, tools=None):
        """
        发送消息给AI并获取回复
        
        参数:
            system_prompt: 系统提示词（人格设定）
            user_message: 用户的问题
            tools: 工具列表（可选，让AI能调用函数）
            
        返回:
            AI的回复文本
        """
        # 构建消息格式
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # 构建请求
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.7,  # 创造性程度 0-2
            "max_tokens": 2000,  # 最大回复长度
        }
        
        # 如果有工具，添加工具定义
        if tools:
            payload["tools"] = tools
        
        # 发送请求
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with self.session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers
        ) as response:
            result = await response.json()
            
            # 解析回复
            if "choices" in result:
                return result["choices"][0]["message"]["content"]
            else:
                return f"错误: {result.get('error', '未知错误')}"
```

## 2.4 工具系统 - tool_subnet.py

工具系统让AI能够执行实际操作：

```python
# webnet/TerminalNet/tools/terminal_tool.py - 终端工具示例

class TerminalTool:
    """
    终端工具 - 在终端执行命令
    
    这个工具让AI能够在服务器上执行真实的命令
    """
    
    def execute(self, command, user_confirm=False):
        """
        执行终端命令
        
        例如：
        - execute("ls") → 列出文件
        - execute("dir") → Windows列出文件
        - execute("python test.py") → 运行Python脚本
        """
        # 检查是否需要用户确认（危险命令）
        dangerous_patterns = ['rm -rf', 'del /f', 'format', 'shutdown']
        if any(p in command for p in dangerous_patterns):
            if not user_confirm:
                self.pending_command = command
                return {"status": "pending_confirm", "message": "请确认是否执行危险命令"}
        
        # 执行命令
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "status": "success",
                "output": result.stdout,
                "error": result.stderr
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
```

---

# 第三部分：改造篇 - 如何修改系统

## 3.1 修改人格设定

**目标**：让弥娅的性格发生改变

**文件**：`core/personality.py`

```python
# 修改前
class Personality:
    def __init__(self):
        self.traits = {
            'warmth': 0.8,      # 温暖度 0-1
            'logic': 0.6,       # 逻辑性 0-1
            'creativity': 0.7   # 创造性 0-1
        }
        
        self.response_templates = {
            'greeting': "你好！有什么我可以帮助你的吗？",
            'farewell': "再见！很高兴和你聊天！"
        }

# 修改后 - 例如让弥娅更活泼
class Personality:
    def __init__(self):
        self.traits = {
            'warmth': 0.95,     # 更温暖！
            'logic': 0.5,       
            'creativity': 0.9,  # 更有创意！
            'playfulness': 0.8  # 新增：活泼度
        }
        
        self.response_templates = {
            'greeting': "嘿！是你呀！开心 今天过得怎么样？",
            'farewell": "拜拜～有空再来找我玩呀！"
        }
```

## 3.2 修改回答风格

**目标**：改变弥娅说话的方式

**文件**：`prompts/default.txt`

```
# 这是系统提示词，决定了弥娅的行为方式

你是一个叫"弥娅"的AI助手。

回答风格要求：
- 使用简洁的语言
- 适当使用emoji 😊
- 保持友好亲切的语气
- 遇到问题时给出实用的建议

你的人格特质：
- 温暖友好
- 逻辑清晰
- 富有创造力
```

## 3.3 添加新的回复模板

**目标**：让弥娅对特定问题有固定回复

**文件**：`hub/decision_hub.py`

```python
# 在 process_perception_cross_platform 方法开头添加

async def process_perception_cross_platform(self, message):
    content = message.get('content', '')
    
    # ======== 添加：快捷回复 ========
    quick_responses = {
        '你是谁': '我叫弥娅，是一个AI助手！',
        '几点了': lambda: f'现在时间是 {datetime.now().strftime("%H:%M")}',
        '天气怎么样': '我无法直接查询天气，但你可以告诉我你在哪个城市～',
    }
    
    # 检查是否有匹配
    for keyword, response in quick_responses.items():
        if keyword in content:
            if callable(response):
                return response()
            return response
    # ======== 快捷回复结束 ========
    
    # ... 原有的处理逻辑继续
```

---

# 第四部分：拓展篇 - 添加新功能

## 4.1 添加新工具（示例：计算器）

### 步骤1：创建工具文件

```python
# tools/calculator.py

class CalculatorTool:
    """
    计算器工具 - 进行数学运算
    """
    
    def get_schema(self):
        """返回工具的定义（让AI知道怎么使用）"""
        return {
            "name": "calculator",
            "description": "进行数学计算，支持加减乘除、幂运算等",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 2+3*4 或 10/2"
                    }
                },
                "required": ["expression"]
            }
        }
    
    def execute(self, expression):
        """执行计算"""
        try:
            # 注意：实际使用应该用安全的eval方式
            # 这里仅作示例
            allowed_chars = set('0123456789+-*/.() ')
            if not all(c in allowed_chars for c in expression):
                return {"error": "表达式包含非法字符"}
            
            result = eval(expression)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}
```

### 步骤2：注册工具

```python
# webnet/ToolNet/registry.py

def get_tools_schema(self):
    # ... 现有工具 ...
    
    # 添加计算器
    tools['calculator'] = {
        "name": "calculator",
        "description": "进行数学计算",
        "parameters": {...}
    }
    
    return tools
```

### 步骤3：AI就能使用了

```
用户: 帮我算一下 123 * 456
AI: (调用calculator工具)
    结果: 56088
```

## 4.2 添加新平台接入（示例：微信）

### 步骤1：创建平台适配器

```python
# hub/platform_adapters.py

class WeChatAdapter:
    """微信消息适配器"""
    
    def to_message(self, raw_data):
        """
        把微信的原始消息转换成统一格式
        """
        return {
            'content': raw_data.get('text', ''),
            'user_id': f"wechat_{raw_data.get('from_user')}",
            'platform': 'wechat',
            'sender_name': raw_data.get('from_nickname', '微信用户')
        }
    
    def from_message(self, message):
        """
        把统一格式的消息转成微信格式
        """
        return {
            'msgtype': 'text',
            'text': {
                'content': message['content']
            }
        }
```

### 步骤2：注册适配器

```python
# hub/platform_adapters.py

_adapters = {
    'terminal': TerminalAdapter(),
    'qq': QQAdapter(),
    'web': WebAdapter(),
    'desktop': DesktopAdapter(),
    'wechat': WeChatAdapter(),  # 添加微信
}

def get_adapter(platform):
    return _adapters.get(platform, TerminalAdapter())
```

## 4.3 添加新记忆类型（示例：图片记忆）

```python
# memory/image_memory.py

class ImageMemory:
    """图片记忆 - 存储和检索图片"""
    
    def __init__(self):
        self.storage_path = 'data/memory/images/'
        os.makedirs(self.storage_path, exist_ok=True)
    
    async def store_image(self, image_data, description):
        """存储图片"""
        # 生成唯一ID
        image_id = hashlib.md5(image_data).hexdigest()
        
        # 保存图片文件
        image_path = f"{self.storage_path}{image_id}.png"
        with open(image_path, 'wb') as f:
            f.write(image_data)
        
        # 保存描述到数据库
        await self.redis.set(
            f"image_desc:{image_id}",
            json.dumps({'description': description, 'path': image_path})
        )
        
        return image_id
    
    async def search_by_description(self, query):
        """用文字描述搜索图片"""
        # 这里需要用CLIP等模型来做图文匹配
        # 简化版：搜索描述文字
        keys = await self.redis.keys("image_desc:*")
        results = []
        
        for key in keys:
            desc_data = await self.redis.get(key)
            if query.lower() in desc_data.lower():
                results.append(json.loads(desc_data))
        
        return results
```

---

# 第五部分：实战篇 - 完整示例

## 5.1 完整示例：添加"提醒"功能

让我们完整地添加一个"定时提醒"功能：

### 第1步：创建提醒工具

```python
# tools/reminder.py

import asyncio
from datetime import datetime, timedelta

class ReminderTool:
    """提醒工具 - 设置定时提醒"""
    
    def __init__(self):
        self.scheduled_tasks = {}  # 存储定时任务
    
    def get_schema(self):
        return {
            "name": "set_reminder",
            "description": "设置定时提醒",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "提醒内容"
                    },
                    "minutes": {
                        "type": "integer", 
                        "description": "多少分钟后提醒"
                    }
                },
                "required": ["message", "minutes"]
            }
        }
    
    async def execute(self, message, minutes):
        """执行提醒"""
        # 计算提醒时间
        remind_time = datetime.now() + timedelta(minutes=minutes)
        
        # 创建异步任务
        task = asyncio.create_task(
            self._do_remind(message, remind_time)
        )
        
        self.scheduled_tasks[message] = task
        
        return {
            "success": True,
            "message": f"好的！{minutes}分钟后我会提醒你：{message}",
            "remind_at": remind_time.strftime("%H:%M")
        }
    
    async def _do_remind(self, message, remind_time):
        """执行实际的提醒"""
        # 等待到提醒时间
        wait_seconds = (remind_time - datetime.now()).total_seconds()
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        
        # 提醒时间到！
        # 这里应该通过某种方式通知用户
        return f"⏰ 提醒：{message}"
```

### 第2步：集成到系统

```python
# 在初始化时创建提醒工具
# run/main.py 或 core/ai_client.py

self.reminder_tool = ReminderTool()

# 在工具注册时添加
def get_tools_schema(self):
    return {
        "set_reminder": self.reminder_tool.get_schema(),
        # ... 其他工具
    }
```

### 第3步：使用方式

```
用户: 帮我设置一个10分钟后的提醒，提醒我喝水
AI: (调用set_reminder工具)
    返回: 好的！10分钟后我会提醒你：喝水
    (10分钟后，系统会提醒用户)
```

## 5.2 完整示例：自定义对话流程

如果你想完全控制对话流程：

```python
# my_custom_hub.py

from hub.decision_hub import DecisionHub

class MyCustomHub(DecisionHub):
    """自定义决策中心"""
    
    async def process_perception_cross_platform(self, message):
        """完全自定义的处理流程"""
        
        content = message.get('content', '')
        
        # ===== 自定义：关键词触发 =====
        if content.startswith('!指令'):
            return await self.handle_command(content[3:])
        
        # ===== 自定义：情感检测 =====
        emotion = self.detect_emotion(content)
        
        # ===== 根据情感调整回复 =====
        if emotion == 'sad':
            message['emotion_context'] = '用户似乎心情不好，需要安慰'
        elif emotion == 'happy':
            message['emotion_context'] = '用户心情不错，可以活泼一些'
        
        # ===== 调用父类处理 =====
        return await super().process_perception_cross_platform(message)
    
    async def handle_command(self, command):
        """处理特殊命令"""
        commands = {
            '状态': lambda: self.get_system_status(),
            '帮助': lambda: self.get_help(),
            '统计': lambda: self.get_statistics(),
        }
        
        cmd = command.strip()
        if cmd in commands:
            return commands[cmd]()
        
        return f"未知命令: {command}"
    
    def detect_emotion(self, text):
        """简单的情感检测"""
        happy_words = ['开心', '高兴', '快乐', '棒', '好']
        sad_words = ['难过', '伤心', '郁闷', '烦', '不爽']
        
        for word in happy_words:
            if word in text:
                return 'happy'
        
        for word in sad_words:
            if word in text:
                return 'sad'
        
        return 'neutral'
```

---

# 附录

## A. 常用命令

```bash
# 启动系统
python run/main.py

# 启动桌面端
python run/desktop_main.py

# 启动Web端
python run/web_main.py

# 检查依赖
python test_imports.py

# 查看日志
tail -f logs/miya.log
```

## B. 调试技巧

```python
# 在代码中添加打印语句
print(f"调试信息: {variable}")

# 使用日志
import logging
logger = logging.getLogger(__name__)
logger.debug(f"调试: {variable}")
logger.info(f"信息: {variable}")
logger.warning(f"警告: {variable}")
```

## C. 重要文件索引

| 功能 | 文件 |
|------|------|
| 主入口 | `run/main.py` |
| 决策中心 | `hub/decision_hub.py` |
| 记忆系统 | `memory/memory_engine.py` |
| AI客户端 | `core/ai_client.py` |
| 人格设定 | `core/personality.py` |
| 提示词 | `prompts/default.txt` |
| 工具注册 | `webnet/ToolNet/registry.py` |
| 终端工具 | `tools/terminal.py` |
| 配置 | `config/.env` |

---

*文档版本: 2026-03-13*
*更多内容请参考: docs/MIYA_REBUILD_GUIDE.md*

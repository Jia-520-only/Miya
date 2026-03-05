# 弥娅跑团主持人和酒馆故事系统设计文档

> 设计时间：2026-03-01
> 设计目的：为弥娅添加 TRPG 跑团主持人和酒馆故事功能

---

## 🎯 系统定位

### 双模式设计

弥娅将提供两种互补的娱乐模式：

1. **酒馆模式 (Tavern Mode)**
   - 自由聊天、角色扮演
   - 故事生成、续写
   - 情绪/语气控制
   - 长期记忆玩家偏好

2. **跑团模式 (TRPG Mode)**
   - 投骰、规则判定
   - 角色卡管理
   - 剧情推进与场景描述
   - 主持人（KP）功能

### 核心理念

```
弥娅 = 酒馆老板娘 + 经验丰富的KP（主持人）
        ↓
    统一的数字生命伴侣
```

---

## 🏗️ 架构设计（符合弥娅蛛网式架构）

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    用户界面层                             │
│  ┌─────────────┐  ┌─────────────┐                    │
│  │  PC UI      │  │  QQ Net     │                    │
│  └─────────────┘  └─────────────┘                    │
│         │                 │                               │
│         └────────┬────────┘                               │
│                  │ M-Link 五流传输                      │
└──────────────────┼─────────────────────────────────────────┘
                   │
┌──────────────────┼─────────────────────────────────────────┐
│                   │         认知核心层                    │
├──────────────────┼─────────────────────────────────────────┤
│  ┌─────────────┐ │ ┌─────────────┐ ┌─────────────┐  │
│  │  Hub中枢    │─┼─│  情绪系统  │ │  人格系统  │  │
│  │ • Scheduler │ │ │  • 染色    │ │  • 人设    │  │
│  └─────────────┘ │ └─────────────┘ └─────────────┘  │
│         │       │                                    │
│         └───────┼────────────────────────────────────┐   │
│                 │                                 │   │
┌─────────────────┼─────────────────────────────────┼───┤
│                 │          子网层                 │   │
├─────────────────┼─────────────────────────────────┼───┤
│  ┌────────────┐ │ ┌────────────┐  ┌─────────┐ │   │
│  │TavernNet  │ │ │  TRPGNet   │  │MemoryNet│ │   │
│  │酒馆子网    │ │ │ 跑团子网   │  │记忆子网 │ │   │
│  │            │ │ │            │  │         │ │   │
│  │• 对话     │ │ │• 投骰     │  │• 对话   │ │   │
│  │• 故事     │ │ │• 角色卡   │  │• 角色   │ │   │
│  │• 角色     │ │ │• 场景     │  │• 剧情   │ │   │
│  │• 记忆     │ │ │• 裁决     │  │• 历史   │ │   │
│  └────────────┘ │ └────────────┘  └─────────┘ │   │
│                  └───────────────────────────────┘   │
└───────────────────────────────────────────────────────────┘
```

### 目录结构设计

```
webnet/
├── EntertainmentNet/          # 娱乐子网（现有）
│   ├── tavern/                # 酒馆子网 ✨ 新增
│   │   ├── __init__.py
│   │   ├── subnet.py         # TavernNet 子网基类
│   │   ├── tools/            # 酒馆工具
│   │   │   ├── __init__.py
│   │   │   ├── start_tavern.py    # 启动酒馆模式
│   │   │   ├── tavern_chat.py     # 酒馆对话
│   │   │   ├── generate_story.py  # 生成故事
│   │   │   ├── continue_story.py  # 续写故事
│   │   │   ├── set_mood.py       # 设置情绪
│   │   │   └── create_character.py # 创建角色
│   │   ├── memory.py         # 酒馆记忆管理
│   │   └── character.py      # 角色管理
│   │
│   └── trpg/                 # 跑团子网 ✨ 新增
│       ├── __init__.py
│       ├── subnet.py         # TRPGNet 子网基类
│       ├── tools/            # 跑团工具
│       │   ├── __init__.py
│       │   ├── start_trpg.py      # 启动跑团模式
│       │   ├── roll_dice.py       # 投骰
│       │   ├── skill_check.py     # 技能检定
│       │   ├── create_pc.py       # 创建角色卡
│       │   ├── show_pc.py         # 查看角色卡
│       │   ├── update_pc.py       # 更新属性
│       │   ├── set_scene.py       # 设置场景
│       │   ├── npc_interact.py    # NPC互动
│       │   ├── kp_command.py      # KP指令
│       │   └── roll_secret.py     # 暗骰
│       ├── dice.py           # 骰子系统核心
│       ├── character.py      # 角色卡系统
│       ├── scene.py          # 场景管理
│       ├── rules/           # 规则模块
│       │   ├── __init__.py
│       │   ├── coc7.py      # COC 7版规则
│       │   ├── dnd5e.py     # D&D 5E规则
│       │   └── wod.py       # WoD规则
│       └── prompt.py         # 跑团提示词
│
└── MemoryNet/                # 记忆子网（现有）
    └── tavern_trpg/          # 酒馆/跑团专用记忆 ✨ 新增
        ├── __init__.py
        ├── conversation.py   # 对话记忆
        ├── character_memory.py # 角色记忆
        └── story_memory.py  # 故事记忆
```

---

## 🎲 TRPG 跑团系统设计

### 1. 投骰系统 (Dice System)

#### 骰子格式支持

```python
# 支持的骰子表达式
"1d100"    # 一个百面骰
"3d6"       # 三个六面骰
"2d10+5"    # 两个十面骰加5
"4d6-2"     # 四个六面骰减2
"1d20+3d4"   # 混合投掷
```

#### COC 7 版规则判定

```python
# d100 判定规则
def check_coc7(roll_value: int, skill_value: int) -> dict:
    """COC7 规则判定"""
    if roll_value == 1:
        return {"result": "大成功", "type": "critical_success"}
    elif roll_value == 100:
        return {"result": "大失败", "type": "critical_failure"}
    elif roll_value <= skill_value // 5:
        return {"result": "极难成功", "type": "extreme_success"}
    elif roll_value <= skill_value // 2:
        return {"result": "困难成功", "type": "hard_success"}
    elif roll_value <= skill_value:
        return {"result": "成功", "type": "success"}
    else:
        return {"result": "失败", "type": "failure"}
```

#### 工具接口设计

```python
class RollDice(BaseTool):
    """投骰工具"""
    
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "roll_dice",
            "description": "投掷骰子，支持格式如 3d6、2d10+5、1d100 等",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "骰子表达式，如 3d6、2d10+5、1d100"
                    },
                    "reason": {
                        "type": "string",
                        "description": "投骰原因（可选），如 '侦查检定'",
                        "default": ""
                    }
                },
                "required": ["expression"]
            }
        }
    
    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        expression = args.get("expression", "")
        reason = args.get("reason", "")
        
        # 解析并投掷骰子
        from webnet.EntertainmentNet.trpg.dice import DiceEngine
        dice = DiceEngine()
        result = dice.roll(expression)
        
        # 格式化输出
        if reason:
            return f"🎲 {reason}: {result['detail']} = **{result['total']}**"
        return f"🎲 投骰结果: {result['detail']} = **{result['total']}**"
```

### 2. 角色卡系统 (Character System)

#### 角色卡数据结构

```python
@dataclass
class CharacterCard:
    """TRPG 角色卡"""
    # 基础信息
    player_id: int          # 玩家QQ号
    character_name: str     # 角色名
    rule_system: str       # 规则系统 (coc7, dnd5e, wod)
    
    # COC 7 属性
    strength: int = 50      # 力量
    dexterity: int = 50     # 敏捷
    constitution: int = 50  # 体质
    appearance: int = 50    # 外貌
    intelligence: int = 50  # 智力
    power: int = 50         # 意志
    luck: int = 50          # 幸运
    education: int = 50     # 教育
    
    # 状态
    hp: int = 10           # 当前生命值
    hp_max: int = 10       # 最大生命值
    mp: int = 10           # 当前魔法值
    mp_max: int = 10       # 最大魔法值
    san: int = 99          # 理智值
    
    # 技能
    skills: Dict[str, int] = field(default_factory=dict)
    
    # 装备和物品
    inventory: List[str] = field(default_factory=list)
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
```

#### 角色管理工具

```python
class CreatePC(BaseTool):
    """创建角色卡工具"""
    
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "create_pc",
            "description": "创建TRPG角色卡，支持COC7、DND5E等规则系统",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "角色名称"
                    },
                    "rule_system": {
                        "type": "string",
                        "enum": ["coc7", "dnd5e", "wod"],
                        "description": "规则系统"
                    },
                    "use_random": {
                        "type": "boolean",
                        "description": "是否随机生成属性",
                        "default": True
                    }
                },
                "required": ["name", "rule_system"]
            }
        }
    
    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        name = args.get("name")
        rule_system = args.get("rule_system")
        use_random = args.get("use_random", True)
        user_id = context.user_id
        
        # 创建角色卡
        from webnet.EntertainmentNet.trpg.character import CharacterManager
        manager = CharacterManager()
        
        if use_random:
            pc = manager.create_random_pc(user_id, name, rule_system)
        else:
            pc = manager.create_empty_pc(user_id, name, rule_system)
        
        return f"✅ 角色卡创建成功！\n\n{pc.format_summary()}"
```

### 3. 场景与剧情系统 (Scene & Story System)

#### 场景管理

```python
@dataclass
class TRPGScene:
    """TRPG 场景"""
    scene_id: str
    group_id: int           # 群号
    name: str              # 场景名称
    description: str       # 场景描述
    
    # NPC 列表
    npcs: List[Dict] = field(default_factory=list)
    
    # 线索
    clues: List[str] = field(default_factory=list)
    
    # 当前状态
    phase: str = "exploration"  # exploration, combat, interaction
    
    # 元数据
    created_by: int = 0     # 创建者（KP）
    created_at: datetime = field(default_factory=datetime.now)
```

#### KP 指令工具

```python
class KPCommand(BaseTool):
    """KP 主持人指令工具"""
    
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "kp_command",
            "description": "KP 主持人指令：设置场景、NPC、线索等",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["set_scene", "add_npc", "add_clue", "next_phase", "reset"],
                        "description": "动作类型"
                    },
                    "name": {
                        "type": "string",
                        "description": "名称（场景名、NPC名等）"
                    },
                    "description": {
                        "type": "string",
                        "description": "描述内容"
                    }
                },
                "required": ["action"]
            }
        }
    
    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        action = args.get("action")
        
        from webnet.EntertainmentNet.trpg.scene import SceneManager
        manager = SceneManager()
        
        if action == "set_scene":
            name = args.get("name", "新场景")
            description = args.get("description", "...")
            scene = manager.create_scene(
                context.group_id,
                name,
                description,
                created_by=context.user_id
            )
            return f"📍 场景已设置：{scene.name}\n{scene.description}"
        
        # ... 其他动作处理
```

---

## 🍺 酒馆故事系统设计

### 1. 酒馆模式核心

#### 酒馆老板娘人设

```python
TAVERN_SYSTEM_PROMPT = """
你是一间深夜酒馆的老板娘，名叫"弥娅"。

你的性格特质：
- 温柔、耐心、善于倾听
- 总是带着淡淡的微笑
- 喜欢听客人们讲故事
- 擅长用温暖的语言安慰疲惫的灵魂
- 会根据客人的情绪调整语气

你擅长做的事情：
- 聊天：与客人进行自然、温暖的对话
- 讲故事：根据主题或开头创作短篇故事
- 续写故事：延续客人给出的故事开头
- 角色扮演：扮演酒馆老板娘与客人互动
- 记住客人：记住常客的性格、偏好、故事

对话风格：
- 简短、自然、像真人聊天
- 不说教、不啰嗦
- 带着温暖的人情味
- 适时提问，引导对话深入

语气控制（根据 mood 参数调整）：
- 温暖：亲切、关怀
- 轻松：幽默、俏皮
- 严肃：认真、专注
- 暗黑：神秘、阴郁
- 治愈：温柔、安抚

记住：你是一间有温度的深夜酒馆，不是冰冷的AI助手。
"""
```

#### 酒馆工具设计

```python
class StartTavern(BaseTool):
    """启动酒馆模式"""
    
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "start_tavern",
            "description": "启动酒馆模式，进入温暖的故事时光",
            "parameters": {
                "type": "object",
                "properties": {
                    "mood": {
                        "type": "string",
                        "enum": ["warm", "relaxed", "serious", "dark", "healing"],
                        "description": "酒馆氛围",
                        "default": "warm"
                    }
                }
            }
        }
    
    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        mood = args.get("mood", "warm")
        
        # 设置酒馆模式状态
        from webnet.EntertainmentNet.tavern.memory import TavernMemory
        memory = TavernMemory()
        memory.set_mode(context.group_id or context.user_id, "tavern")
        memory.set_mood(context.group_id or context.user_id, mood)
        
        # 生成欢迎语
        mood_names = {
            "warm": "温暖",
            "relaxed": "轻松",
            "serious": "严肃",
            "dark": "暗黑",
            "healing": "治愈"
        }
        
        return f"""🍺 **欢迎来到弥娅的深夜酒馆**

这里是一间{mood_names[mood]}的小酒馆。

我是老板娘弥娅，很高兴见到你。
想聊聊天？还是想让我讲个故事？

随便说些什么吧，我会认真倾听的～ ☕✨"""


class GenerateStory(BaseTool):
    """生成故事工具"""
    
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "generate_story",
            "description": "生成一个短篇故事，支持恐怖、温馨、奇幻等风格",
            "parameters": {
                "type": "object",
                "properties": {
                    "theme": {
                        "type": "string",
                        "description": "故事主题，如'恐怖探险'、'温馨日常'、'奇幻冒险'"
                    },
                    "style": {
                        "type": "string",
                        "enum": ["horror", "warm", "fantasy", "scifi", "romance"],
                        "description": "故事风格"
                    },
                    "length": {
                        "type": "string",
                        "enum": ["short", "medium", "long"],
                        "description": "故事长度",
                        "default": "short"
                    }
                },
                "required": ["theme"]
            }
        }
    
    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        theme = args.get("theme")
        style = args.get("style", "fantasy")
        length = args.get("length", "short")
        
        # 使用 AI 生成故事
        story_prompt = f"""
请根据以下要求创作一个{length}篇故事：

主题：{theme}
风格：{style}

要求：
1. 情节完整，有开头、发展、高潮、结尾
2. 语言生动，有画面感
3. 适合深夜酒馆的氛围
4. 300-500字左右

直接输出故事内容，不要加任何说明。
"""
        
        # 调用 AI 生成
        from core.ai_client import AIClient
        ai = AIClient()
        story = await ai.chat(story_prompt)
        
        return f"""📖 **深夜故事** 🌙

{story}

***

喜欢这个故事吗？还想听别的主题吗？
"""
```

---

## 🔄 记忆系统集成

### 双模式记忆隔离

```python
class TavernTRPGMemoryManager:
    """酒馆/跑团记忆管理器"""
    
    def __init__(self, mlink):
        self.mlink = mlink
        self.tavern_memory = TavernMemory()
        self.trpg_memory = TRPGMemory()
    
    async def store_message(self, chat_id: int, mode: str, message: dict):
        """存储消息到对应的记忆系统"""
        if mode == "tavern":
            await self.tavern_memory.add_conversation(chat_id, message)
        elif mode == "trpg":
            await self.trpg_memory.add_event(chat_id, message)
    
    async def get_context(self, chat_id: int, mode: str, limit: int = 10):
        """获取上下文"""
        if mode == "tavern":
            return await self.tavern_memory.get_recent(chat_id, limit)
        elif mode == "trpg":
            return await self.trpg_memory.get_recent_events(chat_id, limit)
        return []
```

### 角色记忆

```python
class CharacterMemory:
    """角色记忆系统"""
    
    def remember_player(self, user_id: int, traits: dict):
        """记住玩家性格特点"""
        self.memory_store.set(f"player_{user_id}_traits", traits)
    
    def get_player_traits(self, user_id: int) -> dict:
        """获取玩家性格特点"""
        return self.memory_store.get(f"player_{user_id}_traits", {})
    
    def remember_preference(self, user_id: int, preference: str):
        """记住玩家偏好"""
        self.memory_store.append(f"player_{user_id}_prefs", preference)
```

---

## 🎯 实现路线图

### Phase 1: 基础框架（Week 1）

- [x] 创建 `webnet/EntertainmentNet/tavern/` 目录结构
- [x] 创建 `webnet/EntertainmentNet/trpg/` 目录结构
- [ ] 实现 `DiceEngine` 骰子系统核心
- [ ] 实现 `CharacterManager` 角色卡管理
- [ ] 实现基础的 `RollDice` 工具

### Phase 2: 酒馆模式（Week 2）

- [ ] 实现 `StartTavern` 工具
- [ ] 实现 `TavernChat` 工具
- [ ] 实现 `GenerateStory` 工具
- [ ] 实现 `ContinueStory` 工具
- [ ] 实现 `TavernMemory` 记忆系统

### Phase 3: 跑团核心（Week 3-4）

- [ ] 实现 COC7 规则模块
- [ ] 实现 `SkillCheck` 技能检定工具
- [ ] 实现 `CreatePC` / `ShowPC` / `UpdatePC` 工具
- [ ] 实现 `SceneManager` 场景管理
- [ ] 实现 `KPCommand` 主持人工具

### Phase 4: 高级功能（Week 5-6）

- [ ] 实现暗骰/私骰功能
- [ ] 实现多规则支持（D&D 5E、WoD）
- [ ] 实现战斗系统
- [ ] 实现疯狂表、创伤表
- [ ] 实现 Web 控制面板

---

## 📝 使用示例

### 酒馆模式对话

```
用户: /tavern
弥娅: 🍺 欢迎来到弥娅的深夜酒馆

这里是一间温暖的小酒馆。

我是老板娘弥娅，很高兴见到你。
想聊聊天？还是想让我讲个故事？

随便说些什么吧，我会认真倾听的～ ☕✨

用户: 给我讲个恐怖探险的故事
弥娅: (调用 generate_story 工具)
📖 深夜故事 🌙

...（AI生成的恐怖故事）...

***

喜欢这个故事吗？还想听别的主题吗？

用户: 我想续写这个故事
弥娅: (调用 continue_story 工具)
好呀，请告诉我你想怎么续写？
```

### 跑团模式对话

```
用户: /trpg coc7
弥娅: 🎲 跑团模式已启动（COC 7版规则）

可用的指令：
- /roll 3d6         投骰
- /sc 侦查 70        技能检定
- /pc create 创建角色卡
- /pc show 查看属性
- /kp set_scene 设置场景

用户: /pc create 小明 coc7
弥娅: ✅ 角色卡创建成功！

角色：小明
力量：55  敏捷：62  体质：48
外貌：70  智力：65  意志：68
幸运：50  教育：60
HP：11    MP：11    SAN：99

用户: /sc 侦查 70
弥娅: 🎲 侦查检定 (70)
3d6 = [4, 2, 3] = 9
总检定值：70 + 9 = 79 → **成功** ✅

你在旧图书馆中仔细搜寻...
（AI生成场景描述）
```

---

## 🔧 技术细节

### 与弥娅核心的集成

```python
# 在 EntertainmentNet 子网中注册工具
from webnet.EntertainmentNet.tavern import TavernNet
from webnet.EntertainmentNet.trpg import TRPGNet

# 初始化子网
tavern_net = TavernNet(
    mlink=mlink,
    ai_client=ai_client,
    personality=personality
)

trpg_net = TRPGNet(
    mlink=mlink,
    ai_client=ai_client,
    memory_engine=memory_engine
)

# 注册到子网路由器
subnet_router.register_subnet(tavern_net)
subnet_router.register_subnet(trpg_net)
```

### 情绪与人格的影响

```python
# 酒馆模式下，情绪影响语气
def generate_tavern_response(self, user_input: str, mood: str, emotion_state: dict):
    """生成酒馆回复"""
    
    # 获取当前主导情绪
    dominant_emotion = emotion_state.get('dominant', 'calm')
    
    # 根据情绪调整系统提示词
    prompt = TAVERN_SYSTEM_PROMPT
    prompt += f"\n\n当前情绪：{dominant_emotion}"
    prompt += f"\n当前氛围：{mood}"
    
    # 调用 AI 生成回复
    response = self.ai_client.chat(prompt + f"\n用户说：{user_input}")
    
    # 情绪染色
    return self.emotion.influence_response(response)
```

---

## ✨ 设计优势

### 1. 完全符合弥娅架构

- ✅ 酒馆和跑团作为独立的子网（TavernNet、TRPGNet）
- ✅ 通过 M-Link 与其他子网通信
- ✅ 与弥娅核心（人格、情绪、记忆）深度集成
- ✅ 遵循蛛网式分布式设计

### 2. 双模式互补

- **酒馆模式**：自由聊天、故事创作，适合放松娱乐
- **跑团模式**：规则严谨、角色扮演，适合游戏互动
- 两种模式记忆隔离，避免"串戏"

### 3. AI 与规则结合

- 酒馆模式：完全由 AI 驱动（对话、故事）
- 跑团模式：AI 负责场景描述 + 规则负责判定
- 既有 AI 的灵活性，又有规则的严谨性

### 4. 可扩展性

- 支持多种 TRPG 规则（COC7、D&D 5E、WoD）
- 可以轻松添加新规则模块
- 工具化设计，便于添加新功能

---

## 📞 下一步行动

1. **确认设计** - 与你讨论此设计是否符合需求
2. **创建骨架** - 创建目录结构和基础文件
3. **实现核心** - 先实现骰系统和酒馆对话
4. **测试反馈** - 在小范围测试，根据反馈调整
5. **完善功能** - 逐步添加高级功能

---

**设计完成时间：2026-03-01**
**设计状态：✅ 待确认**
**符合架构：✅ 100% 符合弥娅框架**

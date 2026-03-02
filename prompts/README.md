# 弥娅提示词管理器使用指南

## 📦 已集成到核心模块

提示词管理器（`PromptManager`）已经作为核心模块的一部分集成到弥娅系统中。

---

## 🔧 核心位置

**模块路径**: `core/prompt_manager.py`

**导入方式**:
```python
from core import PromptManager
```

---

## 📋 功能特性

### 1️⃣ 提示词加载

- ✅ 从 `.env` 配置文件自动加载
- ✅ 支持 JSON 配置文件导入/导出
- ✅ 内置默认提示词

### 2️⃣ 提示词生成

- ✅ 系统提示词 + 人格上下文
- ✅ 用户提示词 + 记忆上下文
- ✅ 占位符支持（`{user_input}`, `{timestamp}`等）

### 3️⃣ 上下文管理

- ✅ 人格上下文自动格式化
- ✅ 记忆上下文智能拼接
- ✅ 可配置上下文大小

### 4️⃣ 历史记录

- ✅ 提示词使用历史
- ✅ 自动限制历史数量
- ✅ 支持历史查询

---

## 💡 基础使用

### 初始化提示词管理器

```python
from core import PromptManager

# 使用默认配置（从 .env 加载）
pm = PromptManager()

# 使用自定义配置路径
from pathlib import Path
pm = PromptManager(config_path=Path('config/custom.env'))
```

### 获取提示词

```python
# 获取系统提示词
system_prompt = pm.get_system_prompt()
print(system_prompt)

# 获取用户提示词模板
template = pm.get_user_prompt_template()
print(template)
```

### 生成完整提示词

```python
# 构建完整提示词
full_prompt = pm.build_full_prompt(
    user_input="你好",
    personality={'vectors': {'warmth': 0.8, 'logic': 0.7}},
    memory_context=[
        {'input': '问题1', 'response': '回答1'},
        {'input': '问题2', 'response': '回答2'}
    ]
)

print(f"系统提示词: {full_prompt['system']}")
print(f"用户提示词: {full_prompt['user']}")
```

---

## 🎨 高级使用

### 自定义系统提示词

```python
# 设置新的系统提示词
pm.set_system_prompt("你是一个专业的Python编程助手。")

# 重置为默认
pm.reset_to_default()
```

### 加载JSON配置

```python
# 从JSON文件加载
pm.load_from_json(Path('prompts/developer.json'))

# 保存到JSON文件
pm.save_to_json(Path('prompts/backup.json'))
```

### 导出配置

```python
# 导出为字符串
config_str = pm.export_prompt_config()
print(config_str)
```

### 获取设置

```python
# 获取所有设置
settings = pm.get_settings()

# 访问具体设置
print(f"系统提示词: {settings['system_prompt']}")
print(f"记忆上下文启用: {settings['memory_context_enabled']}")
print(f"记忆上下文最大条数: {settings['memory_context_max_count']}")
```

---

## 📝 配置文件格式

### JSON配置示例

```json
{
  "system_prompt": "你是弥娅，一个专业的编程助手...",
  "user_prompt_template": "用户输入：{user_input}",
  "personality_context_enabled": true,
  "memory_context_enabled": true,
  "memory_context_max_count": 5
}
```

### .env 配置示例

```env
# 系统提示词
SYSTEM_PROMPT=你是弥娅（Miya），一个温暖、智慧的AI助手。

# 用户提示词模板
USER_PROMPT_TEMPLATE=用户输入：{user_input}

# 上下文配置
ENABLE_PERSONALITY_CONTEXT=true
ENABLE_MEMORY_CONTEXT=true
MEMORY_CONTEXT_MAX_COUNT=5
```

---

## 🔄 提示词变体管理

### 创建多个配置文件

```
prompts/
├── README.md              # 本文件
├── system_prompts.md      # 提示词库
├── standard.json         # 标准助手
├── developer.json        # 编程助手
├── writer.json           # 写作助手
└── custom.json           # 自定义配置
```

### 动态切换

```python
from core import PromptManager
from pathlib import Path

pm = PromptManager()

# 切换到编程助手模式
pm.load_from_json(Path('prompts/developer.json'))

# ... 使用编程助手 ...

# 切换到写作助手模式
pm.load_from_json(Path('prompts/writer.json'))

# ... 使用写作助手 ...
```

---

## 🧪 测试示例

### 测试1：基础功能

```python
from core import PromptManager

pm = PromptManager()

# 测试系统提示词
print("系统提示词:", pm.get_system_prompt())

# 测试用户提示词
print("用户提示词模板:", pm.get_user_prompt_template())
```

### 测试2：上下文生成

```python
from core import PromptManager

pm = PromptManager()

# 模拟人格
personality = {
    'vectors': {
        'warmth': 0.8,
        'logic': 0.7,
        'creativity': 0.6,
        'empathy': 0.75,
        'resilience': 0.7
    },
    'dominant': 'warmth'
}

# 模拟记忆
memories = [
    {'input': '你好', 'response': '你好！有什么可以帮助你的吗？'},
    {'input': '我想学习Python', 'response': 'Python是一门很棒的编程语言...'}
]

# 生成提示词
full_prompt = pm.build_full_prompt(
    user_input="如何入门Python？",
    personality=personality,
    memory_context=memories
)

print("=== 系统提示词 ===")
print(full_prompt['system'])
print("\n=== 用户提示词 ===")
print(full_prompt['user'])
```

### 测试3：配置切换

```python
from core import PromptManager
from pathlib import Path

pm = PromptManager()

# 加载不同配置
configs = [
    'prompts/standard.json',
    'prompts/developer.json',
    'prompts/writer.json'
]

for config_path in configs:
    pm.load_from_json(Path(config_path))
    print(f"\n配置: {config_path}")
    print(f"系统提示词前50字: {pm.get_system_prompt()[:50]}...")
```

---

## 📚 API参考

### PromptManager 类

#### 初始化

```python
PromptManager(config_path: Optional[Path] = None)
```

#### 核心方法

| 方法 | 说明 | 返回值 |
|-----|------|--------|
| `set_system_prompt(prompt)` | 设置系统提示词 | bool |
| `get_system_prompt()` | 获取系统提示词 | str |
| `set_user_prompt_template(template)` | 设置用户提示词模板 | bool |
| `get_user_prompt_template()` | 获取用户提示词模板 | str |
| `build_full_prompt(...)` | 构建完整提示词 | Dict |
| `get_settings()` | 获取所有设置 | Dict |

#### 配置管理

| 方法 | 说明 | 返回值 |
|-----|------|--------|
| `load_from_json(path)` | 从JSON加载 | bool |
| `save_to_json(path)` | 保存到JSON | bool |
| `reset_to_default()` | 重置为默认 | None |
| `export_prompt_config()` | 导出配置字符串 | str |

#### 历史记录

| 方法 | 说明 | 返回值 |
|-----|------|--------|
| `add_to_history(...)` | 添加历史记录 | None |
| `get_history(count)` | 获取历史记录 | List |

---

## 🎯 最佳实践

### 1. 使用JSON配置

**推荐**：使用JSON文件管理提示词，便于版本控制和切换。

```json
{
  "system_prompt": "...",
  "user_prompt_template": "...",
  ...
}
```

### 2. 版本管理

将提示词配置纳入版本控制：

```
git add prompts/*.json
git commit -m "Update developer prompt"
```

### 3. 测试驱动

创建测试用例验证提示词效果。

### 4. 渐进式优化

先从简单提示词开始，逐步优化。

---

## 🚀 集成到弥娅

提示词管理器已经集成到弥娅主程序：

```python
# run/main.py 中已集成
self.prompt_manager = PromptManager()

# 使用时
full_prompt = self.prompt_manager.build_full_prompt(
    user_input=user_input,
    personality=self.personality.get_profile(),
    memory_context=self.memory_engine.get_recent_context(5)
)
```

---

## 📖 相关文档

- `system_prompts.md` - 提示词库
- `PROMPT_CONFIG_GUIDE.md` - 配置指南
- `core/prompt_manager.py` - 源代码

---

## ✨ 开始使用

提示词管理器已集成到核心模块，随时可以调用！

```python
from core import PromptManager

pm = PromptManager()
system_prompt = pm.get_system_prompt()
print(system_prompt)
```

**享受灵活的提示词管理！** 🎉

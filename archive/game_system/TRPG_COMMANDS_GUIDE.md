# 弥娅 TRPG 跑团系统 - 完整指令手册

## 🎲 基础指令

### 启动跑团
```
/trpg coc7 团名
/trpg dnd5e 团名
```
启动跑团模式，选择规则系统和设置团名。

---

## 🎮 角色卡指令

### 创建角色卡
```
/pc create 角色名 coc7
/pc create 角色名 dnd5e
```
创建角色卡，支持随机生成属性或手动设置。

### 查看角色卡
```
/pc show
/pc show 123456  # 查看指定玩家
```
显示角色的完整信息。

### 更新角色卡
```
/pc update 力量 60
/pc update hp 5 add
/pc update san 10 subtract
```
更新角色属性或状态值。

### 删除角色卡
```
/pc delete
```
删除当前角色卡（需要确认）。

---

## 🎯 投骰指令

### 普通投骰
```
/roll 3d6
/roll 1d100
/roll 2d10+5 力量检定
```
投掷骰子，支持标准骰子表达式。

### 暗骰
``/rs 1d100 潜行
/roll_secret 1d100 潜行
```
进行暗骰，结果仅发送给 KP。

### 技能检定
``/sc 侦查 60
/sc 力量 50
/sc 聆听 70 coc7
/skill_check 侦查 60
```
进行技能检定，自动计算修正值和判定结果。

---

## 🎪 KP 主持人指令

### 设置场景
```
/kp set_scene 场景名 描述
/kp set_scene "迷雾图书馆" "这是一座古老的图书馆，充满了神秘气息..."
```
设置当前场景的名称和描述。

### 查看场景
```
/kp show_scene
```
显示当前场景的详细信息。

### 添加 NPC
```
/kp add_npc NPC名 描述
/kp add_npc "老图书管理员" "一位年迈的管理员，眼睛虽然浑浊但洞察一切"
```
向当前场景添加 NPC。

### 移除 NPC
```
/kp remove_npc NPC名
```
从场景中移除 NPC。

### 列出 NPC
```
/kp list_npc
```
列出当前场景的所有 NPC。

### 添加线索
```
/kp add_clue 线索内容
/kp add_clue "在书架角落发现一本古老的日记"
```
向当前场景添加线索。

### 列出线索
```
/kp list_clue
```
列出当前场景的所有线索。

### 设置 KP 模式
```
/kp set_kp_mode independent
/kp set_kp_mode cross_group
/kp set_kp_mode global
```
设置 KP 模式：
- `independent`: 每个群独立 KP
- `cross_group`: 跨群共享 KP
- `global`: 全局唯一 KP

### 设置 KP
```
/kp set_kp 123456
```
设置当前群的 KP（需要 KP QQ 号）。

### 设置阶段
```
/kp set_phase exploration  # 探索
/kp set_phase combat      # 战斗
/kp set_phase interaction # 互动
/kp set_phase rest        # 休息
```
设置当前游戏阶段。

---

## ⚔️ 战斗指令

### 攻击
```
/attack 目标
/attack 怪物名
/attack 目标 --attack_bonus 5 --damage_dice 2d6 --damage_bonus 3
```
进行攻击检定和伤害计算。

### 战斗日志
``/combat_log
/combat_log --limit 20
```
查看最近的战斗记录。

---

## 📊 系统统计

### 当前工具列表（11 个）

1. `start_trpg` - 启动跑团模式
2. `roll_dice` - 投骰
3. `roll_secret` - 暗骰
4. `create_pc` - 创建角色卡
5. `show_pc` - 查看角色卡
6. `update_pc` - 更新角色卡
7. `delete_pc` - 删除角色卡
8. `skill_check` - 技能检定
9. `kp_command` - KP 指令（10+ 子指令）
10. `attack` - 攻击
11. `combat_log` - 战斗日志

---

## 🎯 规则系统

### COC 7 规则
- ✅ d100 判定系统
- ✅ 成功等级（大成功、极难成功、困难成功、成功、失败、大失败）
- ✅ 衍生属性计算
- ✅ 理智检定
- ✅ 技能检定

### D&D 5E 规则
- ✅ 属性修正值
- ✅ 优势/劣势系统
- ✅ 技能检定
- ✅ 攻击检定
- ✅ 伤害检定
- ✅ 先攻检定
- ✅ 豁免检定

---

## 💾 数据存储

系统会创建以下数据文件：

- `data/trpg_sessions.json` - 跑团会话数据
- `data/trpg_characters.json` - 角色卡数据
- `data/trpg_scenes.json` - 场景数据
- `data/trpg_combat_logs.json` - 战斗日志

---

## 🎭 使用示例

### COC7 跑团示例

```
玩家: /trpg coc7 迷雾图书馆
弥娅: 🎲 跑团模式已启动...

玩家: /pc create 亚瑟 coc7
弥娅: ✅ 角色卡创建成功...

KP: /kp set_scene "密室" "这是一间封闭的石室，墙上有奇怪的符号..."
弥娅: 📍 密室...

KP: /kp add_npc "守卫" "身穿盔甲的守卫，手持长剑"
弥娅: ✅ NPC 已添加...

玩家: /sc 侦查 60
弥娅: 🎲 侦查检定...
投骰：42 / 60
结果：成功
✅ 成功！基本达成目标。

玩家: /attack 守卫
弥娅: ⚔️ 亚瑟 攻击 守卫
攻击检定：1d20=[18] + 0 = **18**
✅ 命中！
伤害：1d6=[5] + 0 = **5**
```

### D&D 5E 跑团示例

```
玩家: /trpg dnd5e 地下城探险
弥娅: 🎲 跑团模式已启动...

玩家: /pc create 艾尔 dnd5e
弥娅: ✅ 角色卡创建成功...

玩家: /sc 力量 16 dnd5e
弥娅: 🎲 力量检定...
属性：16
修正值：+3
投骰：**15** + 3 = **18**
✨ 优秀！表现非常出色！

KP: /kp set_phase combat
弥娅: ✅ 当前阶段已设置 - 战斗阶段

玩家: /attack 哥布林 --attack_bonus 5 --damage_dice 2d6 --damage_bonus 2
弥娅: ⚔️ 艾尔 攻击 哥布林...
```

---

## 🔧 高级功能

### 多团支持
- 每个群独立会话
- 角色卡跨群共享
- 三种 KP 模式

### 暗骰功能
- 结果仅发送给 KP
- 适用于秘密行动

### 战斗系统
- 自动记录战斗日志
- 支持暴击和大失败
- 伤害自动计算

### 场景管理
- 场景描述
- NPC 管理
- 线索系统

---

## 📞 帮助

如需帮助，可以：
1. 查看本文档
2. 运行 `python test_trpg_system.py` 测试系统
3. 查看 `TRPG_QUICK_START.md` 快速开始指南

---

**最后更新**: 2026-03-01
**工具数量**: 11 个核心工具 + 10+ KP 子指令
**支持的规则**: COC7, D&D 5E

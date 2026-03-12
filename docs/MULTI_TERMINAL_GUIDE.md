# 弥娅V4.0 - 多终端智能管理系统

## 🎯 功能概述

弥娅V4.0多终端管理系统允许您在同一操作系统上同时管理多个终端窗口，具备AI智能编排能力，支持并行执行、协同任务和自动决策。

## ✨ 核心特性

### 🖥️ 单机多终端
- ✅ 同时创建和管理多个终端
- ✅ 支持多种终端类型（CMD、PowerShell、WSL、Bash、Zsh）
- ✅ 终端间自由切换
- ✅ 实时状态监控

### 🤖 AI智能编排
- ✅ 智能任务分析和决策
- ✅ 自动选择最优终端
- ✅ 多终端协同任务规划
- ✅ 执行策略自动优化

### ⚡ 高级执行模式
- ✅ 并行执行：同时在多个终端执行命令
- ✅ 顺序执行：在单个终端依次执行多条命令
- ✅ 协同任务：多终端配合完成复杂任务

### 🎮 交互式Shell
- ✅ 直观的命令行界面
- ✅ 丰富的系统命令
- ✅ AI辅助执行
- ✅ 实时状态查看

## 📋 快速开始

### 启动多终端系统

**Windows:**
```batch
run/multi_terminal_start.bat
```

**Linux/macOS:**
```bash
chmod +x run/multi_terminal_start.sh
./run/multi_terminal_start.sh
```

### 基本使用

```
[弥娅] CMD主终端 > !create PowerShell -t powershell
[成功] 创建终端: PowerShell (ID: a1b2c3d4)

[弥娅] CMD主终端 > !list

══════════════════════════════════════════════════════════════════
终端列表              类型            状态        目录                  
══════════════════════════════════════════════════════════════════
★ CMD主终端          cmd             idle         D:\AI_MIYA_Facyory\MIYA\Miya
  PowerShell          powershell      idle         D:\AI_MIYA_Facyory\MIYA\Miya
══════════════════════════════════════════════════════════════════

[弥娅] CMD主终端 > !switch a1b2c3d4

[切换到终端] PowerShell (powershell)
[会话ID] a1b2c3d4
[当前目录] D:\AI_MIYA_Facyory\MIYA\Miya
[状态] idle
[命令历史] 0条
```

## 📖 命令参考

### 终端管理

| 命令 | 说明 | 示例 |
|--------|------|------|
| `!create <name> [-t type]` | 创建新终端 | `!create 测试终端 -t powershell` |
| `!list` | 列出所有终端 | `!list` |
| `!switch <session_id>` | 切换活动终端 | `!switch a1b2c3d4` |
| `!close <session_id>` | 关闭指定终端 | `!close a1b2c3d4` |
| `!status` | 显示详细状态 | `!status` |

### 执行模式

| 命令 | 说明 | 示例 |
|--------|------|------|
| `!parallel <sid:cmd>...` | 多终端并行执行 | `!parallel a1b2c3d4:dir e5f6g7h8:ls` |
| `!sequence <sid> <cmd>...` | 单终端顺序执行 | `!sequence a1b2c3d4 cd .. dir` |
| `!collab <task>` | 多终端协同任务 | `!collab 同时检查所有终端状态` |
| `!workspace <type> <dir>` | 自动设置工作空间 | `!workspace python D:\project` |

### AI智能

| 命令 | 说明 | 示例 |
|--------|------|------|
| `? <task>` | AI智能执行任务 | `? 帮我检查系统状态` |
| `?analyze <task>` | AI分析任务 | `?analyze 部署项目` |

## 🎯 使用场景

### 场景1: 开发工作流

```
[弥娅] CMD主终端 > !workspace python D:\MyProject
[弥娅] 正在设置工作空间...
  项目类型: python
  项目目录: D:\MyProject
  ✓ 创建终端: 主终端
  ✓ 创建终端: 虚拟环境

[弥娅] 主终端 > ? 启动开发服务器
[弥娅思考中...]
  任务: 启动开发服务器
  策略: parallel

[执行结果]
  策略: parallel
  并行结果: 2个终端
    abc123: ✓
    def456: ✓
```

### 场景2: 系统运维

```
[弥娅] CMD主终端 > !parallel abc123:tasklist def456:df -h
[并行执行] 2个任务

  abc123: ✓ 当前进程数: 45
  def456: ✓ 磁盘使用: 60%
```

### 场景3: 多终端协同

```
[弥娅] CMD主终端 > !collab 同时监控多个服务器
[弥娅] 协同任务规划
  目标: 同时监控多个服务器
  步骤: 3

[步骤 1/3] 准备阶段
  描述: 准备工作环境
  ✓ 在主终端执行 echo "准备开始"

[步骤 2/3] 数据收集
  描述: 收集服务器数据
  ✓ 并行执行完成

[步骤 3/3] 结果分析
  描述: 分析收集的数据
  ✓ 分析完成

[弥娅] 协同任务完成!
```

## 🏗️ 架构设计

```
弥娅V4.0多终端管理引擎
│
├── core/
│   ├── terminal_types.py        # 终端类型和会话定义
│   ├── local_terminal_manager.py # 单机多终端管理器
│   └── terminal_orchestrator.py # 智能终端编排器
│
└── run/
    ├── multi_terminal_main.py   # 交互式多终端Shell
    ├── multi_terminal_start.bat # Windows启动脚本
    └── multi_terminal_start.sh  # Linux/macOS启动脚本
```

## 🔧 支持的终端类型

- **CMD**: Windows命令提示符
- **PowerShell**: Windows PowerShell
- **WSL**: Windows Subsystem for Linux
- **Bash**: Linux/macOS Bash
- **Zsh**: macOS Zsh
- **Git Bash**: Git Bash

## 🚀 未来规划

- [ ] 集成真实AI后端（DeepSeek等）
- [ ] 远程终端管理（SSH）
- [ ] 终端输出实时捕获
- [ ] 可视化终端管理界面
- [ ] 终端会话持久化
- [ ] 更多预设场景和模板

## 📝 注意事项

1. 当前版本为演示实现，终端进程创建后不会自动清理
2. 命令执行结果为模拟输出，未真实捕获进程输出
3. AI决策使用简化逻辑，未集成真实AI API
4. 建议在生产环境使用前进行完整测试

## 🤝 贡献

欢迎提交Issue和Pull Request来改进弥娅多终端管理系统！

---

**弥娅V4.0 - 让终端管理更智能**

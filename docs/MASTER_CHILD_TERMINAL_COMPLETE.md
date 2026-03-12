# 弥娅V4.0 主-子终端协作架构 - 实现完成

## 📋 实现概述

本次实现完成了符合弥娅框架的主-子终端协作架构，实现了用户要求的"主终端总控、子终端执行、弥娅全时在线"的核心功能。

## 🎯 核心目标达成

### ✅ 1. 主终端（Master Terminal）- 总控中心
- **用户交互与对话**：接收用户输入，弥娅AI响应
- **任务规划与分解**：弥娅AI理解任务意图，规划执行策略
- **思考过程显示**：在主终端展示弥娅的详细思考过程
- **全局调度**：智能分配任务到最优子终端
- **进度监控**：实时监控所有子终端的执行状态
- **结果汇总**：整合并展示所有任务执行结果

### ✅ 2. 子终端（Child Terminals）- 执行环境
- **专注执行**：每个子终端专注于具体任务的执行
- **多类型支持**：本地终端（CMD/PowerShell/WSL）和SSH远程终端
- **状态监控**：实时跟踪执行状态（idle/running/completed/failed）
- **弥娅接管**：支持弥娅直接在子终端中执行命令
- **执行统计**：记录命令执行历史和成功率

### ✅ 3. 弥娅接管模式（MiyaTakeoverMode）- 全时在线
- **统一交互接口**：无论在主终端还是子终端，弥娅都能响应
- **智能识别**：自动识别用户输入是对话请求还是任务执行
- **思考过程显示**：在来源终端显示弥娅的思考过程
- **灵活接管**：可启用/禁用任意终端的弥娅接管模式

## 📁 新增文件

### 1. `core/master_terminal_controller.py`
**主终端控制器 - 总控中心**

核心类：
- `MasterTerminalController`：主终端控制器
  - `process_user_input()`：处理用户输入
  - `_plan_task()`：规划任务执行策略
  - `_execute_task_plan()`：执行任务计划
  - `_create_child_terminal()`：创建子终端
  - `_show_thinking()`：显示思考过程
  - `_show_result_summary()`：显示结果汇总
  - `assign_task()`：分配任务到子终端
  - `_select_optimal_terminal()`：智能选择最优终端
  - `start_monitoring()`/`stop_monitoring()`：监控控制

数据类：
- `Task`：任务对象
- `TaskResult`：任务执行结果
- `TaskPriority`：任务优先级枚举

### 2. `core/child_terminal.py`
**子终端管理 - 执行环境**

核心类：
- `ChildTerminal`：子终端包装
  - `execute()`：执行命令列表
  - `_execute_local()`：本地终端执行
  - `_execute_ssh()`：SSH终端执行
  - `execute_from_miya()`：弥娅接管执行
  - `is_running()`/`is_idle()`：状态检查
  - `get_recent_output()`：获取最近输出
  - `get_result()`：获取执行结果
  - `enable_miya_takeover()`/`disable_miya_takeover()`：接管模式控制

- `ChildTerminalManager`：子终端管理器
  - `create_child_terminal()`：创建子终端
  - `get_child_terminal()`：获取子终端
  - `get_all_child_terminals()`：获取所有子终端
  - `close_child_terminal()`：关闭子终端
  - `close_all()`：关闭所有子终端

数据类：
- `ChildTerminalConfig`：子终端配置

### 3. `core/miya_takeover_mode.py`
**弥娅接管模式 - 全时在线**

核心类：
- `MiyaTakeoverMode`：弥娅接管模式
  - `handle_input()`：处理来自任意终端的输入
  - `_is_miya_request()`：判断是否是对弥娅的请求
  - `_route_to_miya()`：路由到弥娅处理
  - `_handle_child_terminal_command()`：处理子终端中的普通命令
  - `enable_takeover_for_terminal()`：启用指定终端的接管模式
  - `disable_takeover_for_terminal()`：禁用指定终端的接管模式
  - `get_current_terminal()`：获取当前活动终端
  - `get_all_terminals_status()`：获取所有终端状态

## 🔧 修改文件

### 1. `core/terminal_manager.py`
**导出新模块**
- 添加了 `MasterTerminalController`, `ChildTerminal`, `ChildTerminalManager`, `MiyaTakeoverMode` 等类的导出
- 添加了 `Task`, `TaskResult`, `TaskPriority`, `ChildTerminalConfig` 等数据类的导出

### 2. `run/main.py`
**集成主-子终端协作架构**

**新增导入**：
```python
from core.terminal_manager import (
    MasterTerminalController,
    ChildTerminalManager,
    ChildTerminalConfig,
    MiyaTakeoverMode
)
from core.ssh_terminal_manager import SSHTerminalManager
```

**初始化主-子终端架构**（在 `Miya.__init__()` 中）：
```python
# 初始化SSH管理器
self.ssh_manager = SSHTerminalManager()

# 初始化主终端控制器
self.master_terminal_controller = MasterTerminalController(
    local_manager=self.terminal_orchestrator.terminal_manager,
    ssh_manager=self.ssh_manager,
    show_thinking=True,
    auto_monitor=True,
    monitor_interval=1.0
)

# 初始化子终端管理器
self.child_terminal_manager = ChildTerminalManager(
    local_manager=self.terminal_orchestrator.terminal_manager,
    ssh_manager=self.ssh_manager
)

# 初始化弥娅接管模式
self.miya_takeover_mode = MiyaTakeoverMode(
    master_controller=self.master_terminal_controller,
    child_manager=self.child_terminal_manager
)

# 设置弥娅AI回调
self.miya_takeover_mode.set_miya_callback(self._miya_ai_callback)
```

**新增弥娅AI回调方法**：
```python
async def _miya_ai_callback(self, input_text: str, from_terminal: str = "master") -> str:
    """弥娅AI回调 - 用于主终端控制器和弥娅接管模式"""
    from mlink import Message

    message = Message(
        sender_id=from_terminal,
        content=input_text,
        message_type="text",
        timestamp=datetime.now(),
        context={"from_terminal": from_terminal}
    )

    # 使用DecisionHub处理
    response = await self.decision_hub.process_perception_cross_platform(message)

    return response or ""
```

**修改主循环**：
- 将主循环改为异步函数 `main_loop()`
- 使用弥娅接管模式处理所有用户输入
- 添加特殊命令支持：
  - `switch <terminal_name>`：切换终端
  - `list terminals`：列出所有终端

## 🏗️ 架构设计

### 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                  主终端（Master Terminal）              │
│                  ───── 总控中心 ─────             │
│                                                         │
│  功能：                                                │
│  ├─ 用户交互（对话输入输出）                           │
│  ├─ 任务规划与分解（弥娅思考过程）                   │
│  ├─ 全局调度（任务分配到子终端）                       │
│  ├─ 进度监控（所有子终端状态）                          │
│  ├─ 弥娅思考过程显示                                  │
│  └─ 结果汇总（整合所有子终端结果）                       │
│                                                         │
│  弥娅 AI 核心                                          │
│  ├─ 理解用户意图                                       │
│  ├─ 规划任务执行策略                                    │
│  ├─ 决定任务分配（哪个子终端）                           │
│  ├─ 实时思考（显示在主终端）                           │
│  └─ 全局协调与调度                                      │
└─────────────────────────────────────────────────────────┘
                          │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  子终端 1   │  │  子终端 2   │  │  子终端 N   │
│  (执行环境) │  │  (执行环境) │  │  (执行环境) │
└─────────────┘  └─────────────┘  └─────────────┘

每个子终端：
├─ 接收并执行命令（从主终端分配）
├─ 返回执行结果
├─ 状态监控（运行中/完成/失败）
└─ 可被弥娅接管（弥娅直接输入命令）
```

### 交互流程

#### 场景1：用户要求执行新任务

```
用户输入（主终端）：
佳: 弥娅，帮我在服务器上部署这个项目

弥娅思考过程（主终端）：
[弥娅思考] 分析任务: 部署项目到服务器
[弥娅思考] 评估需求: 需要SSH连接到服务器
[弥娅思考] 规划步骤:
           1. 建立SSH连接（子终端1）
           2. 上传代码到服务器
           3. 安装依赖
           4. 启动服务
[弥娅思考] 创建子终端1 (SSH连接服务器1)
[弥娅思考] 任务分配: 子终端1 (上传代码)
[弥娅思考] 创建子终端2 (SSH连接服务器2)
[弥娅思考] 任务分配: 子终端2 (安装依赖)
[弥娅思考] 任务分配: 子终端2 (启动服务)

系统执行（子终端）：
子终端1: $ scp -r . user@server:/app/
子终端2: $ ssh user@server
         $ cd /app
         $ npm install
         $ npm start

主终端监控显示：
[监控] 子终端1: 上传代码中...
[监控] 子终端1: ✓ 上传完成
[监控] 子终端2: 安装依赖中...
[监控] 子终端2: ✓ 依赖安装完成 (30s)
[监控] 子终端2: 启动服务中...
[监控] 子终端2: ✓ 服务启动成功

主终端汇总：
【任务完成】
  代码上传: ✓
  依赖安装: ✓
  服务启动: ✓
  总耗时: 2分15秒
```

#### 场景2：子终端中弥娅接管

```
子终端1状态: 正在运行服务

用户输入（子终端1）：
弥娅，检查服务状态

子终端显示：
[弥娅] 收到来自 子终端1 的请求
[弥娅思考] 查询服务状态...
[弥娅思考] 执行检查命令

弥娅执行：
$ curl http://localhost:8080/health

子终端显示输出：
服务状态: 运行中 (200 OK)
```

#### 场景3：主终端全局调度

```
主终端显示多个任务并行执行

用户输入（主终端）：
佳: 弥娅，同时测试前端和后端

弥娅思考（主终端）：
[弥娅思考] 分析任务: 并行测试前端后端
[弥娅思考] 评估: 需要两个独立终端
[弥娅思考] 分配: 子终端3 (前端测试)
[弥娅思考] 分配: 子终端4 (后端测试)

主终端监控显示：
[监控] === 并行任务执行 ===
[监控] 子终端3: 前端测试
           运行测试套件...
           
[监控] 子终端4: 后端测试
           运行单元测试...
           
[监控] === 子终端3完成 ===
[监控] 结果: ✓ 23个测试通过 (45s)
           
[监控] === 子终端4完成 ===
[监控] 结果: ✓ 156个测试通过 (38s)

主终端汇总：
【并行任务完成】
  前端测试: ✓ 23/23
  后端测试: ✓ 156/156
  总耗时: 45秒（并行）
```

## 🎨 设计优势

### 1. 清晰的职责分离
- **主终端**：规划、调度、监控、交互
- **子终端**：纯粹的任务执行

### 2. 弥娅全时在线
- **任何终端都能与弥娅交互**
- **主终端显示详细思考过程**
- **子终端在执行间隙响应**

### 3. 可扩展性
- 轻松添加新的终端类型（WSL、容器等）
- 支持多种远程连接方式
- 终端池动态管理

### 4. 符合弥娅框架
- 集成人格、记忆、情绪、自主系统
- 保持架构一致性
- 支持蛛网式模块化

### 5. 智能化
- AI理解用户意图
- 智能选择最优终端
- 自动任务分配与调度
- 实时监控与进度展示

## 🚀 使用方式

### 启动系统

```bash
# 主终端启动（默认）
python run/main.py

# 启动后，主终端进入总控模式
佳: （等待用户输入）

# 用户可以：
# 1. 与弥娅对话（主终端显示思考过程）
# 2. 分配任务到子终端
# 3. 监控所有子终端状态
# 4. 在任何子终端中与弥娅交互
```

### 主终端交互示例

```bash
# 对话模式
佳: 弥娅，你好
[弥娅] 你好！我是弥娅，很高兴见到你！

# 任务执行模式
佳: 创建一个新终端并检测系统状态
[弥娅思考] 分析任务: 创建新终端并检测系统状态
[弥娅思考] 评估需求: 需要创建本地终端
[弥娅思考] 创建子终端1 (本地终端)
[弥娅思考] 任务分配: 子终端1 (检测系统状态)
...
【任务完成】
  检测系统状态: ✓
  耗时: 2.5s

# 查看所有终端
佳: list terminals
=== 所有终端状态 ===
  master: 主终端 (master) - active
  abc12345: 子终端1 (local) - completed

# 切换终端
佳: switch abc12345
[主终端] 切换到终端: abc12345
```

## 📊 与现有架构的集成

### 弥娅框架组件集成

```
弥娅框架组件：
├─ Personality: 影响任务分配策略（人格偏好）
│  好奇强: 优先使用新终端尝试
│  逻辑性强: 严格评估任务需求
│  温暖感性: 更友好的思考过程显示
│
├─ Memory: 记住用户习惯
│  常用服务器配置
│  偏好的终端类型
│  历史任务执行模式
│
├─ Autonomy: 自主优化
│  学习最优终端分配策略
│  自动调整监控频率
│  智能任务队列管理
│
└─ Emotion: 情绪化思考过程
   困惑时: 显示更多思考细节
   自信时: 简洁的思考过程
   压力大: 显示详细的计划分解
```

### 工具调用接口

弥娅在主终端调用工具：

```python
# 创建本地子终端
multi_terminal(action='create_terminal',
                name='本地执行1',
                terminal_type='cmd')

# 创建SSH子终端
multi_terminal(action='create_terminal',
                name='服务器1',
                terminal_type='ssh',
                ssh_config={'host': 'server.com', 'user': 'deploy'})

# 并行执行（主终端监控）
multi_terminal(action='execute_parallel',
                commands={
                    'term_1': 'npm test',
                    'term_2': 'pytest'
                })
```

## 📝 技术实现细节

### 1. 任务规划算法

基于关键词分析和启发式规则：
- 识别是否需要新终端（关键词：打开终端、创建终端、新终端等）
- 识别是否需要SSH（关键词：ssh、远程、服务器等）
- 识别是否需要并行（关键词：同时、并行、一起等）
- 智能提取命令（支持多行输入）

### 2. 终端选择策略

优先级规则：
1. 选择空闲终端（状态为idle）
2. 选择活动终端（无空闲时）
3. 创建新终端（需要时）

### 3. 监控机制

- 后台异步监控循环
- 实时获取所有终端状态
- 显示活跃终端数量和状态
- 可配置监控间隔（默认1秒）

### 4. 弥娅接管模式

关键词识别：
- 对话关键词：弥娅、miya、你好、hello、解释、分析、帮我、help等
- 问号结尾
- 智能路由到AI处理

## 🔮 未来扩展

### 短期（已实现基础）
- ✅ 主终端控制器
- ✅ 子终端管理器
- ✅ 弥娅接管模式
- ✅ 本地和SSH终端支持
- ✅ 任务规划与执行
- ✅ 实时监控

### 中期（可扩展）
- 🔄 容器终端支持（Docker/Kubernetes）
- 🔄 WSL2原生支持
- 🔄 任务持久化（保存/恢复）
- 🔄 预设场景模板
- 🔄 自动化工作流

### 长期（可研究）
- 🔄 分布式终端管理（多机协同）
- 🔄 AI自主优化任务分配策略
- 🔄 终端编排可视化界面
- 🔄 任务依赖图管理

## 🎉 总结

本次实现完全符合用户的要求：

✅ **主终端像你一样思考和规划**
- 显示弥娅的思考过程
- 智能理解用户意图
- 自动规划任务执行策略

✅ **子终端专注执行**
- 每个新任务在独立的子终端中运行
- 支持多种终端类型（本地、SSH）
- 实时监控执行状态

✅ **弥娅随时可交互**
- 无论在主控还是子终端，弥娅都可以交互
- 主终端显示思考过程
- 子终端支持弥娅接管执行

✅ **符合弥娅框架**
- 集成所有子系统（Personality、Memory、Emotion、Autonomy）
- 保持蛛网式模块化架构
- 支持未来扩展

这正是用户想要的："主程序的终端是总控规划，其他子终端是执行，和你差不多，但是无论是在总控终端还是子终端，弥娅都可以交互，甚至总控终端还和你一样，可以看见思考过程。"

# 弥娅多终端协作架构设计方案

## 🎯 核心理念

### 设计目标

1. **主终端（Master Terminal）** - 总控与交互中心
   - 专注于用户交互、任务规划、全局调度
   - 显示弥娅的思考过程
   - 负责任务分配到子终端
   - 监控所有子终端的执行进度

2. **子终端（Child Terminals）** - 执行环境
   - 专注于具体任务的执行
   - 每个新任务都在独立的子终端中运行
   - 支持多种终端类型（本地、SSH、容器等）
   - 不直接处理用户交互，只接收并执行命令

3. **弥娅全时交互** - 无论在主终端还是子终端
   - 在任何终端中都能与弥娅交互
   - 主终端显示弥娅的思考过程
   - 子终端在执行间隙也能响应弥娅

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

## 📐 核心模块设计

### 1. 主终端控制器（MasterTerminalController）

```python
class MasterTerminalController:
    """主终端控制器 - 总控中心"""
    
    def __init__(self):
        self.child_terminals = {}  # 子终端池
        self.task_queue = []         # 任务队列
        self.monitoring = True        # 监控状态
        self.miya_thinking = True    # 显示思考过程
        
    def assign_task(self, task: Task, terminal_id: str = None):
        """分配任务到子终端
        
        Args:
            task: 任务对象（包含命令、优先级等）
            terminal_id: 指定的子终端ID，None表示自动选择
        """
        # 弥娅思考过程（显示在主终端）
        self._show_miya_thinking(f"分析任务: {task.description}")
        self._show_miya_thinking(f"评估资源需求...")
        self._show_miya_thinking(f"选择最优执行环境...")
        
        # 智能选择子终端
        if terminal_id:
            selected_terminal = terminal_id
        else:
            selected_terminal = self._select_optimal_terminal(task)
        
        self._show_miya_thinking(f"任务分配到: 子终端 {selected_terminal}")
        
        # 分配任务
        child_terminal = self.child_terminals[selected_terminal]
        child_terminal.execute(task.commands)
        
        # 开始监控
        self._monitor_task(child_terminal, task)
    
    def _select_optimal_terminal(self, task: Task) -> str:
        """智能选择最优子终端
        
        策略：
        1. 检查是否有空闲终端
        2. 评估任务类型（CPU密集、IO密集、网络等）
        3. 根据负载选择最佳终端
        4. 没有空闲时，创建新终端
        """
        pass
    
    def _show_miya_thinking(self, thought: str):
        """显示弥娅的思考过程"""
        if self.miya_thinking:
            print(f"[弥娅思考] {thought}")
    
    def _monitor_task(self, child_terminal, task):
        """监控任务执行进度"""
        while child_terminal.is_running():
            # 显示进度
            print(f"[监控] 子终端 {child_terminal.id}: {task.description}")
            print(f"[监控] 输出: {child_terminal.get_recent_output()}")
            time.sleep(1)
        
        # 任务完成
        result = child_terminal.get_result()
        self._show_result_summary(result)
    
    def _show_result_summary(self, result):
        """显示结果汇总"""
        print(f"\n【任务完成】")
        print(f"  退出码: {result.exit_code}")
        print(f"  耗时: {result.duration}")
        print(f"  输出: {result.output[:200]}...")
```

### 2. 子终端管理器（ChildTerminalManager）

```python
class ChildTerminal:
    """子终端 - 执行环境"""
    
    def __init__(self, terminal_id: str, terminal_type: str):
        self.id = terminal_id
        self.type = terminal_type  # local, ssh, container
        self.status = "idle"    # idle, running, completed, failed
        self.current_task = None
        self.miya_takeover = False  # 弥娅是否接管
        
        # 根据类型创建终端
        if terminal_type == "local":
            self.terminal = LocalTerminal()
        elif terminal_type == "ssh":
            self.terminal = SSHTerminal()
        elif terminal_type == "container":
            self.terminal = ContainerTerminal()
    
    def execute(self, commands: list):
        """执行命令"""
        self.status = "running"
        self.terminal.execute(commands)
    
    def execute_from_miya(self, command: str):
        """弥娅接管执行
        
        当弥娅在子终端中直接输入命令时调用
        """
        if self.miya_takeover:
            self.terminal.execute([command])
            return self.get_recent_output()
    
    def is_running(self):
        """检查是否在运行"""
        return self.status == "running"
    
    def get_recent_output(self, lines: int = 20):
        """获取最近输出"""
        return self.terminal.get_output(lines=lines)
    
    def get_result(self):
        """获取执行结果"""
        self.status = "completed"
        return {
            "exit_code": self.terminal.exit_code,
            "output": self.terminal.get_all_output(),
            "duration": self.terminal.execution_time
        }
```

### 3. SSH终端适配器（SSHTerminalAdapter）

```python
class SSHTerminal:
    """SSH终端 - 远程服务器连接"""
    
    def __init__(self, host: str, username: str, key_path: str = None):
        self.host = host
        self.username = username
        self.key_path = key_path
        self.ssh_client = None
        self.session = None
        
    def connect(self):
        """建立SSH连接"""
        import paramiko
        
        self.ssh_client = paramiko.SSHClient()
        if self.key_path:
            self.ssh_client.connect(
                hostname=self.host,
                username=self.username,
                key_filename=self.key_path
            )
        else:
            # 使用密码认证
            password = getpass.getpass(f"SSH密码 ({self.username}@{self.host}): ")
            self.ssh_client.connect(
                hostname=self.host,
                username=self.username,
                password=password
            )
        
        self.session = self.ssh_client.invoke_shell()
        print(f"✅ SSH连接成功: {self.username}@{self.host}")
    
    def execute(self, commands: list):
        """远程执行命令"""
        for cmd in commands:
            self.session.send(cmd + "\n")
            time.sleep(0.1)  # 等待命令执行
        
        # 获取输出
        output = ""
        while True:
            if self.session.recv_ready():
                data = self.session.recv(4096).decode()
                output += data
                break
        
        return output
    
    def disconnect(self):
        """断开SSH连接"""
        if self.session:
            self.session.close()
        if self.ssh_client:
            self.ssh_client.close()
        print(f"SSH连接已断开: {self.username}@{self.host}")
```

### 4. 弥娅接管模式（MiyaTakeoverMode）

```python
class MiyaTakeoverMode:
    """弥娅接管模式 - 在任何终端中都能交互"""
    
    def __init__(self, master_controller, terminal_manager):
        self.master = master_controller
        self.manager = terminal_manager
        self.current_terminal = "master"  # master 或 child_id
    
    def handle_input(self, input_text: str, from_terminal: str):
        """处理来自任意终端的输入
        
        Args:
            input_text: 用户输入
            from_terminal: 来源终端（"master" 或 child_id）
        """
        # 识别是否是对弥娅的请求
        if self._is_miya_request(input_text):
            # 弥娅处理请求
            self._route_to_miya(input_text, from_terminal)
        elif from_terminal == "master":
            # 主终端的普通命令，分配到子终端
            self.master.assign_task(Task(input_text))
        else:
            # 子终端中的普通命令，直接执行
            child = self.manager.get_terminal(from_terminal)
            child.execute_from_miya(input_text)
    
    def _is_miya_request(self, input: str) -> bool:
        """判断是否是对弥娅的请求
        
        关键词：
        - 弥娅、miya
        - 你好、hello
        - 解释、分析
        - 帮我、help
        - 任何问句
        """
        miya_keywords = ['弥娅', 'miya', '你好', 'hello', '解释', '分析',
                       '帮我', 'help', '?', '怎么', '如何', '为什么']
        return any(kw in input_text.lower() for kw in miya_keywords)
    
    def _route_to_miya(self, input_text: str, from_terminal: str):
        """路由到弥娅处理"""
        self.current_terminal = from_terminal
        
        # 在来源终端显示弥娅思考过程
        print(f"[弥娅] 收到来自 {from_terminal} 的请求")
        
        # 调用弥娅 AI
        response = self.master.call_miya(input_text)
        
        # 在来源终端显示响应
        print(f"\n{response}")
```

## 🎮 交互流程设计

### 场景 1: 用户要求执行新任务

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

### 场景 2: 子终端中弥娅接管

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

### 场景 3: 主终端全局调度

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

## 🔧 配置与扩展

### 终端类型配置

```json
{
  "terminal_types": {
    "local": {
      "name": "本地终端",
      "description": "本地CMD/PowerShell/Bash",
      "default_command": "cmd"
    },
    "ssh": {
      "name": "SSH终端",
      "description": "远程服务器连接",
      "config": {
        "host": "server.example.com",
        "username": "deploy",
        "key_path": "~/.ssh/id_rsa"
      }
    },
    "container": {
      "name": "容器终端",
      "description": "Docker容器",
      "config": {
        "image": "python:3.11",
        "container_name": "app"
      }
    }
  }
}
```

### 主终端配置

```json
{
  "master_terminal": {
    "show_thinking": true,
    "thinking_style": "verbose",
    "auto_monitor": true,
    "monitor_interval": 1
  }
}
```

## 🎯 实现步骤

### 第一阶段：核心架构
1. 创建 MasterTerminalController 类
2. 创建 ChildTerminalManager 类
3. 实现任务分配与调度算法
4. 实现弥娅思考过程显示

### 第二阶段：终端适配
1. 实现 LocalTerminal（本地终端）
2. 实现 SSHTerminal（SSH远程）
3. 实现 ContainerTerminal（容器）

### 第三阶段：弥娅接管
1. 实现 MiyaTakeoverMode 类
2. 支持在任意终端与弥娅交互
3. 思考过程在任何终端显示

### 第四阶段：集成到弥娅框架
1. 集成到 Personality（人格影响调度策略）
2. 集成到 Memory（记住用户偏好）
3. 集成 to Autonomy（自主优化任务分配）

## 📊 与现有架构的集成

### 使用现有组件

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

## 💡 设计优势

### 1. 清晰的职责分离
- 主终端：规划、调度、监控、交互
- 子终端：纯粹的任务执行

### 2. 弥娅全时在线
- 任何终端都能与弥娅交互
- 主终端显示详细思考过程
- 子终端在执行间隙响应

### 3. 可扩展性
- 轻松添加新的终端类型（WSL、容器等）
- 支持多种远程连接方式
- 终端池动态管理

### 4. 符合弥娅框架
- 集成人格、记忆、情绪、自主系统
- 保持架构一致性
- 支持蛛网式模块化

## 🚀 启动方式

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

## 📝 总结

这个架构设计实现了：

✅ **主终端总控** - 规划、调度、监控、交互
✅ **子终端执行** - 独立环境、专注执行
✅ **弥娅全时在线** - 任何终端都能交互
✅ **SSH连接支持** - 远程服务器管理
✅ **思考过程显示** - 主终端详细展示
✅ **符合弥娅框架** - 集成所有子系统
✅ **智能任务分配** - 自主优化执行策略

这正是用户想要的：主终端像你一样思考和规划，子终端专注执行，弥娅随时可交互！

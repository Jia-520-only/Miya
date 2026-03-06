# 弥娅命令行自主能力实现路线图

## 目标
让弥娅在命令行模式具备完全自主能力，能够：
1. 自动检测操作系统和 Linux 发行版
2. 主动发现和解决问题
3. 完全自主的工具调用链（无需用户明确请求）
4. 持续学习和记忆系统配置

## 当前状态分析

### 已具备的基础能力 ✅
- **工具系统**: 50+ 工具已注册在 `webnet/ToolNet/registry.py`
- **自主探索器**: `core/autonomous_explorer.py` 已实现基本探索框架
- **AI 客户端**: 支持 OpenAI Function Calling
- **高级编排器**: `hub/decision_hub.py` 中有 `AdvancedOrchestrator`（懒加载）

### 缺失的关键能力 ❌
1. **系统自动检测**: 没有自动检测 OS/发行版的机制
2. **主动问题发现**: 不具备主动检查代码/配置问题的能力
3. **完全自主决策**: 决策仍依赖用户请求触发
4. **自适应策略**: 没有基于系统环境自适应的工具选择
5. **lint 检查**: 不具备自动 lint 检查能力

---

## 实施方案（分4个阶段）

## 第一阶段：系统环境自动检测（1-2天）

### 目标
让弥娅能够自动识别运行环境，并据此调整行为。

### 新增模块

#### 1.1 `core/system_detector.py`
```python
class SystemDetector:
    """系统环境检测器"""
    def detect_os() -> str          # Windows/Linux/macOS
    def detect_distro() -> str      # Ubuntu/CentOS/Arch 等
    def detect_shell() -> str       # bash/zsh/pwsh
    def detect_package_manager() -> str  # apt/yum/pacman/npm/pip
    def detect_python_version() -> str
    def detect_node_version() -> str
    def get_environment_info() -> Dict  # 返回完整环境信息
```

**关键特性**:
- 跨平台支持（Windows/Linux/macOS）
- Linux 发行版检测（读取 `/etc/os-release`）
- 包管理器自动识别
- 缓存检测结果（避免重复检测）

#### 1.2 `core/environment_context.py`
```python
class EnvironmentContext:
    """环境上下文管理器"""
    def __init__(self, detector: SystemDetector):
        self.detector = detector
        self.env_info = self._build_env_context()

    def _build_env_context(self) -> Dict:
        """构建完整环境上下文"""
        return {
            'os': self.detector.detect_os(),
            'distro': self.detector.detect_distro(),
            'shell': self.detector.detect_shell(),
            'package_manager': self.detector.detect_package_manager(),
            'python': self.detector.detect_python_version(),
            'node': self.detector.detect_node_version(),
            'current_path': os.getcwd(),
            'home_dir': os.path.expanduser('~'),
        }

    def adapt_command(self, command: str) -> str:
        """根据环境适配命令"""
        # 例如：Windows: dir -> Linux: ls
        # Windows: pip install -> Linux: sudo apt install

    def suggest_tools(self) -> List[str]:
        """根据环境推荐工具"""
        # Ubuntu: apt, snap
        # macOS: brew
        # Windows: winget, choco
```

### 集成点
- `run/main.py` 初始化时自动运行系统检测
- 环境信息注入到 `DecisionHub` 的上下文
- 工具调用时自动应用环境适配

---

## 第二阶段：主动问题发现（2-3天）

### 目标
让弥娅能够主动发现代码/配置问题，无需用户请求。

### 新增模块

#### 2.1 `core/problem_scanner.py`
```python
class ProblemScanner:
    """问题扫描器"""
    def __init__(self, tool_adapter, ai_client):
        self.tool_adapter = tool_adapter
        self.ai_client = ai_client
        self.scanners = {
            'linter': LinterScanner(),
            'config': ConfigScanner(),
            'dependency': DependencyScanner(),
            'security': SecurityScanner(),
        }

    async def scan_all(self, path: str = '.') -> List[Problem]:
        """运行所有扫描器"""

    async def scan_lint(self) -> List[LinterError]:
        """扫描 lint 错误"""

    async def scan_dependencies(self) -> List[Problem]:
        """扫描依赖问题"""

    async def scan_configs(self) -> List[Problem]:
        """扫描配置问题"""

    def prioritize_problems(self, problems: List[Problem]) -> List[Problem]:
        """问题优先级排序"""
```

#### 2.2 `core/linter_scanner.py`
```python
class LinterScanner:
    """Linter 扫描器（对应 read_lints 工具）"""
    async def scan(self, path: str = '.') -> List[LinterError]:
        """扫描指定路径的 linter 错误"""

    def is_supported_path(self, path: str) -> bool:
        """判断路径是否支持 linter 检查"""

    def get_linter_types(self) -> List[str]:
        """获取可用的 linter 类型"""
```

#### 2.3 `core/auto_fixer.py`
```python
class AutoFixer:
    """自动修复器"""
    def __init__(self, problem_scanner, tool_adapter):
        self.scanner = problem_scanner
        self.tool_adapter = tool_adapter

    async def fix_problem(self, problem: Problem) -> FixResult:
        """修复单个问题"""

    async def fix_batch(self, problems: List[Problem]) -> List[FixResult]:
        """批量修复问题"""

    def can_fix(self, problem: Problem) -> bool:
        """判断问题是否可自动修复"""

    def create_fix_plan(self, problems: List[Problem]) -> FixPlan:
        """创建修复计划"""
```

### 集成点
- 在 `DecisionHub` 中添加后台扫描任务
- 每次对话后自动触发轻量级扫描
- 发现问题时主动提示用户

---

## 第三阶段：完全自主决策引擎（3-4天）

### 目标
让弥娅能够自主决策，无需用户明确请求。

### 新增模块

#### 3.1 `core/autonomous_engine.py`
```python
class AutonomousEngine:
    """自主决策引擎"""
    def __init__(
        self,
        problem_scanner: ProblemScanner,
        auto_fixer: AutoFixer,
        environment_context: EnvironmentContext,
        ai_client,
        memory_engine
    ):
        self.scanner = problem_scanner
        self.fixer = auto_fixer
        self.env_context = environment_context
        self.ai_client = ai_client
        self.memory = memory_engine

    async def decide_action(self, context: Dict) -> Decision:
        """根据上下文自主决策"""
        # 分析当前状态
        # 评估可选行动
        # 选择最优行动

    async def execute_decision(self, decision: Decision) -> ExecutionResult:
        """执行决策"""

    async def continuous_improvement(self):
        """持续改进循环"""
        while True:
            # 1. 扫描问题
            problems = await self.scanner.scan_all()

            # 2. 评估优先级
            prioritized = self.scanner.prioritize_problems(problems)

            # 3. 自主修复
            for problem in prioritized[:3]:  # 每次最多修复3个
                if self.fixer.can_fix(problem):
                    result = await self.fixer.fix_problem(problem)
                    if result.success:
                        await self._record_fix(problem, result)

            # 4. 学习和记忆
            await self._learn_from_history()

            await asyncio.sleep(300)  # 5分钟循环一次

    async def _record_fix(self, problem: Problem, result: FixResult):
        """记录修复历史"""

    async def _learn_from_history(self):
        """从历史中学习"""
```

#### 3.2 `core/decision.py`
```python
@dataclass
class Decision:
    """决策对象"""
    action: str                    # 动作类型
    description: str               # 描述
    reasoning: str                 # 理由
    confidence: float              # 置信度
    tools_needed: List[str]       # 需要的工具
    estimated_time: float          # 预计耗时（秒）
    risk_level: str               # 风险等级（低/中/高）
    requires_approval: bool       # 是否需要用户批准

@dataclass
class FixResult:
    """修复结果"""
    success: bool
    problem: Problem
    action_taken: str
    output: str
    time_taken: float
```

### 增强现有模块

#### 3.3 增强 `core/autonomous_explorer.py`
```python
class AutonomousExplorer:
    # 新增方法
    async def autonomous_task(self, goal: str) -> TaskResult:
        """自主执行任务（无需用户指导）"""

    async def self_directed_exploration(self, context: Dict) -> ExplorationPlan:
        """自导向探索（自主决定探索方向）"""

    async def adaptive_strategy(self, feedback: Dict):
        """自适应策略调整"""
```

### 集成点
- `DecisionHub` 集成 `AutonomousEngine`
- 后台运行 `continuous_improvement` 任务
- 前台交互时优先使用自主决策

---

## 第四阶段：学习与记忆增强（2-3天）

### 目标
让弥娅能够记住系统配置，从错误中学习。

### 新增模块

#### 4.1 `memory/system_memory.py`
```python
class SystemMemory:
    """系统配置记忆"""
    def __init__(self, storage_client):
        self.storage = storage_client

    async def remember_config(self, path: str, config: Dict):
        """记住配置"""

    async def recall_config(self, path: str) -> Optional[Dict]:
        """回忆配置"""

    async def remember_fix(self, problem: Problem, solution: FixResult):
        """记住修复方案"""

    async def get_similar_problems(self, problem: Problem) -> List[Problem]:
        """获取相似问题"""

    async def learn_pattern(self, problem: Problem, fix: FixResult):
        """学习修复模式"""
```

#### 4.2 `memory/learning_engine.py`
```python
class LearningEngine:
    """学习引擎"""
    def __init__(self, system_memory, ai_client):
        self.memory = system_memory
        self.ai_client = ai_client

    async def extract_patterns(self, history: List[FixResult]) -> List[Pattern]:
        """从历史中提取模式"""

    async def suggest_fix(self, problem: Problem) -> Optional[FixSuggestion]:
        """基于历史建议修复方案"""

    async def update_confidence(self, pattern: Pattern, success: bool):
        """更新模式置信度"""
```

### 集成点
- 系统记忆作为独立存储（Milvus/Neo4j）
- `AutoFixer` 在修复前查询相似历史
- `DecisionHub` 在决策时应用学习到的模式

---

## 配置文件

### `config/terminal_autonomy_config.json`
```json
{
  "autonomous_mode": {
    "enabled": true,
    "continuous_scan_interval": 300,
    "max_fixes_per_cycle": 3,
    "risk_threshold": "medium"
  },
  "problem_detection": {
    "linter_enabled": true,
    "dependency_check_enabled": true,
    "config_validation_enabled": true,
    "security_scan_enabled": false
  },
  "learning": {
    "enabled": true,
    "pattern_similarity_threshold": 0.8,
    "min_history_for_learning": 10
  },
  "auto_fix": {
    "enabled": true,
    "require_approval_for": ["high", "critical"],
    "dry_run": false,
    "backup_before_fix": true
  }
}
```

---

## 工作流程

### 完整的自主工作流程
```
1. 系统启动
   ↓
2. SystemDetector 检测环境
   ↓
3. EnvironmentContext 构建上下文
   ↓
4. AutonomousEngine 启动后台循环
   ↓
5. 每次交互
   ├─ DecisionHub 接收用户输入
   ├─ 评估是否需要主动扫描
   ├─ 生成响应（使用 AI + 工具）
   └─ 存储 到记忆
   ↓
6. 后台循环（每5分钟）
   ├─ ProblemScanner 扫描问题
   ├─ AutonomousEngine 决策行动
   ├─ AutoFixer 执行修复
   └─ SystemMemory 记录历史
   ↓
7. 学习改进
   ├─ LearningEngine 提取模式
   └─ 更新决策策略
```

---

## 关键设计原则

### 1. 安全性
- 高风险操作需要用户批准
- 修复前自动备份
- 回滚机制

### 2. 可控性
- 配置文件控制所有行为
- 可随时启用/禁用自主功能
- 用户可手动覆盖决策

### 3. 透明性
- 所有决策记录 reasoning
- 用户可查看决策历史
- 详细的执行日志

### 4. 渐进式
- 从低风险操作开始
- 根据成功率逐步扩大权限
- 持续学习改进

---

## 测试计划

### 单元测试
- SystemDetector 各平台测试
- ProblemScanner 各类问题检测
- AutoFixer 修复逻辑

### 集成测试
- 完整自主流程测试
- 跨平台兼容性测试
- 性能测试（扫描耗时）

### 用户测试
- 用户体验测试
- 误报/漏报测试
- 学习效果测试

---

## 预期效果

### 实现后的能力
1. **自动环境适配**: 在任何系统上都能正常工作
2. **主动发现问题**: 不需要用户报告，主动检测问题
3. **自主修复**: 低风险问题自动修复
4. **持续学习**: 从历史中学习，越来越聪明
5. **完全自主**: 真正具备"想做什么"的能力

### 与 Claude 能力对比
| 能力 | Claude | 弥娅（实现后） |
|------|--------|----------------|
| 代码理解 | ✅ | ✅ |
| 工具调用 | ✅ | ✅ |
| 主动发现 | ✅ | ✅ |
| 自主修复 | ✅ | ✅ |
| 系统自适应 | ❌ | ✅ |
| 持续学习 | ❌ | ✅ |
| 人格情绪 | ❌ | ✅ |
| 记忆系统 | ❌ | ✅ |

---

## 风险与挑战

### 技术挑战
1. **误报问题**: 扫描器可能误报，需要高准确率
2. **错误修复**: 自动修复可能引入新问题
3. **性能影响**: 后台扫描可能影响系统性能

### 解决方案
1. 置信度阈值：只有高置信度的问题才自动修复
2. A/B 测试：在修复前先测试
3. 资源限制：限制扫描频率和并发数

---

## 下一步行动

### 立即开始（第一周）
1. 创建 `core/system_detector.py` 模块
2. 创建 `core/environment_context.py` 模块
3. 编写单元测试
4. 集成到 `run/main.py`

### 后续迭代
- 根据测试反馈调整设计
- 逐步实现后续阶段
- 持续优化性能和准确率

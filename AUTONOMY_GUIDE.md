# 弥娅自主能力使用指南

## 快速开始

### 1. 基本使用

```python
from core.autonomy_manager import get_autonomy_manager

# 初始化
manager = get_autonomy_manager()
manager.initialize()

# 手动触发改进
result = await manager.manual_improvement(max_fixes=10, auto_approve=False)

# 查看结果
print(f"发现问题: {result['problems_found']}")
print(f"决策数: {result['decisions_made']}")
print(f"尝试修复: {result['fixes_attempted']}")
print(f"成功修复: {result['fixes_successful']}")
print(f"失败修复: {result['fixes_failed']}")

# 关闭
manager.shutdown()
```

### 2. 自动改进模式

```python
# 启用自动改进（每 5 分钟）
manager.enable_auto_improvement(interval=300)

# 系统会自动在后台运行，持续改进

# 停止自动改进
manager.disable_auto_improvement()
```

### 3. 查看状态

```python
# 获取当前状态
status = manager.get_status()

print(f"初始化状态: {status['initialized']}")
print(f"自动改进: {status['auto_improvement_enabled']}")
print(f"总决策数: {status['engine']['total_decisions']}")
print(f"自动决策: {status['engine']['auto_decisions']}")
print(f"成功修复: {status['engine']['successful_fixes']}")
```

### 4. 生成报告

```python
# 生成完整报告
report = manager.generate_report()

print(f"系统: {report['system']['os_name']}")
print(f"架构: {report['system']['arch']}")
print(f"Python: {report['system']['python_version']}")

print("\n自主能力:")
print(f"  运行状态: {report['autonomy']['status']['engine']['is_running']}")
print(f"  总决策: {report['autonomy']['engine_report']['total_decisions']}")
print(f"  自动批准: {report['autonomy']['engine_report']['auto_approved']}")

print("\n最近决策:")
for decision in report['autonomy']['recent_decisions']:
    print(f"  - {decision['decision_type']}: {decision['reasoning']}")
```

### 5. 优化策略

```python
# 分析并优化决策策略
report = manager.optimize_decisions()

print(f"当前策略: {report['strategy']}")
print(f"分析模式数: {report['patterns_analyzed']}")

print("\n优化建议:")
for rec in report['recommendations']:
    print(f"  - {rec}")

print("\n风险调整:")
for key, value in report['risk_adjustments'].items():
    print(f"  - {key}: {value}")
```

## 风险等级说明

弥娅使用五级风险评估系统：

| 风险等级 | 值 | 说明 | 行为 |
|---------|-----|------|------|
| SAFE | 1 | 安全，可自动执行 | ✅ 自动批准并执行 |
| LOW | 2 | 低风险，可自动执行 | ✅ 自动批准并执行 |
| MEDIUM | 3 | 中等风险，需要记录 | ✅ 自动批准并执行 |
| HIGH | 4 | 高风险，需要用户确认 | ⚠️ 需要用户确认 |
| CRITICAL | 5 | 极高风险，拒绝执行 | ❌ 拒绝执行 |

## 决策类型说明

| 决策类型 | 说明 |
|---------|------|
| AUTO_FIX | 自动修复 |
| MANUAL_REVIEW | 人工审查 |
| ESCALATE | 上报给用户 |
| IGNORE | 忽略 |
| DEFER | 延后处理 |

## 配置选项

### 自动改进配置

```python
# 启用自动改进
manager.enable_auto_improvement(
    interval=300,  # 扫描间隔（秒），默认 5 分钟
)

# 自主引擎配置
engine = manager.engine
engine.auto_approve_threshold = RiskLevel.LOW  # 自动批准阈值
engine.improvement_interval = 300  # 改进间隔
engine.max_improvements_per_cycle = 5  # 每次最多修复数
```

### 风险评估规则

弥娅使用以下规则评估风险：

1. **问题严重程度**
   - critical: +3
   - high: +2
   - medium: +1

2. **问题类型**
   - security: +2
   - dependency: +1

3. **修复动作**
   - delete/remove: +2
   - modify/change: +1

4. **文件路径**
   - 关键文件: +3
   - 包含敏感词: +2

## 实际使用示例

### 示例 1: 启动弥娅并开启自动改进

```python
import asyncio
from core.autonomy_manager import get_autonomy_manager

async def main():
    # 初始化
    manager = get_autonomy_manager()
    manager.initialize()

    print("弥娅自主能力已初始化")

    # 启用自动改进
    manager.enable_auto_improvement(interval=300)
    print("自动改进已启用，每 5 分钟扫描一次")

    # 保持运行
    try:
        while True:
            await asyncio.sleep(60)
            # 每 60 秒检查一次状态
            status = manager.get_status()
            print(f"总决策: {status['engine']['total_decisions']}, "
                  f"成功修复: {status['engine']['successful_fixes']}")
    except KeyboardInterrupt:
        print("\n正在关闭...")
        manager.shutdown()
        print("已关闭")

if __name__ == "__main__":
    asyncio.run(main())
```

### 示例 2: 手动触发一次改进

```python
import asyncio
from core.autonomy_manager import get_autonomy_manager

async def main():
    manager = get_autonomy_manager()
    manager.initialize()

    print("开始手动改进...")
    result = await manager.manual_improvement(
        max_fixes=10,
        auto_approve=False  # 不自动批准高风险操作
    )

    print(f"\n改进结果:")
    print(f"  扫描: {'✅' if result['scanned'] else '❌'}")
    print(f"  发现问题: {result['problems_found']}")
    print(f"  做出决策: {result['decisions_made']}")
    print(f"  尝试修复: {result['fixes_attempted']}")
    print(f"  成功修复: {result['fixes_successful']}")
    print(f"  失败修复: {result['fixes_failed']}")

    if result['errors']:
        print(f"\n错误:")
        for error in result['errors']:
            print(f"  - {error}")

    manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

### 示例 3: 优化决策策略

```python
import asyncio
from core.autonomy_manager import get_autonomy_manager

async def main():
    manager = get_autonomy_manager()
    manager.initialize()

    print("分析决策策略...")
    report = manager.optimize_decisions()

    print(f"\n策略: {report['strategy']}")
    print(f"分析模式: {report['patterns_analyzed']}")

    print("\n建议:")
    for rec in report['recommendations']:
        print(f"  • {rec}")

    print("\n性能指标:")
    for key, value in report['performance_metrics'].items():
        print(f"  • {key}: {value}")

    manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

## 与主程序集成

### 在 run/main.py 中集成

```python
from core.autonomy_manager import get_autonomy_manager

class MiyaAssistant:
    def __init__(self):
        # ... 现有初始化代码 ...

        # 初始化自主能力
        self.autonomy = get_autonomy_manager()
        self.autonomy.initialize()

        # 可选：启用自动改进
        # self.autonomy.enable_auto_improvement(interval=300)

    async def process_command(self, command: str):
        # ... 现有命令处理逻辑 ...

        # 如果用户要求自动改进
        if "自动改进" in command or "auto improve" in command:
            result = await self.autonomy.manual_improvement(
                max_fixes=10,
                auto_approve=True
            )
            return f"改进完成：发现 {result['problems_found']} 个问题，" \
                   f"修复 {result['fixes_successful']} 个"

        # 如果用户要求查看状态
        if "状态" in command or "status" in command:
            status = self.autonomy.get_status()
            return self._format_status(status)

    def shutdown(self):
        # ... 现有关闭代码 ...
        self.autonomy.shutdown()
```

## 监控和日志

### 决策日志

弥娅会记录所有决策，包括：

- 决策 ID
- 问题 ID
- 决策类型
- 风险等级
- 推理
- 执行结果
- 时间戳

### 统计数据

- 总决策数
- 自动决策数
- 人工决策数
- 成功修复数
- 失败修复数
- 改进次数

### 查看决策历史

```python
# 获取最近的决策
decisions = manager.engine.get_recent_decisions(limit=10)

for decision in decisions:
    print(f"{decision.timestamp}: {decision.decision_type.value}")
    print(f"  风险: {decision.risk_level.name}")
    print(f"  推理: {decision.reasoning}")
    print(f"  结果: {decision.result}")
```

## 故障排除

### 问题：扫描速度慢

**解决方案**：
- 增加 `improvement_interval`
- 减少 `max_improvements_per_cycle`
- 排除不需要扫描的目录

### 问题：误报过多

**解决方案**：
- 调整 `auto_approve_threshold` 为更保守的级别
- 修改风险评估规则
- 添加白名单

### 问题：修复失败

**解决方案**：
- 检查备份目录权限
- 查看错误日志
- 使用 `auto_approve=False` 手动确认

## 最佳实践

1. **首次使用**
   - 从手动改进开始
   - 设置 `auto_approve=False`
   - 观察决策结果

2. **生产环境**
   - 使用保守的风险阈值
   - 定期查看决策报告
   - 保留完整的备份

3. **开发环境**
   - 可以使用激进策略
   - 启用自动改进
   - 充分利用学习能力

4. **持续优化**
   - 定期运行 `optimize_decisions()`
   - 查看优化建议
   - 调整策略参数

## 总结

弥娅的自主能力让她能够：

- ✅ **自动发现问题** - 扫描代码、配置、依赖
- ✅ **智能决策** - 基于风险评估自动决策
- ✅ **持续改进** - 后台自动运行
- ✅ **学习优化** - 从历史中学习最佳实践
- ✅ **完整监控** - 详细的统计和报告

让弥娅成为你的智能助手，帮助你维护和改进代码！

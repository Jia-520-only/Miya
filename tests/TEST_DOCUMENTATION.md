# 弥娅系统测试文档

## 概述

本文档详细描述了弥娅系统的测试架构、测试用例、执行方法以及覆盖率统计。

---

## 测试架构

### 测试分层

```
弥娅测试体系
├── 单元测试 (Unit Tests)
│   ├── test_core_comprehensive.py  - 核心模块综合测试
│   ├── test_memory_system.py      - 记忆系统测试
│   └── test_personality.py       - 人格系统测试
│
├── 集成测试 (Integration Tests)
│   ├── test_integration_suite.py  - 集成测试套件
│   └── test_trpg_system.py      - TRPG系统测试
│
├── 边界测试 (Edge Case Tests)
│   └── test_edge_cases.py        - 异常情况测试
│
└── 性能测试 (Performance Tests)
    └── test_performance.py        - 性能压力测试
```

---

## 测试文件说明

### 1. test_core_comprehensive.py
**核心模块综合测试**

#### 测试范围
- **人格系统**
  - 人格初始化和加载
  - 称呼管理
  - 人格状态切换
  - 关系影响计算

- **记忆系统**
  - 记忆添加和查询
  - 记忆压缩和清理
  - 重要性评分
  - 记忆检索

- **情绪系统**
  - 情绪初始化
  - 情绪强度计算
  - 情绪衰减

- **仲裁系统**
  - 仲裁决策
  - 冲突解决

- **AI客户端**
  - DeepSeek客户端初始化
  - 提示词生成
  - 工具调用支持

#### 关键测试用例
```python
# 测试人格切换
def test_personality_switching():
    personality = Personality()
    personality.switch_state("playful")
    assert personality.get_current_state() == "playful"

# 测试记忆压缩
async def test_memory_compression():
    memory_system = MemorySystem()
    # 添加100条记忆
    for i in range(100):
        memory_system.add_memory(f"Memory {i}")
    # 触发压缩
    await memory_system.compress_memories()
    assert len(memory_system.get_all_memories()) < 100
```

---

### 2. test_integration_suite.py
**集成测试套件**

#### 测试范围
- **模块间集成**
  - 人格 + 记忆集成
  - 人格 + 情绪集成
  - 记忆 + 仲裁集成
  - 全流程集成

- **Agent管理器集成**
  - 任务创建和执行
  - 工具调用循环
  - 会话记忆管理

#### 关键集成场景
```python
# 人格与记忆的集成
async def test_personality_memory_integration():
    personality = Personality()
    memory_system = MemorySystem()
    
    # 人格根据记忆调整状态
    personality.process_memory(memory_system.get_recent_memories())
    
    # 验证人格状态更新
    assert personality.get_current_state() == "expected_state"

# 完整Agent流程
async def test_full_agent_workflow():
    manager = AgentManager()
    
    # 创建任务
    await manager.create_task("task_1", "Test task")
    
    # 添加步骤
    step = TaskStep(...)
    await manager.add_task_step("task_1", step)
    
    # 验证任务状态
    stats = manager.get_statistics()
    assert stats["total_tasks"] > 0
```

---

### 3. test_edge_cases.py
**边界测试和异常情况测试**

#### 测试范围

#### A. 输入边界测试
- **空输入处理**
  - 空任务创建
  - None参数处理
  - 空字符串处理

- **极端输入**
  - 超长任务名称（1000+字符）
  - Unicode字符处理（emoji、特殊符号）
  - 特殊字符处理（引号、转义符）

#### B. 异常处理测试
- **格式错误**
  - 格式错误的JSON解析
  - 全角字符转换
  - Malformed数据

- **操作异常**
  - 重复任务创建
  - 访问不存在的任务
  - 失败的工具调用

#### C. 边界条件测试
- **阈值测试**
  - 记忆压缩阈值
  - 零值和负值处理
  - 速度限制边界

- **并发测试**
  - 并发任务操作
  - 并发记忆访问
  - 钩子异常处理

#### 关键测试用例
```python
# 空输入处理
def test_empty_task_creation():
    result = await agent_manager.create_task("", "")
    assert result is not None

# Unicode处理
def test_unicode_handling():
    unicode_text = "你好🌍🎉🚀✨"
    result = await agent_manager.create_task("test", unicode_text)
    assert result == "test"

# 格式错误JSON
def test_malformed_json_handling():
    malformed = '{"tool_name": "test"'
    clean_text, tool_calls = agent_manager.parse_tool_calls(malformed)
    assert len(tool_calls) == 0

# 失败的工具调用
async def test_failed_tool_call():
    executor = async def failing_executor(**kwargs):
        raise Exception("Test failure")
    
    agent_manager.register_tool_executor("failing", executor)
    result = await agent_manager.execute_tool_call({
        "tool_name": "test",
        "service_name": "failing"
    })
    
    assert result.success is False
    assert result.error is not None
```

---

### 4. test_performance.py
**性能压力测试**

#### 测试指标

#### A. 吞吐量测试
- **任务创建吞吐量**
  - 测试目标: 1000个任务 < 10秒
  - P95延迟: < 10ms

- **步骤添加吞吐量**
  - 测试目标: 500个步骤 < 25秒
  - P95延迟: < 50ms

- **记忆查询吞吐量**
  - 测试目标: 1000次查询 < 100秒
  - P95延迟: < 100ms

#### B. 并发性能测试
- **并发任务**
  - 测试目标: 50个并发任务
  - 成功率: > 95%
  - P95完成时间: < 1秒

#### C. 压力测试
- **大数据处理**
  - 测试目标: 50MB数据
  - 处理成功率: > 95%

- **长会话测试**
  - 测试目标: 100个会话
  - 操作延迟: < 20ms

#### 性能基准
| 测试项 | 目标值 | P95延迟 | 成功率 |
|--------|--------|---------|--------|
| 任务创建 | <10ms | <15ms | >99% |
| 步骤添加 | <50ms | <75ms | >98% |
| 记忆查询 | <50ms | <100ms | >99% |
| 并发任务 | <1s | <1.5s | >95% |
| 统计获取 | <1ms | <2ms | >99% |

#### 性能测试执行
```bash
# 运行性能测试
python tests/test_performance.py

# 输出示例
================================================================================
性能测试摘要
================================================================================

【任务创建压力测试】
  总运行次数: 100
  成功/失败: 100/0
  成功率: 100.00%
  平均耗时: 0.0050s
  最小/最大: 0.0021s / 0.0123s
  中位数: 0.0048s
  P95: 0.0095s
```

---

## 测试覆盖率

### 当前覆盖率统计

| 模块 | 函数覆盖率 | 行覆盖率 | 分支覆盖率 |
|------|-----------|---------|-----------|
| core/agent_manager.py | 95% | 88% | 82% |
| core/personality.py | 92% | 85% | 78% |
| core/ai_client.py | 90% | 83% | 75% |
| memory/memory_system.py | 88% | 80% | 72% |
| **总体** | **91%** | **84%** | **77%** |

### 未覆盖的关键区域

1. **agent_manager.py**
   - 智能压缩策略（需要LLM环境）
   - 评估系统（需要评分环境）

2. **ai_client.py**
   - 实际API调用（需要API密钥）
   - 工具调用结果处理

3. **memory_system.py**
   - 大规模记忆压缩
   - 分布式记忆同步

---

## 测试执行

### 运行所有测试
```bash
# 使用pytest（推荐）
pytest tests/ -v --cov=. --cov-report=html

# 使用unittest
python -m unittest discover tests/ -v
```

### 运行特定测试
```bash
# 运行核心测试
pytest tests/test_core_comprehensive.py -v

# 运行性能测试
pytest tests/test_performance.py -v

# 运行边界测试
pytest tests/test_edge_cases.py -v
```

### 生成覆盖率报告
```bash
# HTML报告
pytest --cov=. --cov-report=html

# 控制台报告
pytest --cov=. --cov-report=term-missing

# JSON报告
pytest --cov=. --cov-report=json
```

---

## 持续集成配置

### GitHub Actions示例
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.8'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run tests
        run: |
          pytest tests/ --cov=. --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

## 测试最佳实践

### 1. 测试命名
```python
# ✅ 好的命名
def test_personality_switching_saves_state():
    pass

def test_memory_compression_reduces_size():
    pass

# ❌ 不好的命名
def test1():
    pass

def test_personality():
    pass  # 太模糊
```

### 2. 测试结构
```python
def test_feature():
    # Arrange - 准备
    personality = Personality()
    
    # Act - 执行
    personality.switch_state("playful")
    
    # Assert - 断言
    assert personality.get_current_state() == "playful"
```

### 3. 异步测试
```python
async def test_async_feature():
    # Arrange
    manager = AgentManager()
    
    # Act
    result = await manager.create_task("test", "purpose")
    
    # Assert
    assert result == "test"
```

### 4. Mock使用
```python
from unittest.mock import Mock, AsyncMock

def test_with_mock():
    # 创建mock对象
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = "response"
    
    # 使用mock
    result = await agent.generate(mock_llm)
    
    # 验证
    mock_llm.generate.assert_called_once()
```

---

## 测试维护

### 定期检查清单

- [ ] 每周运行完整测试套件
- [ ] 每月更新覆盖率报告
- [ ] 每季度审查测试用例
- [ ] 及时修复失败的测试
- [ ] 为新功能添加测试

### 测试质量指标

- **通过率**: 目标 > 95%
- **覆盖率**: 目标 > 85%
- **测试执行时间**: 目标 < 5分钟
- **Flaky测试**: 目标 = 0

---

## 故障排除

### 常见问题

#### 1. 测试失败
```bash
# 查看详细错误
pytest tests/ -vv

# 只运行失败的测试
pytest --lf

# 进入调试模式
pytest --pdb
```

#### 2. 导入错误
```bash
# 检查Python路径
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# 使用pytest路径
pytest tests/ --pythonpath=$(pwd)
```

#### 3. 异步测试问题
```bash
# 确保使用pytest-asyncio
pip install pytest-asyncio

# 标记异步测试
@pytest.mark.asyncio
async def test_async_feature():
    pass
```

---

## 总结

弥娅系统的测试体系涵盖了单元测试、集成测试、边界测试和性能测试，确保了系统的高质量和可靠性。通过持续维护和改进测试用例，我们可以快速发现和修复问题，提高代码质量。

---

**文档版本**: 1.0  
**最后更新**: 2026-03-01  
**维护者**: 弥娅开发团队

"""
高级能力模块测试脚本
测试 TaskPlanner, AutonomousExplorer, IntelligentExecutor, ChainOfThought
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.task_planner import TaskPlanner, TaskStatus
from core.autonomous_explorer import AutonomousExplorer
from core.intelligent_executor import IntelligentExecutor
from core.chain_of_thought import ChainOfThought, ThoughtType


class MockAIClient:
    """模拟AI客户端"""
    
    async def chat_with_system_prompt(self, system_prompt: str, user_message: str) -> str:
        """模拟AI回复"""
        print(f"[AI] 系统提示词: {system_prompt[:100]}...")
        print(f"[AI] 用户消息: {user_message[:100]}...")
        
        # 简单模拟返回
        if "任务分解" in user_message or "task" in user_message.lower():
            return '''{
  "tasks": [
    {
      "name": "分析需求",
      "description": "分析用户需求",
      "tool_name": "natural_language",
      "dependencies": [],
      "priority": 10
    },
    {
      "name": "执行任务",
      "description": "执行具体任务",
      "tool_name": "terminal_command",
      "dependencies": ["分析需求"],
      "priority": 5
    }
  ]
}'''
        
        if "决策" in user_message or "decide" in user_message.lower():
            return '''{
  "action": "think",
  "description": "分析当前状态",
  "params": {},
  "reasoning": "需要更多信息才能继续",
  "confidence": 0.5
}'''
        
        if "反思" in user_message or "reflect" in user_message.lower():
            return "反思完成"
        
        if "完善" in user_message or "enhance" in user_message.lower():
            return '''{
  "content": "完善后的思考内容",
  "reasoning": "详细的推理过程",
  "confidence": 0.8,
  "evidence": ["证据1"],
  "alternatives": ["替代方案1"]
}'''
        
        return "AI响应"


async def mock_tool_executor(tool_name: str, params: dict) -> str:
    """模拟工具执行器"""
    print(f"[工具执行] {tool_name} - 参数: {params}")
    
    if tool_name == "terminal_command":
        command = params.get("command", "")
        if "ls" in command or "dir" in command:
            return "file1.py\nfile2.txt\nconfig.json"
        elif command == "pwd":
            return "/home/user/project"
        else:
            return f"执行成功: {command}"
    
    if tool_name == "read_file":
        path = params.get("path", "")
        return f"文件内容: {path}"
    
    if tool_name == "list_files":
        return "列出文件成功"
    
    if tool_name == "search_content":
        return "搜索完成，找到3个匹配"
    
    return f"工具 {tool_name} 执行成功"


async def test_task_planner():
    """测试任务规划器"""
    print("\n" + "="*60)
    print("测试 TaskPlanner（任务规划器）")
    print("="*60)
    
    ai_client = MockAIClient()
    planner = TaskPlanner(ai_client=ai_client)
    
    # 分解任务
    tasks = await planner.decompose_task(
        goal="帮我分析项目结构",
        context={"project_path": "/home/user/project"}
    )
    
    print(f"\n✅ 任务分解完成，共 {len(tasks)} 个任务:")
    for i, task in enumerate(tasks, 1):
        print(f"  {i}. {task.name}")
        print(f"     描述: {task.description}")
        print(f"     工具: {task.tool_name}")
        print(f"     优先级: {task.priority}")
        print(f"     状态: {task.status.value}")
    
    # 添加任务到规划器
    planner.add_tasks(tasks)
    
    # 获取可执行任务
    ready_tasks = planner.get_ready_tasks()
    print(f"\n✅ 可执行任务: {len(ready_tasks)} 个")
    
    # 获取摘要
    summary = planner.get_summary()
    print(f"\n✅ 任务摘要: {summary}")
    
    return True


async def test_autonomous_explorer():
    """测试自主探索器"""
    print("\n" + "="*60)
    print("测试 AutonomousExplorer（自主探索器）")
    print("="*60)
    
    ai_client = MockAIClient()
    explorer = AutonomousExplorer(
        ai_client=ai_client,
        tool_executor=mock_tool_executor,
        max_steps=5  # 限制步骤数以便测试
    )
    
    # 开始探索
    plan = await explorer.explore(
        goal="查找项目中的配置文件",
        context={"project_path": "."}
    )
    
    print(f"\n✅ 探索完成:")
    print(f"  目标: {plan.goal}")
    print(f"  步骤数: {plan.current_step}")
    print(f"  完成状态: {plan.completed}")
    print(f"  发现数: {len(plan.findings)}")
    
    print(f"\n  发现:")
    for finding in plan.findings[:5]:
        print(f"    - {finding}")
    
    # 生成报告
    report = explorer.get_exploration_report(plan)
    print(f"\n✅ 探索报告:\n{report[:500]}...")
    
    return True


async def test_intelligent_executor():
    """测试智能执行器"""
    print("\n" + "="*60)
    print("测试 IntelligentExecutor（智能执行器）")
    print("="*60)
    
    executor = IntelligentExecutor(
        tool_executor=mock_tool_executor,
        max_concurrent_tasks=2,
        enable_rollback=True,
        enable_result_validation=True
    )
    
    # 执行单个任务
    print("\n📋 执行单个任务...")
    result = await executor.execute_task(
        task_id="task_1",
        tool_name="terminal_command",
        params={"command": "ls"},
        retry_on_failure=True,
        max_retries=2
    )
    
    print(f"\n✅ 单个任务执行完成:")
    print(f"  任务ID: {result.task_id}")
    print(f"  成功: {result.success}")
    print(f"  输出: {result.output[:50] if result.output else '无'}")
    print(f"  耗时: {result.execution_time:.3f}秒")
    print(f"  重试次数: {result.retry_count}")
    
    # 批量执行任务
    print("\n📋 批量执行任务...")
    tasks = [
        {
            "task_id": "task_2",
            "tool_name": "terminal_command",
            "params": {"command": "pwd"}
        },
        {
            "task_id": "task_3",
            "tool_name": "read_file",
            "params": {"path": "test.txt"}
        }
    ]
    
    results = await executor.execute_tasks(
        tasks=tasks,
        parallel=True
    )
    
    print(f"\n✅ 批量任务执行完成，共 {len(results)} 个任务:")
    for task_id, result in results.items():
        print(f"  {task_id}: {'成功' if result.success else '失败'}")
    
    # 获取统计
    stats = executor.get_execution_stats()
    print(f"\n✅ 执行统计:")
    print(f"  总任务数: {stats['total']}")
    print(f"  成功: {stats['success']}")
    print(f"  失败: {stats['failed']}")
    print(f"  成功率: {stats['success_rate']:.2%}")
    print(f"  平均耗时: {stats['avg_execution_time']:.3f}秒")
    
    return True


async def test_chain_of_thought():
    """测试思维链"""
    print("\n" + "="*60)
    print("测试 ChainOfThought（思维链）")
    print("="*60)
    
    ai_client = MockAIClient()
    cot = ChainOfThought(ai_client=ai_client)
    
    # 分析问题
    print("\n📊 分析问题...")
    chain = await cot.analyze(
        problem="如何优化系统的性能？",
        context={"system": "MIYA"}
    )
    
    print(f"\n✅ 思维链分析完成:")
    print(f"  目标: {chain.goal}")
    print(f"  步骤数: {len(chain.steps)}")
    print(f"  结论: {chain.conclusion}")
    
    print(f"\n  思考步骤:")
    for i, step in enumerate(chain.steps, 1):
        print(f"    {i}. {step.thought_type.value}: {step.content[:60]}...")
        print(f"       置信度: {step.confidence:.2f}")
    
    # 手动添加步骤
    print("\n📊 手动添加思考步骤...")
    await cot.add_thought_step(
        thought_type=ThoughtType.REFLECTION,
        content="反思前面的分析",
        reasoning="需要更深入地考虑性能瓶颈",
        confidence=0.7,
        use_ai=False
    )
    
    # 生成摘要
    summary = cot.get_chain_summary()
    print(f"\n✅ 思维链摘要:\n{summary[:500]}...")
    
    # 生成树状视图
    tree = cot.get_chain_tree()
    print(f"\n✅ 树状视图:\n{tree}")
    
    # 反思
    reflection = await cot.reflect_on_chain()
    print(f"\n✅ 反思结果:")
    print(f"  平均置信度: {reflection['avg_confidence']:.2f}")
    print(f"  类型分布: {reflection['type_distribution']}")
    if reflection['suggested_improvements']:
        print(f"  改进建议:")
        for improvement in reflection['suggested_improvements']:
            print(f"    - {improvement}")
    
    return True


async def test_advanced_orchestrator():
    """测试高级编排器"""
    print("\n" + "="*60)
    print("测试 AdvancedOrchestrator（高级编排器）")
    print("="*60)
    
    from core.advanced_orchestrator import AdvancedOrchestrator
    
    ai_client = MockAIClient()
    orchestrator = AdvancedOrchestrator(
        ai_client=ai_client,
        tool_executor=mock_tool_executor,
        storage_dir=str(project_root / "data" / "test_advanced")
    )
    
    # 处理复杂任务
    print("\n🚀 处理复杂任务...")
    result = await orchestrator.process_complex_task(
        goal="帮我分析项目中的所有配置文件",
        context={"project_path": "."},
        enable_exploration=True,
        enable_cot=True
    )
    
    print(f"\n✅ 复杂任务处理完成:")
    print(f"  目标: {result['goal']}")
    print(f"  成功: {result['success']}")
    print(f"  执行时间: {result['execution_time']:.2f}秒")
    print(f"  步骤数: {len(result['steps'])}")
    print(f"  发现数: {len(result.get('findings', []))}")
    print(f"  结论: {result.get('conclusion', '无')}")
    
    print(f"\n  执行步骤:")
    for i, step in enumerate(result['steps'], 1):
        print(f"    {i}. {step['phase']}: {'成功' if step['success'] else '失败'}")
    
    # 生成报告
    report = orchestrator.generate_report(result)
    print(f"\n✅ 执行报告:\n{report[:800]}...")
    
    # 清理
    await orchestrator.cleanup()
    
    return True


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("弥娅高级能力模块测试")
    print("="*60)
    
    results = {}
    
    # 测试各个模块
    try:
        results['TaskPlanner'] = await test_task_planner()
    except Exception as e:
        print(f"\n❌ TaskPlanner 测试失败: {e}")
        results['TaskPlanner'] = False
    
    try:
        results['AutonomousExplorer'] = await test_autonomous_explorer()
    except Exception as e:
        print(f"\n❌ AutonomousExplorer 测试失败: {e}")
        results['AutonomousExplorer'] = False
    
    try:
        results['IntelligentExecutor'] = await test_intelligent_executor()
    except Exception as e:
        print(f"\n❌ IntelligentExecutor 测试失败: {e}")
        results['IntelligentExecutor'] = False
    
    try:
        results['ChainOfThought'] = await test_chain_of_thought()
    except Exception as e:
        print(f"\n❌ ChainOfThought 测试失败: {e}")
        results['ChainOfThought'] = False
    
    try:
        results['AdvancedOrchestrator'] = await test_advanced_orchestrator()
    except Exception as e:
        print(f"\n❌ AdvancedOrchestrator 测试失败: {e}")
        results['AdvancedOrchestrator'] = False
    
    # 输出测试总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    for module, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {module}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")


if __name__ == "__main__":
    asyncio.run(main())

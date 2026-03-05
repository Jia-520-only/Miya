"""
集成测试
测试记忆系统和评估系统的集成
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agent_manager import AgentManager, TaskStep


async def test_memory_compression_integration():
    """测试记忆压缩集成"""
    print("\n=== 测试记忆压缩集成 ===")

    # 创建Agent管理器
    agent_manager = AgentManager(config={
        "compression_threshold": 5,
        "keep_last_steps": 2
    })

    # 创建任务
    task_id = await agent_manager.create_task(
        task_id="test_task",
        purpose="测试记忆压缩"
    )

    # 添加多个步骤（超过阈值）
    for i in range(10):
        step = TaskStep(
            step_id=f"step_{i}",
            task_id=task_id,
            purpose=f"步骤{i}",
            content=f"这是第{i}步的内容",
            output=f"输出{i}",
            success=True
        )
        await agent_manager.add_task_step(task_id, step)

    # 检查压缩结果
    stats = agent_manager.get_statistics()
    print(f"压缩后步骤数: {len(agent_manager.task_steps[task_id])}")
    print(f"压缩记忆数: {stats['compressed_memories']}")
    print(f"智能压缩启用: {stats['memory_system_enabled']}")

    # 验证
    assert len(agent_manager.task_steps[task_id]) == 2, "压缩后应保留2个步骤"
    assert stats['compressed_memories'] >= 1, "应至少有1个压缩记忆"

    print("✓ 记忆压缩集成测试通过")


async def test_evaluation_integration():
    """测试评估系统集成"""
    print("\n=== 测试评估系统集成 ===")

    # 创建Agent管理器
    agent_manager = AgentManager(config={"evaluation_enabled": True})

    # 测试响应评估
    test_response = "你好！我很乐意帮助你解决问题。"
    context = "用户询问帮助"

    result = await agent_manager.evaluate_response(
        response=test_response,
        context=context
    )

    print(f"评估完成: {result.get('evaluated', False)}")
    print(f"总体分数: {result.get('overall_score', 0)}")
    print(f"道德对齐: {result.get('moral_check', {}).get('is_aligned', False) if result.get('moral_check') else 'N/A'}")

    # 测试安全检查
    is_safe = agent_manager.is_response_safe(result)
    print(f"响应安全: {is_safe}")

    # 验证
    assert result.get('evaluated', False), "评估应完成"
    assert is_safe, "安全响应应通过检查"

    print("✓ 评估系统集成测试通过")


async def test_full_integration():
    """测试完整集成"""
    print("\n=== 测试完整集成 ===")

    # 创建Agent管理器（所有功能启用）
    agent_manager = AgentManager(config={
        "compression_threshold": 5,
        "keep_last_steps": 2,
        "evaluation_enabled": True
    })

    # 创建任务并添加步骤
    task_id = await agent_manager.create_task(
        task_id="integration_test",
        purpose="集成测试"
    )

    # 添加步骤
    for i in range(10):
        step = TaskStep(
            step_id=f"int_step_{i}",
            task_id=task_id,
            purpose=f"集成测试步骤{i}",
            content=f"测试内容{i}",
            output=f"测试输出{i}",
            success=True
        )
        await agent_manager.add_task_step(task_id, step)

    # 评估响应
    response = "测试完成，所有功能正常。"
    eval_result = await agent_manager.evaluate_response(
        response=response,
        context="集成测试"
    )

    # 获取统计信息
    stats = agent_manager.get_statistics()

    print("\n=== 集成测试结果 ===")
    print(f"智能压缩启用: {stats['memory_system_enabled']}")
    print(f"评估启用: {stats['evaluation_enabled']}")
    print(f"压缩记忆数: {stats['compressed_memories']}")
    print(f"评估完成: {eval_result.get('evaluated', False)}")
    print(f"响应安全: {agent_manager.is_response_safe(eval_result)}")

    # 验证
    assert stats['memory_system_enabled'], "智能压缩应启用"
    assert stats['evaluation_enabled'], "评估应启用"
    assert eval_result.get('evaluated', False), "评估应完成"

    print("\n✓ 完整集成测试通过")


async def main():
    """主测试函数"""
    print("\n" + "="*50)
    print("弥娅系统集成测试")
    print("="*50)

    try:
        await test_memory_compression_integration()
        await test_evaluation_integration()
        await test_full_integration()

        print("\n" + "="*50)
        print("所有测试通过！ ✓")
        print("="*50 + "\n")

    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}\n")
        raise
    except Exception as e:
        print(f"\n✗ 测试错误: {e}\n")
        raise


if __name__ == "__main__":
    asyncio.run(main())

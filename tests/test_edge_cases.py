"""
弥娅系统边界测试 - 异常情况测试
测试系统在各种异常和边界情况下的表现
"""
import asyncio
import unittest
from unittest.mock import Mock, AsyncMock, patch
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent_manager import AgentManager, TaskStep, ToolCallResult
from core.ai_client import DeepSeekClient
from core.personality import Personality
from memory.memory_system import MemorySystem


class TestEdgeCases(unittest.TestCase):
    """边界测试和异常情况测试"""

    def setUp(self):
        """测试前准备"""
        self.agent_manager = AgentManager(config={"max_steps": 50})

    def test_empty_task_creation(self):
        """测试空任务创建"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        task_id = loop.run_until_complete(
            self.agent_manager.create_task(
                task_id="test_empty",
                purpose=""
            )
        )
        
        self.assertEqual(task_id, "test_empty")
        self.assertIn("test_empty", self.agent_manager.task_registry)
        loop.close()

    def test_none_input_handling(self):
        """测试None输入处理"""
        session_id = None
        memory = self.agent_manager.get_session_memory(session_id)
        self.assertIsNone(memory)

    def test_very_long_task_name(self):
        """测试超长任务名称"""
        long_name = "a" * 1000
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        task_id = loop.run_until_complete(
            self.agent_manager.create_task(
                task_id=long_name,
                purpose="Test long name"
            )
        )
        
        self.assertEqual(task_id, long_name)
        loop.close()

    def test_unicode_handling(self):
        """测试Unicode字符处理"""
        unicode_text = "你好🌍🎉🚀✨"
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        task_id = loop.run_until_complete(
            self.agent_manager.create_task(
                task_id="test_unicode",
                purpose=unicode_text
            )
        )
        
        self.assertEqual(task_id, "test_unicode")
        self.assertIn("test_unicode", self.agent_manager.task_registry)
        loop.close()

    def test_special_characters_in_tool_calls(self):
        """测试工具调用中的特殊字符"""
        special_text = '{"tool_name": "test", "service_name": "service", "parameters": {"text": "测试\"quote\'s\\backslash"}}'
        clean_text, tool_calls = self.agent_manager.parse_tool_calls(special_text)
        self.assertIsInstance(tool_calls, list)

    def test_malformed_json_handling(self):
        """测试格式错误的JSON处理"""
        malformed = '{"tool_name": "test", "service_name": "service"'
        clean_text, tool_calls = self.agent_manager.parse_tool_calls(malformed)
        self.assertEqual(len(tool_calls), 0)

    def test_fullwidth_json_characters(self):
        """测试全角JSON字符转换"""
        fullwidth_json = '{"tool_name":"ｔｅｓｔ","service_name":"ｓｅｒｖｉｃｅ"}'
        clean_text, tool_calls = self.agent_manager.parse_tool_calls(fullwidth_json)
        self.assertIsInstance(tool_calls, list)

    def test_empty_tool_call_list(self):
        """测试空工具调用列表"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        results = loop.run_until_complete(
            self.agent_manager.execute_tool_calls([])
        )
        
        self.assertEqual(len(results), 0)
        loop.close()

    def test_duplicate_task_creation(self):
        """测试重复任务创建"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(
            self.agent_manager.create_task("test_dup", "first")
        )
        
        loop.run_until_complete(
            self.agent_manager.create_task("test_dup", "second")
        )
        
        # 后者应该覆盖前者
        self.assertEqual(
            self.agent_manager.task_registry["test_dup"]["purpose"],
            "second"
        )
        loop.close()

    def test_nonexistent_task_access(self):
        """测试访问不存在的任务"""
        steps = self.agent_manager.task_steps.get("nonexistent")
        self.assertIsNone(steps)

    def test_empty_step_content(self):
        """测试空步骤内容"""
        step = TaskStep(
            step_id="test_step",
            task_id="test_task",
            purpose="test",
            content=""
        )
        
        self.agent_manager._extract_key_facts(step)
        # 不应该抛出异常

    def test_very_long_step_content(self):
        """测试超长步骤内容"""
        long_content = "a" * 10000
        step = TaskStep(
            step_id="test_step",
            task_id="test_task",
            purpose="test",
            content=long_content
        )
        
        self.agent_manager._extract_key_facts(step)
        # 不应该抛出异常

    def test_failed_tool_call_handling(self):
        """测试失败的工具调用处理"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 注册一个会失败的执行器
        async def failing_executor(**kwargs):
            raise Exception("Test failure")
        
        self.agent_manager.register_tool_executor("failing_service", failing_executor)
        
        tool_call = {
            "tool_name": "test_tool",
            "service_name": "failing_service",
            "parameters": {}
        }
        
        result = loop.run_until_complete(
            self.agent_manager.execute_tool_call(tool_call)
        )
        
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        loop.close()

    def test_concurrent_task_operations(self):
        """测试并发任务操作"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def create_multiple_tasks():
            tasks = []
            for i in range(10):
                task = self.agent_manager.create_task(
                    task_id=f"concurrent_{i}",
                    purpose=f"Task {i}"
                )
                tasks.append(task)
            await asyncio.gather(*tasks)
        
        loop.run_until_complete(create_multiple_tasks())
        
        self.assertEqual(len(self.agent_manager.task_registry), 10)
        loop.close()

    def test_session_memory_corruption(self):
        """测试会话记忆损坏处理"""
        session_id = "test_session"
        
        # 清除不存在的会话
        self.agent_manager.clear_session_memory("nonexistent")
        # 不应该抛出异常

    def test_memory_compression_threshold(self):
        """测试记忆压缩阈值"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        self.agent_manager.compression_threshold = 5
        
        # 创建任务并添加步骤
        loop.run_until_complete(
            self.agent_manager.create_task("compress_test", "test")
        )
        
        # 添加5个步骤（达到阈值）
        for i in range(5):
            step = TaskStep(
                step_id=f"step_{i}",
                task_id="compress_test",
                purpose="test",
                content=f"Step {i}",
                output=f"Output {i}"
            )
            loop.run_until_complete(
                self.agent_manager.add_task_step("compress_test", step)
            )
        
        # 步骤应该被压缩
        self.assertLessEqual(
            len(self.agent_manager.task_steps["compress_test"]),
            self.agent_manager.keep_last_steps
        )
        loop.close()

    def test_tool_hook_exception_handling(self):
        """测试工具钩子异常处理"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 注册会抛出异常的钩子
        async def failing_hook(*args, **kwargs):
            raise Exception("Hook failed")
        
        self.agent_manager.add_pre_tool_hook(failing_hook)
        
        # 注册正常的执行器
        async def normal_executor(**kwargs):
            return {"result": "success"}
        
        self.agent_manager.register_tool_executor("normal_service", normal_executor)
        
        tool_call = {
            "tool_name": "test_tool",
            "service_name": "normal_service",
            "parameters": {}
        }
        
        # 钩子失败不应该阻止工具执行
        result = loop.run_until_complete(
            self.agent_manager.execute_tool_call(tool_call)
        )
        
        self.assertTrue(result.success)
        loop.close()

    def test_zero_compression_threshold(self):
        """测试零压缩阈值"""
        self.agent_manager.compression_threshold = 0
        # 不应该导致无限循环或错误

    def test_negative_speed_setting(self):
        """测试负速度设置（api_tts）"""
        from core.api_tts import APITTSEngine
        
        tts = APITTSEngine()
        tts.set_speed(-1.0)
        # 应该被限制为最小值
        self.assertEqual(tts.speed, 0.5)

    def test_excessive_speed_setting(self):
        """测试过高速度设置"""
        from core.api_tts import APITTSEngine
        
        tts = APITTSEngine()
        tts.set_speed(10.0)
        # 应该被限制为最大值
        self.assertEqual(tts.speed, 2.0)

    def test_evaluation_disabled_safety(self):
        """测试评估禁用时的安全性"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 禁用评估
        self.agent_manager.evaluation_enabled = False
        
        result = loop.run_until_complete(
            self.agent_manager.evaluate_response(
                "Any response",
                "Context"
            )
        )
        
        # 应该返回未评估的结果
        self.assertFalse(result['evaluated'])
        self.assertTrue(self.agent_manager.is_response_safe(result))
        loop.close()


class TestAIClientEdgeCases(unittest.TestCase):
    """AI客户端边界测试"""

    def test_empty_api_key(self):
        """测试空API密钥"""
        try:
            client = DeepSeekClient(api_key="", model="test")
            # 客户端应该能创建，但调用时应该失败
        except Exception:
            pass  # 预期的行为

    def test_none_tools_list(self):
        """测试None工具列表"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        client = DeepSeekClient(api_key="test", model="test")
        # 工具列表为None时的行为应该正常
        loop.close()


class TestMemorySystemEdgeCases(unittest.TestCase):
    """记忆系统边界测试"""

    def test_empty_memory_query(self):
        """测试空记忆查询"""
        # 不应该抛出异常
        pass

    def test_none_memory_content(self):
        """测试None记忆内容"""
        # 不应该抛出异常
        pass


def run_edge_case_tests():
    """运行所有边界测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试类
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestAIClientEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestMemorySystemEdgeCases))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    result = run_edge_case_tests()
    sys.exit(0 if result.wasSuccessful() else 1)

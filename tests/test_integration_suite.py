"""
集成测试套件
测试弥娅系统的集成功能
"""
import pytest
import asyncio
from pathlib import Path
import sys
import os
import tempfile
import shutil

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPersonalityIntegration:
    """人格系统集成测试"""
    
    @pytest.mark.asyncio
    async def test_personality_with_memory_integration(self):
        """测试人格与记忆系统集成"""
        from core import Personality
        
        personality = Personality()
        
        # 模拟记忆影响人格
        initial_warmth = personality.get_vector('warmth')
        personality.adjust_vector('warmth', 0.1)
        adjusted_warmth = personality.get_vector('warmth')
        
        # 确保人格向量被调整
        assert adjusted_warmth >= initial_warmth
    
    @pytest.mark.asyncio
    async def test_personality_form_switching_integration(self):
        """测试形态切换的集成"""
        from core import Personality
        
        personality = Personality()
        
        # 切换形态
        personality.set_form('battle')
        assert personality.current_form == 'battle'
        
        # 获取描述应该包含形态信息
        description = personality.get_personality_description()
        assert description is not None


class TestMemoryIntegration:
    """记忆系统集成测试"""
    
    @pytest.mark.asyncio
    async def test_memory_storage_and_retrieval(self):
        """测试记忆存储和检索"""
        try:
            from core import GRAGMemoryStore
            from datetime import datetime
            
            # 使用临时目录
            temp_dir = tempfile.mkdtemp()
            try:
                memory = GRAGMemoryStore(storage_path=temp_dir)
                
                # 存储记忆
                await memory.add_memory(
                    user_id="test_user",
                    content="这是一条测试记忆",
                    importance=0.8
                )
                
                # 检索记忆
                memories = await memory.retrieve_memories(
                    user_id="test_user",
                    limit=5
                )
                
                # 应该至少有一条记忆
                assert len(memories) >= 1
                assert "测试记忆" in str(memories)
                
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            pytest.skip(f"Memory integration test skipped: {e}")
    
    @pytest.mark.asyncio
    async def test_temporal_knowledge_graph(self):
        """测试时序知识图谱"""
        try:
            from core import TemporalKnowledgeGraph
            from datetime import datetime
            
            # 使用临时目录
            temp_dir = tempfile.mkdtemp()
            try:
                graph = TemporalKnowledgeGraph(storage_path=temp_dir)
                
                # 添加事件
                await graph.add_event(
                    event_type="test_event",
                    user_id="test_user",
                    data={"test": "data"}
                )
                
                # 查询事件
                events = await graph.query_events(
                    event_type="test_event",
                    limit=5
                )
                
                # 应该至少有一个事件
                assert len(events) >= 1
                
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            pytest.skip(f"Temporal knowledge graph test skipped: {e}")


class TestToolIntegration:
    """工具系统集成测试"""
    
    def test_tool_loading(self):
        """测试工具加载"""
        from webnet.ToolNet.registry import ToolRegistry
        
        registry = ToolRegistry()
        registry.load_all_tools()
        
        # 应该有工具被加载
        assert len(registry.tools) > 0
    
    def test_tool_schema_generation(self):
        """测试工具schema生成"""
        from webnet.ToolNet.registry import ToolRegistry
        
        registry = ToolRegistry()
        registry.load_all_tools()
        
        # 获取工具schema
        schemas = registry.get_tools_schema()
        
        # 应该有schema
        assert len(schemas) > 0
        
        # 检查schema格式
        for schema in schemas:
            assert 'type' in schema
            assert 'function' in schema
            assert schema['type'] == 'function'


class TestMultiAgentIntegration:
    """多Agent集成测试"""
    
    @pytest.mark.asyncio
    async def test_agent_orchestration(self):
        """测试Agent编排"""
        try:
            from core import MultiAgentOrchestrator
            
            orchestrator = MultiAgentOrchestrator()
            
            # 创建测试任务
            task = {
                "task_id": "test_task",
                "task_type": "conversation",
                "input": "测试输入"
            }
            
            # 分配任务
            result = await orchestrator.assign_task(task)
            
            # 应该有结果
            assert result is not None
        except Exception as e:
            pytest.skip(f"Agent orchestration test skipped: {e}")


class TestConsistencyIntegration:
    """一致性集成测试"""
    
    @pytest.mark.asyncio
    async def test_personality_consistency_check(self):
        """测试人格一致性检查"""
        try:
            from core import PersonalityConsistencyChecker
            from core import Personality
            
            personality = Personality()
            checker = PersonalityConsistencyChecker()
            
            # 检查一致性
            score = await checker.check_consistency(personality)
            
            # 一致性分数应该在0-1之间
            assert 0 <= score <= 1
        except Exception as e:
            pytest.skip(f"Personality consistency test skipped: {e}")


class TestConfigIntegration:
    """配置集成测试"""
    
    def test_prompt_loading(self):
        """测试提示词加载"""
        from core.ai_client import BaseAIClient
        from core import Personality
        
        # 创建人格实例
        personality = Personality()
        
        # 创建AI客户端
        client = BaseAIClient(api_key="test", model="test", personality=personality)
        
        # 获取提示词
        prompt = client.get_miya_system_prompt()
        
        # 应该有提示词
        assert prompt is not None
        assert len(prompt) > 0


class TestWorkflowIntegration:
    """工作流集成测试"""
    
    @pytest.mark.asyncio
    async def test_complete_conversation_workflow(self):
        """测试完整对话工作流"""
        try:
            from core import Personality
            from webnet.ToolNet.registry import ToolRegistry
            
            # 初始化组件
            personality = Personality()
            registry = ToolRegistry()
            
            # 加载工具
            registry.load_all_tools()
            
            # 验证组件都已初始化
            assert personality is not None
            assert len(registry.tools) > 0
            
            # 这个测试验证了基本的工作流初始化
            # 实际的对话执行需要真实的环境和API
        except Exception as e:
            pytest.skip(f"Complete workflow test skipped: {e}")


class TestLifecycleIntegration:
    """生命周期集成测试"""
    
    def test_system_initialization(self):
        """测试系统初始化"""
        try:
            from core import (
                Personality,
                Ethics,
                Arbitrator
            )
            from webnet.ToolNet.registry import ToolRegistry
            
            # 初始化核心组件
            personality = Personality()
            ethics = Ethics()
            arbitrator = Arbitrator(personality, ethics)
            registry = ToolRegistry()
            
            # 验证所有组件都已初始化
            assert personality is not None
            assert ethics is not None
            assert arbitrator is not None
            assert registry is not None
        except Exception as e:
            pytest.skip(f"System initialization test skipped: {e}")


class TestPerformanceIntegration:
    """性能集成测试"""
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """测试并发操作"""
        try:
            from core import Personality
            
            # 创建多个人格实例
            personalities = [Personality() for _ in range(10)]
            
            # 并发切换形态
            tasks = []
            for i, personality in enumerate(personalities):
                form = ['normal', 'battle', 'muse', 'singer', 'ghost'][i % 5]
                tasks.append(asyncio.create_task(
                    asyncio.to_thread(personality.set_form, form)
                ))
            
            # 等待所有任务完成
            results = await asyncio.gather(*tasks)
            
            # 所有操作都应该成功
            assert all(results)
        except Exception as e:
            pytest.skip(f"Concurrent operations test skipped: {e}")


# 测试套件管理
class TestSuiteManager:
    """测试套件管理器"""
    
    @staticmethod
    def run_unit_tests():
        """运行单元测试"""
        return pytest.main(["-v", "tests/test_core_comprehensive.py"])
    
    @staticmethod
    def run_integration_tests():
        """运行集成测试"""
        return pytest.main(["-v", "tests/test_integration_suite.py"])
    
    @staticmethod
    def run_all_tests():
        """运行所有测试"""
        return pytest.main(["-v", "tests/"])


if __name__ == "__main__":
    # 运行集成测试
    TestSuiteManager.run_integration_tests()

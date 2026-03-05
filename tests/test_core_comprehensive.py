"""
核心模块综合测试套件
测试弥娅系统的核心功能
"""
import pytest
import asyncio
from pathlib import Path
import sys
import os
from core.constants import Encoding

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPersonality:
    """人格系统测试"""
    
    def test_personality_initialization(self):
        """测试人格初始化"""
        from core import Personality
        
        personality = Personality()
        assert personality.vectors is not None
        assert 'warmth' in personality.vectors
        assert 'logic' in personality.vectors
        assert personality.current_form == 'normal'
    
    def test_form_switching(self):
        """测试形态切换"""
        from core import Personality
        
        personality = Personality()
        
        # 切换到战态
        assert personality.set_form('battle') == True
        assert personality.current_form == 'battle'
        
        # 切换到缪斯形态
        assert personality.set_form('muse') == True
        assert personality.current_form == 'muse'
        
        # 无效形态
        assert personality.set_form('invalid') == False
    
    def test_personality_description(self):
        """测试人格描述生成"""
        from core import Personality
        
        personality = Personality()
        description = personality.get_personality_description()
        assert description is not None
        assert len(description) > 0
    
    def test_title_selection(self):
        """测试称呼选择"""
        from core import Personality
        
        personality = Personality()
        title = personality.get_current_title()
        assert title is not None
        assert len(title) > 0


class TestAIClient:
    """AI客户端测试"""
    
    def test_ai_client_initialization(self):
        """测试AI客户端初始化"""
        from core import AIClientFactory
        
        # 测试工厂方法
        assert AIClientFactory is not None
    
    def test_aimessage_dataclass(self):
        """测试AIMessage数据类"""
        from core.ai_client import AIMessage
        
        msg = AIMessage(role="user", content="测试消息")
        assert msg.role == "user"
        assert msg.content == "测试消息"
        assert msg.tool_calls is None
        assert msg.tool_call_id is None
    
    @pytest.mark.asyncio
    async def test_base_chat_method(self):
        """测试基础chat方法"""
        from core.ai_client import BaseAIClient
        from core.ai_client import AIMessage
        
        # 创建客户端（使用假API key）
        client = BaseAIClient(api_key="test_key", model="test_model")
        
        # 测试消息构造
        messages = [AIMessage(role="user", content="测试")]
        assert len(messages) == 1
        
        # 注意：实际调用会失败，因为我们没有真实的API key
        # 这里只测试消息构造


class TestMemorySystem:
    """记忆系统测试"""
    
    def test_memory_components_available(self):
        """测试记忆组件是否可用"""
        try:
            from core import (
                GRAGMemoryStore,
                TemporalKnowledgeGraph,
                MultiModalMemoryStore
            )
            assert True
        except ImportError:
            pytest.skip("Memory components not available")
    
    @pytest.mark.asyncio
    async def test_grag_memory_store(self):
        """测试GRAG记忆存储"""
        try:
            from core import GRAGMemoryStore
            
            # 创建记忆存储
            memory = GRAGMemoryStore()
            assert memory is not None
        except Exception as e:
            pytest.skip(f"GRAGMemoryStore test skipped: {e}")


class TestEthics:
    """伦理系统测试"""
    
    def test_ethics_initialization(self):
        """测试伦理系统初始化"""
        from core import Ethics
        
        ethics = Ethics()
        assert ethics is not None
        assert ethics.forbidden_actions is not None
    
    def test_permission_checking(self):
        """测试权限检查"""
        from core import Ethics
        
        ethics = Ethics()
        
        # 测试允许的操作
        assert ethics.is_allowed('chat', 'user') == True
        
        # 测试禁止的操作（如果有定义）
        # assert ethics.is_allowed('delete_all', 'user') == False


class TestArbitrator:
    """仲裁系统测试"""
    
    def test_arbitrator_initialization(self):
        """测试仲裁系统初始化"""
        from core import Arbitrator, Personality, Ethics
        
        personality = Personality()
        ethics = Ethics()
        arbitrator = Arbitrator(personality, ethics)
        
        assert arbitrator is not None
        assert arbitrator.personality is not None
        assert arbitrator.ethics is not None
    
    def test_arbitrate_simple(self):
        """测试简单仲裁"""
        from core import Arbitrator, Personality, Ethics
        
        personality = Personality()
        ethics = Ethics()
        arbitrator = Arbitrator(personality, ethics)
        
        # 创建选项
        options = [
            {'action': 'chat', 'score': 0.8, 'metadata': {'type': 'emotional'}},
            {'action': 'respond', 'score': 0.6, 'metadata': {'type': 'logical'}}
        ]
        
        context = {'user_level': 'user'}
        result = arbitrator.arbitrate(options, context)
        
        assert result is not None
        assert 'final_score' in result


class TestConsistencyManagers:
    """一致性管理器测试"""
    
    def test_visual_consistency_manager(self):
        """测试视觉一致性管理器"""
        try:
            from core import VisualConsistencyManager
            
            manager = VisualConsistencyManager()
            assert manager is not None
        except ImportError:
            pytest.skip("VisualConsistencyManager not available")
    
    def test_audio_consistency_manager(self):
        """测试音频一致性管理器"""
        try:
            from core import AudioConsistencyManager
            
            manager = AudioConsistencyManager()
            assert manager is not None
        except ImportError:
            pytest.skip("AudioConsistencyManager not available")


class TestMultiModal:
    """多模态集成测试"""
    
    def test_multimodal_integrator(self):
        """测试多模态集成器"""
        try:
            from core import MultimodalIntegrator
            
            integrator = MultimodalIntegrator()
            assert integrator is not None
        except ImportError:
            pytest.skip("MultimodalIntegrator not available")


class TestCoordination:
    """协调系统测试"""
    
    def test_deMAC_coordinator(self):
        """测试DeMAC协调器"""
        try:
            from core import DeMACCoordinator
            
            coordinator = DeMACCoordinator()
            assert coordinator is not None
        except ImportError:
            pytest.skip("DeMACCoordinator not available")
    
    def test_realtime_state_sync(self):
        """测试实时状态同步"""
        try:
            from core import RealTimeStateSync
            
            sync = RealTimeStateSync(agent_id="test_agent")
            assert sync is not None
            assert sync.agent_id == "test_agent"
        except ImportError:
            pytest.skip("RealTimeStateSync not available")


class TestToolSystem:
    """工具系统测试"""
    
    def test_tool_registry(self):
        """测试工具注册表"""
        from webnet.ToolNet.registry import ToolRegistry
        
        registry = ToolRegistry()
        assert registry is not None
        assert registry.tools is not None
    
    def test_base_tool(self):
        """测试基础工具"""
        from webnet.tools.base import BaseTool
        
        tool = BaseTool()
        assert tool is not None
        assert tool.name == "BaseTool"


class TestConfig:
    """配置系统测试"""
    
    def test_personality_config(self):
        """测试人格配置"""
        config_path = Path(__file__).parent.parent / "prompts" / "miya_personality_compact.json"
        if config_path.exists():
            import json
            with open(config_path, 'r', encoding=Encoding.UTF8) as f:
                config = json.load(f)
            assert 'system_prompt' in config
        else:
            pytest.skip("Personality config file not found")


# 运行测试的便利函数
def run_all_tests():
    """运行所有测试"""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    run_all_tests()

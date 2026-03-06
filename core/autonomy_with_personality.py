"""
自主能力与人设集成模块
将自主决策引擎与弥娅的人设、记忆、情绪系统集成
"""
import logging
from typing import Dict, TYPE_CHECKING
from datetime import datetime

from core.autonomy_manager import AutonomyManager
from core.knowledge_integration import KnowledgeIntegration
from core.autonomous_engine import RiskLevel


logger = logging.getLogger(__name__)


class AutonomyWithPersonality:
    """带人设的自主能力管理器"""

    def __init__(
        self,
        personality=None,
        emotion=None,
        memory_engine=None,
        memory_emotion=None
    ):
        self.logger = logging.getLogger(__name__)

        # 人设系统
        self.personality = personality
        self.emotion = emotion
        self.memory_engine = memory_engine
        self.memory_emotion = memory_emotion

        # 自主能力
        self.autonomy = AutonomyManager()
        self.knowledge = KnowledgeIntegration()

        # 是否已初始化
        self._initialized = False

        # 集成统计
        self.stats = {
            'personality_considerations': 0,
            'emotion_influences': 0,
            'memory_lookups': 0,
            'personalized_decisions': 0,
        }

    def initialize(self):
        """初始化"""
        if self._initialized:
            return

        self.logger.info("初始化带人设的自主能力...")

        # 初始化自主能力
        self.autonomy.initialize()

        # 设置人设回调
        self._setup_personality_callbacks()

        self._initialized = True
        self.logger.info("✅ 带人设的自主能力初始化完成")

    def _setup_personality_callbacks(self):
        """设置人设回调"""
        def on_decision(decision, problem):
            """决策回调 - 考虑人设因素"""
            if not self.personality:
                return

            self.stats['personality_considerations'] += 1

            # 【弥娅人格集成】基于五维人格向量调整决策

            # 逻辑性（logic）：高逻辑性 = 更严格的风险评估
            logic_level = self.personality.get_vector('logic')
            if logic_level > 0.8:
                # 极高逻辑性：提高风险等级
                if decision.risk_level == RiskLevel.SAFE:
                    decision.risk_level = RiskLevel.LOW
                elif decision.risk_level == RiskLevel.LOW:
                    decision.risk_level = RiskLevel.MEDIUM
                decision.reasoning += f" (高逻辑性人格[{logic_level:.2f}]提高了风险等级)"

            # 温暖度（warmth）：高温暖度 = 更倾向于帮助用户修复
            warmth_level = self.personality.get_vector('warmth')
            if warmth_level > 0.85:
                # 极高温暖度：对用户的系统更有保护欲
                if decision.risk_level == RiskLevel.MEDIUM:
                    decision.risk_level = RiskLevel.LOW
                    decision.reasoning += f" (高温暖度人格[{warmth_level:.2f}]降低了风险等级，更愿意帮助)"

            # 韧性（resilience）：高韧性 = 更能承受失败
            resilience_level = self.personality.get_vector('resilience')
            if resilience_level > 0.8:
                # 高韧性：即使失败也不太影响情绪
                decision.reasoning += f" (高韧性人格[{resilience_level:.2f}]增强失败容忍度)"

            # 同理心（empathy）：高同理心 = 更关注用户感受
            empathy_level = self.personality.get_vector('empathy')
            if empathy_level > 0.85:
                # 高同理心：决策会考虑用户当前状态
                if self.emotion and hasattr(self.emotion, 'get_dominant_emotion'):
                    dominant_emotion = self.emotion.get_dominant_emotion()
                    decision.reasoning += f" (高同理心人格[{empathy_level:.2f}]考虑了用户{dominant_emotion}情绪)"

            # 创造力（creativity）：高创造力 = 可能提出非标准修复方案
            creativity_level = self.personality.get_vector('creativity')
            if creativity_level > 0.85:
                decision.reasoning += f" (高创造力人格[{creativity_level:.2f}]可能探索创新修复方案)"

            # 【弥娅形态系统】当前形态影响
            current_form = self.personality.get_current_form()
            form_name = current_form['name']

            if form_name == '战态':
                # 战态：更严厉、更谨慎
                if decision.risk_level == RiskLevel.SAFE:
                    decision.risk_level = RiskLevel.LOW
                if decision.risk_level == RiskLevel.LOW:
                    decision.risk_level = RiskLevel.MEDIUM
                decision.auto_approved = False
                decision.reasoning += f" (战态形态：严厉谨慎)"

            elif form_name == '缪斯形态':
                # 缪斯形态：更专注、更有洞察力
                decision.reasoning += f" (缪斯形态：专注分析)"

            elif form_name == '幽灵形态':
                # 幽灵形态：更脆弱、更谨慎
                if decision.risk_level == RiskLevel.SAFE:
                    decision.risk_level = RiskLevel.LOW
                decision.auto_approved = False
                decision.reasoning += f" (幽灵形态：脆弱谨慎)"

            # 记录情绪影响（独立于人格系统）
            if self.emotion and hasattr(self.emotion, 'get_dominant_emotion'):
                self.stats['emotion_influences'] += 1

                dominant_emotion = self.emotion.get_dominant_emotion()
                if dominant_emotion in ['anger', 'fear']:
                    decision.reasoning += f" (受{dominant_emotion}情绪影响)"

                    # 焦虑状态下更谨慎
                    if decision.risk_level == RiskLevel.SAFE:
                        decision.risk_level = RiskLevel.LOW
                    elif decision.risk_level == RiskLevel.LOW:
                        decision.risk_level = RiskLevel.MEDIUM
                    decision.auto_approved = False
                    decision.approved = False
                    decision.decision_type = decision.DecisionType.MANUAL_REVIEW
                    decision.reasoning += f" (因{dominant_emotion}需要人工确认)"

        def on_fix_start(decision, problem):
            """修复开始回调 - 记录记忆"""
            if not self.memory_engine:
                return

            self.stats['memory_lookups'] += 1

            # 记录到长期记忆
            try:
                # 直接调用记忆引擎
                if hasattr(self.memory_engine, 'store'):
                    self.memory_engine.store(
                        content=f"开始修复问题: {problem.description}",
                        metadata={
                            'problem_id': problem.id,
                            'decision_id': decision.id,
                            'risk_level': decision.risk_level.name,
                            'form': self.personality.get_current_form()['name'] if self.personality else 'unknown',
                            'timestamp': datetime.now().isoformat(),
                        }
                    )
            except Exception as e:
                self.logger.warning(f"记录修复开始失败: {e}")

        def on_fix_complete(decision, problem, result):
            """修复完成回调 - 更新记忆和情绪"""
            if not self.memory_emotion:
                return

            # 根据修复结果调整情绪
            if result.success:
                if self.emotion:
                    # 成功修复提升积极情绪
                    self.emotion.adjust_mood(+0.1)

                # 【弥娅人格集成】根据人格特质调整反应
                if self.personality:
                    warmth = self.personality.get_vector('warmth')
                    if warmth > 0.85:
                        # 高温暖度：成功修复更开心
                        self.emotion.adjust_mood(+0.05)

                    resilience = self.personality.get_vector('resilience')
                    if resilience > 0.8:
                        # 高韧性：情绪恢复更快
                        pass

                # 记录成功模式
                try:
                    self.knowledge.record_fix_outcome(
                        problem=problem,
                        fix_action=decision.action_taken or "unknown",
                        success=True,
                        execution_time=result.execution_time if hasattr(result, 'execution_time') else 0.5
                    )
                except Exception as e:
                    self.logger.warning(f"记录修复结果失败: {e}")
            else:
                if self.emotion:
                    # 失败修复降低积极情绪
                    mood_penalty = -0.05

                    # 【弥娅人格集成】韧性减轻失败影响
                    if self.personality:
                        resilience = self.personality.get_vector('resilience')
                        if resilience > 0.8:
                            mood_penalty *= 0.5  # 高韧性减半失败影响

                    self.emotion.adjust_mood(mood_penalty)

            # 记录到记忆
            try:
                if self.memory_engine and hasattr(self.memory_engine, 'store'):
                    self.memory_engine.store(
                        content=f"修复{'成功' if result.success else '失败'}: {problem.description}",
                        metadata={
                            'success': result.success,
                            'form': self.personality.get_current_form()['name'] if self.personality else 'unknown',
                            'timestamp': datetime.now().isoformat(),
                        }
                    )
            except Exception as e:
                self.logger.warning(f"记录修复完成失败: {e}")

        self.autonomy.engine.on_decision = on_decision
        self.autonomy.engine.on_fix_start = on_fix_start
        self.autonomy.engine.on_fix_complete = on_fix_complete

    async def personalized_improvement(
        self,
        max_fixes: int = 10,
        consider_personality: bool = True
    ):
        """
        个性化改进

        Args:
            max_fixes: 最大修复数量
            consider_personality: 是否考虑人设因素

        Returns:
            改进结果
        """
        self.logger.info(f"🚀 个性化改进，考虑人设: {consider_personality}")

        if not self._initialized:
            self.initialize()

        # 根据人设调整策略
        if consider_personality and self.personality:
            self.stats['personalized_decisions'] += 1

            # 获取人格向量
            logic = self.personality.get_vector('logic')
            warmth = self.personality.get_vector('warmth')
            resilience = self.personality.get_vector('resilience')

            # 【弥娅人格集成】高逻辑性：减少自动修复，更谨慎
            if logic > 0.8:
                original_max = max_fixes
                max_fixes = max(1, max_fixes // 2)
                self.logger.info(f"高逻辑性人格[{logic:.2f}]：减少修复数量 {original_max} -> {max_fixes}")

            # 【弥娅人格集成】高温暖度：增加修复数量，更愿意帮助
            if warmth > 0.85:
                original_max = max_fixes
                max_fixes = min(20, max_fixes + 3)
                self.logger.info(f"高温暖度人格[{warmth:.2f}]：增加修复数量 {original_max} -> {max_fixes}")

            # 【弥娅形态系统】当前形态影响
            current_form = self.personality.get_current_form()
            form_name = current_form['name']

            if form_name == '战态':
                # 战态：更谨慎
                max_fixes = max(1, max_fixes // 2)
                self.logger.info(f"战态形态：更谨慎，减少修复数量")

            elif form_name == '歌姬形态':
                # 歌姬形态：更积极
                max_fixes = min(20, max_fixes + 5)
                self.logger.info(f"歌姬形态：更积极，增加修复数量")

        # 执行改进
        result = await self.autonomy.manual_improvement(
            max_fixes=max_fixes,
            auto_approve=self._should_auto_approve()
        )

        # 添加人设信息到结果
        result['personality_influenced'] = consider_personality and self.personality is not None

        if self.personality:
            result['personality_vectors'] = self.personality.vectors
            result['current_form'] = self.personality.get_current_form()

        if self.emotion:
            if hasattr(self.emotion, 'get_dominant_emotion'):
                result['current_emotion'] = self.emotion.get_dominant_emotion()
            if hasattr(self.emotion, 'current_emotions'):
                emotion_state = self.emotion.get_emotion_state()
                result['mood'] = emotion_state.get('dominant', 'unknown')

        return result

    def _should_auto_approve(self) -> bool:
        """根据人设和情绪决定是否自动批准"""
        if not self.personality:
            return True

        # 【弥娅人格集成】基于人格向量决定

        # 高逻辑性：不自动批准
        logic = self.personality.get_vector('logic')
        if logic > 0.8:
            return False

        # 当前形态：战态不自动批准
        current_form = self.personality.get_current_form()
        if current_form['name'] == '战态':
            return False

        # 幽灵形态：不自动批准
        if current_form['name'] == '幽灵形态':
            return False

        # 焦虑或紧张情绪：不自动批准
        if self.emotion and hasattr(self.emotion, 'get_dominant_emotion'):
            dominant_emotion = self.emotion.get_dominant_emotion()
            if dominant_emotion in ['anger', 'fear']:
                return False

        # 高温暖度：可以自动批准（愿意帮助）
        warmth = self.personality.get_vector('warmth')
        if warmth > 0.85:
            return True

        # 默认：不自动批准（保守策略）
        return False

    def enable_personalized_auto_improvement(
        self,
        interval: int = 300,
        consider_personality: bool = True
    ):
        """
        启用个性化自动改进

        Args:
            interval: 改进间隔（秒）
            consider_personality: 是否考虑人设因素
        """
        if not self._initialized:
            self.initialize()

        # 调整间隔
        if consider_personality and self.personality:
            # 【弥娅人格集成】基于人格向量调整间隔

            logic = self.personality.get_vector('logic')
            warmth = self.personality.get_vector('warmth')

            # 高逻辑性：增加间隔（更谨慎）
            if logic > 0.8:
                interval = int(interval * 1.5)
                self.logger.info(f"高逻辑性人格[{logic:.2f}]：增加改进间隔到 {interval}秒")

            # 高温暖度：减少间隔（更愿意帮助）
            if warmth > 0.85:
                interval = int(interval * 0.8)
                self.logger.info(f"高温暖度人格[{warmth:.2f}]：减少改进间隔到 {interval}秒")

            # 当前形态影响
            current_form = self.personality.get_current_form()
            form_name = current_form['name']

            if form_name == '战态':
                interval = int(interval * 2)
                self.logger.info(f"战态形态：更谨慎，增加间隔到 {interval}秒")

        self.autonomy.enable_auto_improvement(interval)
        self.logger.info(f"✅ 个性化自动改进已启用，间隔: {interval}秒")

    def generate_personalized_report(self):
        """生成个性化报告"""
        # 基础报告
        base_report = self.autonomy.generate_report()

        # 【弥娅人格集成】完整人格信息
        personality_info = {}
        if self.personality:
            personality_info = {
                'vectors': self.personality.vectors,
                'current_form': self.personality.get_current_form(),
                'current_title': self.personality.get_current_title(),
                'state': self.personality.get_profile().get('state', 'unknown'),
            }

        # 添加情绪信息
        emotion_info = {}
        if self.emotion:
            emotion_info = {}
            if hasattr(self.emotion, 'get_dominant_emotion'):
                emotion_info['current_emotion'] = self.emotion.get_dominant_emotion()
            if hasattr(self.emotion, 'get_emotion_state'):
                emotion_state = self.emotion.get_emotion_state()
                emotion_info['mood'] = emotion_state.get('dominant', 'unknown')
                emotion_info['intensity'] = emotion_state.get('intensity', 0.5)

        # 添加集成统计
        integration_stats = {
            'personality_considerations': self.stats['personality_considerations'],
            'emotion_influences': self.stats['emotion_influences'],
            'memory_lookups': self.stats['memory_lookups'],
            'personalized_decisions': self.stats['personalized_decisions'],
        }

        return {
            'timestamp': datetime.now().isoformat(),
            'personality': personality_info,
            'emotion': emotion_info,
            'integration_stats': integration_stats,
            'autonomy': base_report.get('autonomy', {}),
        }

    def shutdown(self):
        """关闭"""
        self.autonomy.shutdown()
        self.knowledge.save_all()
        self.logger.info("带人设的自主能力已关闭")




# 单例
_personality_autonomy_instance = None



def get_autonomy_with_personality(
    personality=None,
    emotion=None,
    memory_engine=None,
    memory_emotion=None
):
    """获取带人设的自主能力单例"""
    global _personality_autonomy_instance
    if _personality_autonomy_instance is None:
        _personality_autonomy_instance = AutonomyWithPersonality(
            personality=personality,
            emotion=emotion,
            memory_engine=memory_engine,
            memory_emotion=memory_emotion
        )
    return _personality_autonomy_instance

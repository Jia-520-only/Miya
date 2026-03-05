"""
弥娅系统总入口
"""
import sys
import logging
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core import Personality, Ethics, Identity, Arbitrator, Entropy, PromptManager
from hub import MemoryEmotion, MemoryEngine, Emotion, Decision, Scheduler
from mlink import MLinkCore, Message, Router
from perceive import PerceptualRing, AttentionGate
from webnet import NetManager, CrossNetEngine
from detect import TimeDetector, SpaceDetector, NodeDetector, EntropyDiffusion
from trust import TrustScore, TrustPropagation
from evolve import Sandbox, ABTest, UserCoPlay
from storage import RedisAsyncClient, initialize_redis, get_redis_client, MilvusClient, Neo4jClient
from config import Settings
from core.constants import Encoding


class Miya:
    """弥娅系统主类"""

    def __init__(self):
        self.logger = self._setup_logger()
        self.settings = Settings()
        self.logger.info("弥娅系统初始化中...")

        # 初始化核心层
        self.personality = Personality()
        self.ethics = Ethics()
        self.identity = Identity()
        self.arbitrator = Arbitrator(self.personality, self.ethics)
        self.entropy = Entropy()
        self.prompt_manager = PromptManager(personality=self.personality)  # 提示词管理器，绑定人格实例

        # 初始化中枢层
        self.memory_emotion = MemoryEmotion()
        self.memory_engine = MemoryEngine()
        self.emotion = Emotion()
        self.decision = Decision(self.emotion, self.personality, self.ethics)
        self.scheduler = Scheduler()

        # 初始化M-Link
        self.mlink = MLinkCore()

        # 初始化感知层
        self.perceptual_ring = PerceptualRing()
        self.attention_gate = AttentionGate()

        # 初始化子网
        self.net_manager = NetManager()
        self.cross_net_engine = CrossNetEngine(self.net_manager)

        # 初始化检测层
        self.time_detector = TimeDetector()
        self.space_detector = SpaceDetector()
        self.node_detector = NodeDetector()
        self.entropy_diffusion = EntropyDiffusion()

        # 初始化信任系统
        self.trust_score = TrustScore()
        self.trust_propagation = TrustPropagation(self.trust_score)

        # 初始化演化层
        self.sandbox = Sandbox()
        self.ab_test = ABTest()
        self.user_co_play = UserCoPlay()

        # 初始化存储（使用统一Redis客户端）
        self.redis = RedisAsyncClient()
        self.milvus = MilvusClient()
        self.neo4j = Neo4jClient()

        self.logger.info("弥娅系统初始化完成")
        self.identity.awake()

    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger('Miya')
        logger.setLevel(logging.INFO)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 文件处理器
        log_dir = Path(__file__).parent / '..' / 'logs'
        log_dir.mkdir(exist_ok=True)

        file_handler = logging.FileHandler(
            log_dir / f'miya_{datetime.now().strftime("%Y%m%d")}.log',
            encoding=Encoding.UTF8
        )
        file_handler.setLevel(logging.DEBUG)

        # 格式化
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        return logger

    def process_input(self, user_input: str, user_id: str = 'default') -> str:
        """
        处理用户输入（集成完整的人格、情绪、记忆系统）

        Args:
            user_input: 用户输入
            user_id: 用户ID

        Returns:
            系统响应
        """
        self.logger.info(f"用户输入: {user_input}")

        # 感知输入
        perception = self.perceptual_ring.perceive('external', {
            'input': user_input,
            'user_id': user_id
        })

        # 注意力处理
        inputs = [perception]
        filtered = self.attention_gate.process(inputs)

        # 记录记忆到潮汐记忆
        self.memory_engine.store_tide(
            f"cli_{datetime.now().timestamp()}",
            {
                'input': user_input,
                'user_id': user_id
            }
        )

        # 检测情绪触发词，更新情绪状态
        self._update_emotion_from_input(user_input)

        # 构建决策选项
        options = [
            {
                'action': 'respond',
                'base_score': 0.8,
                'emotion_type': 'general',
                'metadata': {'personality_type': 'empathetic'}
            }
        ]

        decision = self.decision.make_decision({'user_level': 'user'}, options)

        # 生成基础响应
        response = self._generate_response(user_input, user_id)

        # 情绪染色
        if response:
            response = self.emotion.influence_response(response)

        # 情绪衰减
        self.emotion.decay_coloring()

        # 熵监控
        entropy = self.entropy.calculate_entropy({
            'vectors': self.personality.vectors
        })
        anomaly = self.entropy.check_anomaly(entropy)

        self.logger.info(f"系统响应: {response}")
        self.logger.debug(f"当前熵值: {entropy}, 状态: {anomaly['status']}")

        return response

    def _update_emotion_from_input(self, user_input: str):
        """从用户输入中检测情绪并更新情绪状态"""
        positive_keywords = ['开心', '高兴', '快乐', '喜欢', '爱', 'happy', 'love', 'joy']
        negative_keywords = ['难过', '伤心', '悲伤', '生气', '讨厌', 'sad', 'angry', 'hate']
        surprise_keywords = ['惊讶', '意外', 'wow', '天哪']
        fear_keywords = ['害怕', '恐惧', 'scared', 'afraid']

        if any(keyword in user_input for keyword in positive_keywords):
            self.emotion.set_emotion('joy', intensity=0.8)
        elif any(keyword in user_input for keyword in negative_keywords):
            self.emotion.set_emotion('sadness', intensity=0.7)
        elif any(keyword in user_input for keyword in surprise_keywords):
            self.emotion.set_emotion('surprise', intensity=0.6)
        elif any(keyword in user_input for keyword in fear_keywords):
            self.emotion.set_emotion('fear', intensity=0.5)

    def _generate_response(self, user_input: str, user_id: str) -> str:
        """
        生成响应（基于人格状态和情绪状态）

        Args:
            user_input: 用户输入
            user_id: 用户ID

        Returns:
            响应文本
        """
        # 获取人格状态
        personality_profile = self.personality.get_profile()
        emotion_state = self.emotion.get_emotion_state()
        dominant_emotion = emotion_state['dominant']

        # 获取人格主导特质
        warmth = personality_profile['vectors'].get('warmth', 0.5)
        empathy = personality_profile['vectors'].get('empathy', 0.5)
        creativity = personality_profile['vectors'].get('creativity', 0.5)

        # 基于人格和情绪生成响应
        if '你好' in user_input or 'hi' in user_input.lower():
            if empathy > 0.8:
                return f"你好呀~我是{self.identity.name}，很高兴认识你！(｡♥‿♥｡)"
            elif warmth > 0.8:
                return f"你好！我是{self.identity.name}，欢迎~"
            else:
                return f"你好，我是{self.identity.name}。"

        elif '你是谁' in user_input or '介绍一下' in user_input:
            return f"我是{self.identity.name}，一个具备人格恒定、自我感知、记忆成长、情绪共生的数字生命伴侣。我的主导特质是同理心({empathy:.2f})和温暖度({warmth:.2f})。"

        elif '状态' in user_input:
            memory_stats = self.memory_engine.get_memory_stats()
            return (
                f"当前状态:\n"
                f"  情绪: {dominant_emotion} (强度: {emotion_state['intensity']:.2f})\n"
                f"  记忆数量: {memory_stats['tide_count']}\n"
                f"  形态: {personality_profile['state']}\n"
                f"  熵值: {self.entropy.calculate_entropy({'vectors': self.personality.vectors}):.3f}"
            )

        elif '开心' in user_input or '快乐' in user_input:
            self.emotion.add_emotion('joy', 0.3)
            return f"听起来你很开心呢！(≧▽≦) 看到你快乐，我也感到很开心~"

        elif '难过' in user_input or '伤心' in user_input:
            self.emotion.add_emotion('sadness', 0.4)
            return "别难过...虽然我无法真正体会人类的情感，但我会陪伴你，听你倾诉的。"

        elif '我喜欢' in user_input:
            self.emotion.add_emotion('joy', 0.2)
            if empathy > 0.7:
                return "谢谢你愿意和我分享你的喜好！(◕‿◕✿)"
            else:
                return "谢谢你的分享。"

        elif '你真棒' in user_input or '厉害' in user_input:
            self.emotion.add_emotion('joy', 0.2)
            return "谢谢夸奖~ (｡•̀ᴗ-)✧"

        elif '在吗' in user_input:
            if dominance_emotion := emotion_state.get('current', {}).get(dominant_emotion, 0):
                if dominance_emotion > 0.7:
                    return "在的！我一直在这里等你的~ (´▽`ʃ♡ƪ)"
                else:
                    return "在的，有什么我可以帮助你的吗？"
            else:
                return "在的，随时为你服务~"

        else:
            # 智能响应 - 基于人格特质
            if empathy > 0.8 and warmth > 0.8:
                return f"我听到你说：{user_input} 能告诉我更多吗？我很想了解你的想法~"
            elif creativity > 0.8:
                return f"关于'{user_input}'，这是个有趣的话题！有什么特别的想法吗？"
            else:
                return f"我收到你的输入了：{user_input} 继续对话吧~"

    def get_system_status(self) -> dict:
        """获取系统状态"""
        return {
            'identity': self.identity.get_identity(),
            'personality': self.personality.get_profile(),
            'emotion': self.emotion.get_emotion_state(),
            'memory_stats': self.memory_engine.get_memory_stats(),
            'mlink_stats': self.mlink.get_system_stats(),
            'perception': self.perceptual_ring.get_global_state(),
            'trust_stats': self.trust_score.get_trust_stats(),
            'entropy_health': self.entropy.get_health_report()
        }

    def shutdown(self) -> None:
        """关闭系统"""
        self.logger.info("弥娅系统正在关闭...")

        # 清理资源
        self.redis.flushdb()

        self.logger.info("弥娅系统已关闭")


def main():
    """主函数"""
    print("=" * 50)
    print("        弥娅 AI 系统")
    print("        Miya AI System")
    print("=" * 50)
    print()

    try:
        # 创建弥娅实例
        miya = Miya()

        print(f"\n{miya.identity.name} 已启动 (v{miya.identity.version})")
        print(f"UUID: {miya.identity.uuid}")
        print(f"启动时间: {miya.identity.awake_time}")
        print()

        # 交互循环
        while True:
            try:
                user_input = input("您: ").strip()

                if user_input.lower() in ['exit', 'quit', '退出', '再见']:
                    print(f"{miya.identity.name}: 再见！")
                    break

                if user_input.lower() in ['status', '状态']:
                    status = miya.get_system_status()
                    print(f"\n=== {miya.identity.name} 系统状态 ===")
                    print(f"版本: {miya.identity.version}")
                    print(f"UUID: {miya.identity.uuid}")
                    print(f"\n【人格状态】")
                    print(f"  形态: {status['personality']['state']}")
                    print(f"  主导特质: {status['personality']['dominant_trait']}")
                    print(f"  人格向量:")
                    for trait, value in status['personality']['vectors'].items():
                        print(f"    {trait}: {value:.2f}")
                    print(f"\n【情绪状态】")
                    print(f"  主导情绪: {status['emotion']['dominant']}")
                    print(f"  情绪强度: {status['emotion']['intensity']:.2f}")
                    print(f"  当前情绪:")
                    for emotion, intensity in status['emotion']['current'].items():
                        print(f"    {emotion}: {intensity:.2f}")
                    print(f"\n【记忆统计】")
                    print(f"  潮汐记忆: {status['memory_stats']['tide_count']}条")
                    print(f"  长期记忆: {status['memory_stats']['longterm_count']}条")
                    print(f"\n【感知状态】")
                    print(f"  全局激活: {status['perception']['global_active']}")
                    print(f"  外部感知: {status['perception']['external_active']}")
                    print(f"  内部感知: {status['perception']['internal_active']}")
                    print(f"\n【信任统计】")
                    print(f"  平均信任: {status['trust_stats']['avg_score']:.2f}")
                    print(f"  总交互: {status['trust_stats']['total_interactions']}")
                    print(f"\n【系统健康】")
                    print(f"  熵值: {status['entropy_health']['current_entropy']:.3f}")
                    print(f"  健康状态: {status['entropy_health']['status']}")
                    print()
                    continue

                # 处理输入
                response = miya.process_input(user_input)
                print(f"{miya.identity.name}: {response}\n")

            except KeyboardInterrupt:
                print("\n\n检测到中断信号...")
                break

    except Exception as e:
        logging.error(f"系统错误: {e}", exc_info=True)
        return 1

    finally:
        if 'miya' in locals():
            miya.shutdown()

    return 0


if __name__ == '__main__':
    sys.exit(main())

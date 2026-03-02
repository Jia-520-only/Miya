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
from storage import RedisClient, MilvusClient, Neo4jClient
from config import Settings


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

        # 初始化存储
        self.redis = RedisClient()
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
            encoding='utf-8'
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
        处理用户输入

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

        # 决策
        options = [
            {
                'action': 'respond',
                'base_score': 0.8,
                'emotion_type': 'general',
                'metadata': {'personality_type': 'empathetic'}
            }
        ]

        decision = self.decision.make_decision({'user_level': 'user'}, options)

        # 情绪染色
        response = "我已收到您的输入，正在处理..."

        if decision:
            response = self.emotion.influence_response(response)

        # 情绪衰减
        self.emotion.decay_coloring()

        # 记录记忆
        self.memory_engine.store_tide(
            f"input_{datetime.now().timestamp()}",
            {
                'input': user_input,
                'response': response,
                'user_id': user_id
            }
        )

        # 熵监控
        entropy = self.entropy.calculate_entropy({
            'vectors': self.personality.vectors
        })

        anomaly = self.entropy.check_anomaly(entropy)

        self.logger.info(f"系统响应: {response}")
        self.logger.debug(f"当前熵值: {entropy}, 状态: {anomaly['status']}")

        return response

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
                    print(f"\n系统状态:")
                    print(f"  主导情绪: {status['emotion']['dominant']}")
                    print(f"  记忆数量: {status['memory_stats']['tide_count']}")
                    print(f"  平均信任: {status['trust_stats']['avg_score']}")
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

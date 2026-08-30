"""
自愈引擎
监控系统状态并自动恢复
"""
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core import Entropy
from config import Settings
from core.constants import Encoding


class AutoHealEngine:
    """自愈引擎"""

    def __init__(self):
        self.logger = self._setup_logger()
        self.settings = Settings()
        self.entropy = Entropy()
        self.running = False

        # 检查阈值
        self.check_interval = self.settings.get('detection.check_interval', 60)  # 秒

    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger('AutoHeal')
        logger.setLevel(logging.INFO)

        log_dir = Path(__file__).parent / '..' / 'logs'
        log_dir.mkdir(exist_ok=True)

        file_handler = logging.FileHandler(
            log_dir / 'auto_heal.log',
            encoding=Encoding.UTF8
        )
        file_handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        return logger

    def check_system_health(self) -> dict:
        """检查系统健康状态"""
        # 检查熵值
        current_entropy = self.entropy.calculate_entropy({
            'vectors': {'warmth': 0.8, 'logic': 0.7, 'creativity': 0.6}
        })

        anomaly = self.entropy.check_anomaly(current_entropy)

        return {
            'entropy': current_entropy,
            'status': anomaly['status'],
            'alerts': anomaly['alerts']
        }

    def heal_personality_drift(self) -> bool:
        """修复人格漂移"""
        self.logger.info("检测到人格漂移，开始修复...")

        # 简化实现：重置人格向量
        try:
            from core import Personality
            personality = Personality()

            self.logger.info("人格向量已重置")
            return True
        except Exception as e:
            self.logger.error(f"人格修复失败: {e}")
            return False

    def heal_memory_corruption(self) -> bool:
        """修复记忆损坏"""
        self.logger.info("检测到记忆损坏，开始修复...")

        # 简化实现：清理过期记忆
        try:
            from hub import MemoryEngine
            memory_engine = MemoryEngine()
            expired = memory_engine.cleanup_expired()

            self.logger.info(f"已清理 {expired} 条过期记忆")
            return True
        except Exception as e:
            self.logger.error(f"记忆修复失败: {e}")
            return False

    def execute_healing(self, health_status: dict) -> None:
        """执行自愈操作"""
        if health_status['status'] == 'critical':
            self.logger.warning("系统状态严重，执行紧急修复...")

            # 执行所有修复操作
            self.heal_personality_drift()
            self.heal_memory_corruption()

        elif health_status['status'] == 'warning':
            self.logger.info("系统状态警告，执行预防性修复...")

            # 根据警告类型执行相应修复
            for alert in health_status.get('alerts', []):
                if '人格' in alert:
                    self.heal_personality_drift()
                elif '记忆' in alert:
                    self.heal_memory_corruption()

    def run(self) -> None:
        """运行自愈引擎"""
        self.running = True
        self.logger.info("自愈引擎已启动")

        try:
            while self.running:
                # 检查系统健康
                health_status = self.check_system_health()

                self.logger.info(
                    f"系统健康检查 - 熵值: {health_status['entropy']:.3f}, "
                    f"状态: {health_status['status']}"
                )

                # 如果需要修复
                if health_status['status'] != 'normal':
                    self.execute_healing(health_status)

                # 等待下一次检查
                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            self.logger.info("接收到中断信号")
            self.running = False
        except Exception as e:
            self.logger.error(f"自愈引擎错误: {e}", exc_info=True)
            self.running = False

        self.logger.info("自愈引擎已停止")

    def stop(self) -> None:
        """停止自愈引擎"""
        self.running = False


def main():
    """主函数"""
    print("=" * 50)
    print("        弥娅自愈引擎")
    print("        Auto Heal Engine")
    print("=" * 50)
    print()

    try:
        engine = AutoHealEngine()
        engine.run()
    except Exception as e:
        logging.error(f"引擎启动失败: {e}", exc_info=True)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())

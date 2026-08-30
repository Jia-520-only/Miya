"""
M-Link 消息监听器
监听并处理通过 M-Link 传递的消息
"""
import asyncio
import logging
from typing import Callable, Dict, Optional
from .message import Message


logger = logging.getLogger(__name__)


class MessageListener:
    """消息监听器 - 监听特定类型的消息"""

    def __init__(self, mlink_core):
        """
        初始化监听器

        Args:
            mlink_core: MLinkCore 实例
        """
        self.mlink = mlink_core
        self.handlers: Dict[str, Callable] = {}
        self.running = False
        self._task = None

    def register_handler(self, msg_type: str, handler: Callable) -> None:
        """
        注册消息处理器

        Args:
            msg_type: 消息类型
            handler: 处理函数，接收 Message 对象，返回处理结果
        """
        self.handlers[msg_type] = handler
        logger.info(f"已注册消息处理器: {msg_type}")

    def unregister_handler(self, msg_type: str) -> None:
        """注销消息处理器"""
        if msg_type in self.handlers:
            del self.handlers[msg_type]
            logger.info(f"已注销消息处理器: {msg_type}")

    async def start(self) -> None:
        """启动监听器"""
        if self.running:
            logger.warning("消息监听器已在运行")
            return

        self.running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("M-Link 消息监听器已启动")

    async def stop(self) -> None:
        """停止监听器"""
        if not self.running:
            return

        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("M-Link 消息监听器已停止")

    async def _listen_loop(self) -> None:
        """监听循环"""
        while self.running:
            try:
                # 检查是否有新消息需要处理
                # 这里模拟从 M-Link 获取消息
                # 实际实现中，M-Link 应该提供消息队列机制
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"消息监听循环错误: {e}")

    async def process_message(self, message: Message) -> Optional[Dict]:
        """
        处理消息

        Args:
            message: 消息对象

        Returns:
            处理结果
        """
        # 标记消息已接收
        self.mlink.receive(message)

        # 查找对应的处理器
        handler = self.handlers.get(message.msg_type)
        if not handler:
            logger.warning(f"未找到消息处理器: {message.msg_type}")
            return None

        try:
            # 异步处理消息
            if asyncio.iscoroutinefunction(handler):
                result = await handler(message)
            else:
                result = handler(message)

            logger.debug(f"消息处理完成: {message.msg_type}")
            return result

        except Exception as e:
            logger.error(f"处理消息失败: {message.msg_type}, 错误: {e}", exc_info=True)
            return None

"""弥娅WebUI虚拟发送器 - 整合Undefined的WebUI能力

该模块提供WebUI虚拟发送器，支持：
- 通过WebUI模拟消息发送
- 虚拟消息路由
- 多端消息转发

设计理念：符合弥娅的M-Link架构，作为webnet层的扩展
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class WebUIMessage:
    """WebUI消息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = "webui"
    sender_name: str = "WebUI用户"
    content: str = ""
    message_type: str = "text"  # text, image, audio, etc.
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    reply_to: Optional[str] = None


@dataclass
class WebUIResponse:
    """WebUI响应"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str = ""
    content: str = ""
    response_type: str = "text"
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class WebUISender:
    """WebUI虚拟发送器
    
    职责：
    - 接收WebUI的消息输入
    - 将消息转换为弥娅统一格式
    - 通过M-Link路由到相应模块
    - 接收并返回响应
    
    架构定位：属于webnet层，提供WebUI消息处理能力
    """

    def __init__(self):
        # 消息队列
        self._message_queue: asyncio.Queue[WebUIMessage] = asyncio.Queue()
        
        # 响应等待器
        self._response_waiters: Dict[str, asyncio.Future] = {}
        
        # 消息处理器
        self._message_handler: Optional[
            Callable[[WebUIMessage], Coroutine[Any, Any, WebUIResponse]]
        ] = None
        
        # 运行状态
        self._running = False
        self._process_task: Optional[asyncio.Task[None]] = None

    def set_message_handler(
        self,
        handler: Callable[[WebUIMessage], Coroutine[Any, Any, WebUIResponse]]
    ) -> None:
        """设置消息处理器"""
        self._message_handler = handler

    async def send_message(
        self,
        content: str,
        message_type: str = "text",
        sender_name: str = "WebUI用户",
        metadata: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Optional[WebUIResponse]:
        """发送消息并等待响应
        
        Args:
            content: 消息内容
            message_type: 消息类型
            sender_name: 发送者名称
            metadata: 元数据
            timeout: 超时时间
        
        Returns:
            WebUI响应，超时返回None
        """
        message = WebUIMessage(
            content=content,
            message_type=message_type,
            sender_name=sender_name,
            metadata=metadata or {},
        )
        
        # 创建响应等待器
        response_future: asyncio.Future[WebUIResponse] = asyncio.Future()
        self._response_waiters[message.id] = response_future
        
        # 入队消息
        await self._message_queue.put(message)
        
        logger.debug(
            "[WebUI发送器] 消息已发送 id=%s content_len=%s",
            message.id,
            len(content),
        )
        
        # 等待响应
        try:
            response = await asyncio.wait_for(response_future, timeout=timeout)
            logger.debug(
                "[WebUI发送器] 收到响应 id=%s",
                message.id,
            )
            return response
        except asyncio.TimeoutError:
            logger.warning(
                "[WebUI发送器] 响应超时 id=%s timeout=%.1fs",
                message.id,
                timeout,
            )
            self._response_waiters.pop(message.id, None)
            return None

    async def _process_messages(self) -> None:
        """处理消息队列"""
        logger.info("[WebUI发送器] 消息处理器已启动")
        
        while self._running:
            try:
                # 获取消息（带超时，避免阻塞停止）
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0,
                )
                
                if not self._message_handler:
                    logger.warning("[WebUI发送器] 未设置消息处理器")
                    continue
                
                # 处理消息
                try:
                    response = await self._message_handler(message)
                    response.request_id = message.id
                    
                    # 通知等待器
                    waiter = self._response_waiters.pop(message.id, None)
                    if waiter and not waiter.done():
                        waiter.set_result(response)
                    
                except Exception as e:
                    logger.error(
                        "[WebUI发送器] 消息处理异常 id=%s error=%s",
                        message.id,
                        e,
                        exc_info=True,
                    )
                    
                    # 通知异常
                    waiter = self._response_waiters.pop(message.id, None)
                    if waiter and not waiter.done():
                        waiter.set_exception(e)
                
            except asyncio.TimeoutError:
                # 超时是正常的，继续循环
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "[WebUI发送器] 处理循环异常 error=%s",
                    e,
                    exc_info=True,
                )
        
        logger.info("[WebUI发送器] 消息处理器已停止")

    async def start(self) -> None:
        """启动WebUI发送器"""
        if self._running:
            logger.warning("[WebUI发送器] 已在运行")
            return
        
        self._running = True
        self._process_task = asyncio.create_task(self._process_messages())
        logger.info("[WebUI发送器] 已启动")

    async def stop(self) -> None:
        """停止WebUI发送器"""
        if not self._running:
            return
        
        self._running = False
        
        # 停止处理任务
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
            self._process_task = None
        
        # 清理所有等待器
        for future in self._response_waiters.values():
            if not future.done():
                future.cancel()
        self._response_waiters.clear()
        
        logger.info("[WebUI发送器] 已停止")

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "running": self._running,
            "queue_size": self._message_queue.qsize(),
            "pending_responses": len(self._response_waiters),
        }

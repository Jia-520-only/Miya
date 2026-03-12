"""
弥娅接管模式 - 弥娅V4.0多终端协作架构

弥娅接管模式允许在任何终端中与弥娅交互：
- 主终端：显示思考过程，全局调度
- 子终端：弥娅可以接管并直接执行命令
- 统一交互接口：无论在哪个终端，弥娅都能响应用户请求
"""

import asyncio
from typing import Dict, Optional, Callable
from .master_terminal_controller import MasterTerminalController
from .child_terminal import ChildTerminalManager
import logging

logger = logging.getLogger(__name__)


class MiyaTakeoverMode:
    """弥娅接管模式 - 在任何终端中都能交互
    
    功能：
    1. 识别是否是对弥娅的请求
    2. 路由到弥娅处理
    3. 在来源终端显示响应
    4. 支持弥娅接管任何终端执行命令
    """
    
    def __init__(
        self,
        master_controller: MasterTerminalController,
        child_manager: ChildTerminalManager
    ):
        self.master = master_controller
        self.child_manager = child_manager
        self.current_terminal = "master"  # master 或 child_id
        
        # 弥娅AI回调
        self.miya_callback: Optional[Callable] = None
        
        logger.info("[弥娅接管模式] 初始化完成")
    
    def set_miya_callback(self, callback: Callable):
        """设置弥娅AI回调
        
        Args:
            callback: 弥娅AI处理函数，接收(input_text, from_terminal) 返回 response
        """
        self.miya_callback = callback
        # 同时设置给主终端控制器
        self.master.set_miya_callback(callback)
        logger.info("[弥娅接管模式] 弥娅AI回调已设置")

    async def handle_input(
        self,
        input_text: str,
        from_terminal: str = "master"
    ):
        """处理来自任意终端的输入
        
        Args:
            input_text: 用户输入
            from_terminal: 来源终端（"master" 或 child_id）
        """
        self.current_terminal = from_terminal
        
        # 识别是否是对弥娅的请求
        if self._is_miya_request(input_text):
            # 弥娅处理请求 - 发送给AI决定工具调用
            await self._route_to_miya(input_text, from_terminal)
        elif from_terminal == "master":
            # 主终端的普通命令，也通过AI处理（让AI决定调用哪个工具）
            # 这样AI可以正确选择 multi_terminal 工具来创建终端
            await self._route_to_miya(input_text, from_terminal)
        else:
            # 子终端中的普通命令
            await self._handle_child_terminal_command(input_text, from_terminal)

    def _is_miya_request(self, input_text: str) -> bool:
        """判断是否是对弥娅的请求
        
        关键词：
        - 弥娅、miya
        - 你好、hello
        - 解释、分析
        - 帮我、help
        - 任何问句
        
        Args:
            input_text: 输入文本
            
        Returns:
            True如果是对弥娅的请求
        """
        miya_keywords = [
            '弥娅', 'miya', '你好', 'hello', 'hi',
            '解释', '分析', '帮我', 'help', 'assist',
            '?', '？', '怎么', '如何', '为什么', '为什么',
            '告诉我', '介绍一下', '说明', '说明一下'
        ]
        
        input_lower = input_text.lower()
        for kw in miya_keywords:
            if kw in input_lower:
                return True
        
        # 问号结尾通常是对话
        if '?' in input_text or '？' in input_text:
            return True
        
        return False

    async def _route_to_miya(self, input_text: str, from_terminal: str):
        """路由到弥娅处理
        
        Args:
            input_text: 输入文本
            from_terminal: 来源终端
        """
        print(f"\n[弥娅] 收到来自 {from_terminal} 的请求")
        
        # 调用弥娅AI
        if self.miya_callback:
            response = await self.miya_callback(input_text, from_terminal)
            
            # 在来源终端显示响应
            print(f"\n{response}\n")
        else:
            print("\n[弥娅] AI回调未设置，无法处理请求\n")

    async def _handle_child_terminal_command(
        self,
        input_text: str,
        terminal_id: str
    ):
        """处理子终端中的普通命令
        
        Args:
            input_text: 输入文本
            terminal_id: 终端ID
        """
        child = self.child_manager.get_child_terminal(terminal_id)
        
        if not child:
            print(f"\n[错误] 子终端不存在: {terminal_id}\n")
            return
        
        # 如果启用了弥娅接管模式
        if child.miya_takeover:
            # 弥娅接管执行
            result = await child.execute_from_miya(input_text)
            
            if result.success:
                print(f"\n[执行成功]\n{result.output}\n")
            else:
                print(f"\n[执行失败] {result.error}\n")
        else:
            # 直接执行命令（不通过弥娅）
            results = await child.execute([input_text])
            
            if results and results[0].success:
                print(f"\n{results[0].output}\n")
            else:
                print(f"\n[执行失败] {results[0].error if results else '未知错误'}\n")

    async def enable_takeover_for_terminal(self, terminal_id: str):
        """启用指定终端的弥娅接管模式
        
        Args:
            terminal_id: 终端ID
        """
        child = self.child_manager.get_child_terminal(terminal_id)
        
        if child:
            child.enable_miya_takeover()
            print(f"\n[弥娅] 已启用终端 {terminal_id} 的接管模式\n")
        else:
            print(f"\n[错误] 子终端不存在: {terminal_id}\n")

    async def disable_takeover_for_terminal(self, terminal_id: str):
        """禁用指定终端的弥娅接管模式
        
        Args:
            terminal_id: 终端ID
        """
        child = self.child_manager.get_child_terminal(terminal_id)
        
        if child:
            child.disable_miya_takeover()
            print(f"\n[弥娅] 已禁用终端 {terminal_id} 的接管模式\n")
        else:
            print(f"\n[错误] 子终端不存在: {terminal_id}\n")

    def get_current_terminal(self) -> str:
        """获取当前活动终端"""
        return self.current_terminal

    def get_all_terminals_status(self) -> Dict:
        """获取所有终端状态"""
        status = {
            "master": {
                "type": "master",
                "name": "主终端",
                "status": "active"
            }
        }
        
        child_terminals = self.child_manager.get_all_child_terminals()
        for child in child_terminals:
            status[child["id"]] = {
                "type": "child",
                "name": child["name"],
                "status": child["status"],
                "miya_takeover": child["miya_takeover"]
            }
        
        return status

"""
弥娅接管模式 - 弥娅V4.0多终端协作架构

弥娅接管模式允许在任何终端中与弥娅交互：
- 主终端：显示思考过程，全局调度
- 子终端：弥娅可以接管并直接执行命令
- 统一交互接口：无论在哪个终端，弥娅都能响应用户请求
"""

import asyncio
import sys
import time
from typing import Dict, Optional, Callable
from .master_terminal_controller import MasterTerminalController
from .child_terminal import ChildTerminalManager
import logging

logger = logging.getLogger(__name__)


def _should_stream_output(text: str) -> bool:
    """
    判断是否应该使用流式输出（逐字显示）
    
    规则：
    - 聊天/文本内容 → 流式输出
    - 系统目录/状态/命令结果 → 一次性输出
    """
    if not text:
        return False
    
    text_lower = text.lower().strip()
    
    # 系统类内容模式（不需要流式输出）
    system_patterns = [
        # 目录列表
        text.startswith('/') or '目录' in text or '文件夹' in text,
        text.startswith('d:') or text.startswith('c:') or text.startswith('e:') or text.startswith('f:'),
        'total ' in text_lower and 'drwxr-xr-x' in text_lower,  # Linux目录
        # 命令提示符
        'root@' in text or ':~' in text or ':/$' in text,
        # 状态信息
        'status:' in text_lower or '状态:' in text,
        # 错误信息
        text.startswith('error') or text.startswith('error:') or text.startswith('错误'),
        # JSON/XML结构
        (text.strip().startswith('{') and text.strip().endswith('}')),
        (text.strip().startswith('[') and text.strip().endswith(']')),
        # 纯数字/符号
        text.isdigit(),
        # 命令执行结果（通常有分隔线）
        ('=' * 20 in text or '-' * 20 in text),
    ]
    
    # 如果匹配任何系统模式，不使用流式输出
    if any(system_patterns):
        return False
    
    # 检查是否像正常的对话文本
    chat_indicators = [
        '你好', '您好', '我知道了', '明白了', '好的', '可以', '没问题',
        '请问', '有什么', '帮助', '是的', '不是', '但是', '因为', '所以',
        '我建议', '你可以', '让我', '我来', '推荐', '今天', '天气',
    ]
    
    # 统计中文字符和标点
    chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    punctuation_count = sum(1 for c in text if c in '，。！？；：""''（）')
    
    # 如果有足够的中文字符或对话关键词，认为是聊天内容
    if chinese_count > 10 or any(indicator in text for indicator in chat_indicators):
        return True
    
    # 如果标点比例较高，也认为是文本
    if len(text) > 20 and punctuation_count / len(text) > 0.05:
        return True
    
    # 默认返回True（流式输出）
    return True


def _stream_print(text: str, delay: float = 0.02):
    """流式输出（逐字显示）
    
    Args:
        text: 要输出的文本
        delay: 每个字符的延迟（秒），默认0.02秒
    """
    if not text:
        print()
        return
    
    # 逐字输出
    for i, char in enumerate(text):
        sys.stdout.write(char)
        sys.stdout.flush()
        # 最后一个字符或遇到句末标点时停顿稍长
        if i < len(text) - 1:
            if char in '。！？；：\n':
                time.sleep(delay * 3)
            else:
                time.sleep(delay)
    
    print()  # 最后换行


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
            
            # 根据内容类型决定输出方式
            if _should_stream_output(response):
                _stream_print(f"\n{response}")
                print()
            else:
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

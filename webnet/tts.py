"""
TTSNet - TTS子网
处理TTS相关的消息和调用
"""
import logging
from typing import Optional, Dict, Any
from pathlib import Path

from core.tts_registry import TTSRegistry
from core.gpt_sovits import GPTSoviTSEngine
from core.system_tts import SystemTTSEngine
from core.api_tts import APITTSEngine
from mlink.message import Message, MessageType, FlowType


logger = logging.getLogger(__name__)


class TTSNet:
    """TTS子网 - 处理文本转语音任务"""

    def __init__(self, mlink=None):
        """
        初始化TTSNet

        Args:
            mlink: M-Link核心实例
        """
        self.mlink = mlink
        self.registry = TTSRegistry()

        # 注册TTS引擎
        self._register_engines()

        # 注册到M-Link
        if self.mlink:
            self._register_to_mlink()

    def _register_engines(self):
        """注册TTS引擎"""
        # 注册GPT-SOViTS引擎
        gpt_sovits = GPTSoviTSEngine()
        self.registry.register_engine(gpt_sovits, is_default=True)

        # 注册系统TTS引擎
        system_tts = SystemTTSEngine()
        self.registry.register_engine(system_tts, is_default=False)

        # 注册API TTS引擎
        api_tts = APITTSEngine()
        self.registry.register_engine(api_tts, is_default=False)

        logger.info("TTS engines registered: gpt_sovits, system_tts, api_tts")

    def _register_to_mlink(self):
        """注册到M-Link"""
        if self.mlink:
            self.mlink.register_node("tts", self.handle_tts_message)

    async def handle_tts_message(self, message: Message) -> Optional[Message]:
        """
        处理TTS消息

        Args:
            message: TTS消息

        Returns:
            Message: 处理结果消息
        """
        try:
            if message.message_type != MessageType.TTS:
                return None

            text = message.content.get("text")
            engine = message.content.get("engine")
            output_format = message.content.get("format", "mp3")
            output_path = message.content.get("output_path")

            if not text:
                error_msg = Message(
                    sender="tts",
                    content={"error": "Text is required"},
                    message_type=MessageType.ERROR,
                    flow_type=FlowType.RESPONSE
                )
                return error_msg

            # 执行TTS
            if output_path:
                result_path = await self.registry.synthesize_to_file(
                    text=text,
                    output_path=output_path,
                    engine_name=engine,
                    output_format=output_format
                )
                response = Message(
                    sender="tts",
                    content={"text": text, "output_path": result_path},
                    message_type=MessageType.TTS,
                    flow_type=FlowType.RESPONSE
                )
            else:
                audio_data = await self.registry.synthesize(
                    text=text,
                    engine_name=engine,
                    output_format=output_format
                )
                response = Message(
                    sender="tts",
                    content={"text": text, "audio_data": audio_data, "format": output_format},
                    message_type=MessageType.TTS,
                    flow_type=FlowType.RESPONSE
                )

            return response

        except Exception as e:
            logger.error(f"TTS message handling failed: {e}")
            error_msg = Message(
                sender="tts",
                content={"error": str(e)},
                message_type=MessageType.ERROR,
                flow_type=FlowType.RESPONSE
            )
            return error_msg

    async def synthesize(self, text: str, engine: Optional[str] = None,
                        output_format: str = "mp3", **kwargs) -> Optional[bytes]:
        """
        合成语音

        Args:
            text: 要合成的文本
            engine: 引擎名称
            output_format: 输出格式
            **kwargs: 其他参数

        Returns:
            bytes: 语音数据
        """
        return await self.registry.synthesize(text, engine, output_format, **kwargs)

    async def synthesize_to_file(self, text: str, output_path: str,
                                engine: Optional[str] = None,
                                output_format: str = "mp3", **kwargs) -> Optional[str]:
        """
        合成语音并保存到文件

        Args:
            text: 要合成的文本
            output_path: 输出文件路径
            engine: 引擎名称
            output_format: 输出格式
            **kwargs: 其他参数

        Returns:
            str: 输出文件路径
        """
        return await self.registry.synthesize_to_file(text, output_path, engine, output_format, **kwargs)

    def set_current_engine(self, engine_name: str) -> bool:
        """
        设置当前使用的引擎

        Args:
            engine_name: 引擎名称

        Returns:
            bool: 设置是否成功
        """
        return self.registry.set_current_engine(engine_name)

    def get_available_engines(self):
        """获取可用引擎列表"""
        return self.registry.get_available_engines()

    def initialize(self, config: Dict[str, Any]):
        """
        初始化TTSNet

        Args:
            config: TTS配置字典
        """
        logger.info(f"TTSNet initializing with config keys: {list(config.keys())}")

        # 从配置中提取引擎配置
        engines_config = config.get("engines", {})
        logger.info(f"Found {len(engines_config)} engine configs: {list(engines_config.keys())}")

        # 只初始化启用的引擎
        for engine_name, engine_config in engines_config.items():
            enabled = engine_config.get("enabled", False)
            logger.info(f"Engine {engine_name}: enabled={enabled}")

            if enabled:
                engine = self.registry.engines.get(engine_name)
                if engine:
                    logger.info(f"Initializing engine: {engine_name}")
                    success = engine.initialize(engine_config)
                    if success:
                        logger.info(f"✅ TTS engine initialized: {engine_name}")
                    else:
                        logger.error(f"❌ TTS engine initialization failed: {engine_name}")
                else:
                    logger.warning(f"⚠️ Engine not found in registry: {engine_name}")
            else:
                logger.info(f"⏭️ TTS engine disabled: {engine_name}")

        logger.info("TTSNet initialized")

    def cleanup(self):
        """清理TTSNet资源"""
        self.registry.cleanup_all()
        logger.info("TTSNet cleaned up")

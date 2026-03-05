"""
TTS注册管理器
管理多个TTS引擎的注册、切换和调用
"""
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging
import asyncio

from .tts_engine import TTSEngine


logger = logging.getLogger(__name__)


class TTSRegistry:
    """TTS引擎注册管理器"""

    def __init__(self):
        self.engines: Dict[str, TTSEngine] = {}
        self.default_engine: Optional[str] = None
        self.current_engine: Optional[str] = None

    def register_engine(self, engine: TTSEngine, is_default: bool = False):
        """
        注册TTS引擎

        Args:
            engine: TTS引擎实例
            is_default: 是否设为默认引擎
        """
        engine_name = engine.engine_name
        self.engines[engine_name] = engine

        if is_default or self.default_engine is None:
            self.default_engine = engine_name

        if self.current_engine is None:
            self.current_engine = engine_name

        logger.info(f"Registered TTS engine: {engine_name} (default: {is_default})")

    def unregister_engine(self, engine_name: str):
        """
        注销TTS引擎

        Args:
            engine_name: 引擎名称
        """
        if engine_name in self.engines:
            engine = self.engines[engine_name]
            engine.cleanup()
            del self.engines[engine_name]

            if self.current_engine == engine_name:
                self.current_engine = self.default_engine or (list(self.engines.keys())[0] if self.engines else None)

            if self.default_engine == engine_name:
                self.default_engine = list(self.engines.keys())[0] if self.engines else None

            logger.info(f"Unregistered TTS engine: {engine_name}")

    def get_engine(self, engine_name: Optional[str] = None) -> Optional[TTSEngine]:
        """
        获取TTS引擎

        Args:
            engine_name: 引擎名称, 不指定则使用当前引擎

        Returns:
            TTSEngine: 引擎实例
        """
        if engine_name is None:
            engine_name = self.current_engine

        return self.engines.get(engine_name)

    def set_current_engine(self, engine_name: str) -> bool:
        """
        设置当前使用的引擎

        Args:
            engine_name: 引擎名称

        Returns:
            bool: 设置是否成功
        """
        if engine_name in self.engines:
            self.current_engine = engine_name
            logger.info(f"Current TTS engine set to: {engine_name}")
            return True
        return False

    def get_available_engines(self) -> List[str]:
        """
        获取所有已注册的引擎

        Returns:
            list: 引擎名称列表
        """
        return list(self.engines.keys())

    async def synthesize(self, text: str, engine_name: Optional[str] = None,
                        output_format: str = "mp3", **kwargs) -> Optional[bytes]:
        """
        合成语音

        Args:
            text: 要合成的文本
            engine_name: 引擎名称
            output_format: 输出格式
            **kwargs: 其他参数

        Returns:
            bytes: 语音数据
        """
        engine = self.get_engine(engine_name)
        if engine is None:
            logger.error(f"TTS engine not found: {engine_name or self.current_engine}")
            return None

        if not engine.is_initialized:
            logger.error(f"TTS engine not initialized: {engine.engine_name}")
            return None

        return await engine.synthesize(text, output_format=output_format, **kwargs)

    async def synthesize_to_file(self, text: str, output_path: str,
                                engine_name: Optional[str] = None,
                                output_format: str = "mp3", **kwargs) -> Optional[str]:
        """
        合成语音并保存到文件

        Args:
            text: 要合成的文本
            output_path: 输出文件路径
            engine_name: 引擎名称
            output_format: 输出格式
            **kwargs: 其他参数

        Returns:
            str: 输出文件路径
        """
        engine = self.get_engine(engine_name)
        if engine is None:
            logger.error(f"TTS engine not found: {engine_name or self.current_engine}")
            return None

        if not engine.is_initialized:
            logger.error(f"TTS engine not initialized: {engine.engine_name}")
            return None

        return await engine.synthesize_to_file(text, output_path, output_format=output_format, **kwargs)

    async def initialize_all(self, config: Dict[str, Any]):
        """
        初始化所有已注册的引擎

        Args:
            config: 配置字典, key为引擎名称, value为引擎配置
        """
        for engine_name, engine_config in config.items():
            engine = self.engines.get(engine_name)
            if engine:
                success = engine.initialize(engine_config)
                if success:
                    logger.info(f"TTS engine initialized: {engine_name}")
                else:
                    logger.error(f"TTS engine initialization failed: {engine_name}")

    def cleanup_all(self):
        """清理所有引擎资源"""
        for engine in self.engines.values():
            engine.cleanup()
        logger.info("All TTS engines cleaned up")

    def __repr__(self):
        return f"<TTSRegistry: engines={list(self.engines.keys())}, current={self.current_engine}>"

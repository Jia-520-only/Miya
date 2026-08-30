#!/usr/bin/env python3
"""
Provider 管理器

统一管理所有 Provider 实例：
- 加载/卸载 Provider
- 获取 Provider 实例
- Provider 健康检查
- 使用统计
"""

import asyncio
import logging
import traceback
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProviderManager:
    """Provider 管理器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True

        # Provider 实例映射
        self.inst_map: Dict[str, Any] = {}

        # 所有 Provider 实例列表
        self.provider_insts: List[Any] = []

        # 当前使用的 Provider
        self.curr_provider: Optional[Any] = None

        # 配置
        self.provider_config: List[Dict] = []
        self.provider_settings: Dict = {}

        # 加载锁
        self._load_lock = asyncio.Lock()

        # 使用统计
        self.usage_stats: Dict[str, Dict] = {}

    def load_config(
        self,
        provider_config: List[Dict],
        provider_settings: Dict,
    ) -> None:
        """加载配置"""
        self.provider_config = provider_config
        self.provider_settings = provider_settings

        logger.info(f"[ProviderManager] 加载配置: {len(provider_config)} 个 Provider")

    async def initialize(self) -> None:
        """初始化所有 Provider"""
        for config in self.provider_config:
            try:
                await self.load_provider(config)
            except Exception as e:
                logger.error(f"[ProviderManager] 加载 Provider {config.get('id')} 失败: {e}")
                logger.error(traceback.format_exc())

        # 设置默认 Provider
        if self.provider_insts:
            default_id = self.provider_settings.get("default_provider_id")

            if default_id and default_id in self.inst_map:
                self.curr_provider = self.inst_map[default_id]
            else:
                self.curr_provider = self.provider_insts[0]

            logger.info(f"[ProviderManager] 当前 Provider: {self.curr_provider.meta().id}")

    async def load_provider(self, config: Dict) -> None:
        """加载单个 Provider"""
        provider_type = config.get("type", "")
        provider_id = config.get("id", "")

        # 检查是否启用
        if not config.get("enable", True):
            logger.info(f"[ProviderManager] Provider {provider_id} 已禁用")
            return

        logger.info(f"[ProviderManager] 加载 {provider_type}({provider_id})...")

        # 动态导入
        try:
            self._dynamic_import(provider_type)
        except (ImportError, ModuleNotFoundError) as e:
            logger.critical(f"[ProviderManager] 导入 {provider_type} 失败: {e}")
            return

        # 获取 Provider 类
        from core.providers.register import get_provider_meta

        meta = get_provider_meta(provider_type)
        if not meta:
            logger.error(f"[ProviderManager] 未找到 {provider_type} 的元数据")
            return

        # 实例化
        try:
            cls_type = meta.cls_type
            inst = cls_type(config, self.provider_settings)

            # 如果有 initialize 方法
            if hasattr(inst, "initialize"):
                await inst.initialize()

            # 保存
            self.inst_map[provider_id] = inst
            self.provider_insts.append(inst)

            logger.info(f"[ProviderManager] 已加载 {provider_type}({provider_id})")

        except Exception as e:
            logger.error(f"[ProviderManager] 实例化 {provider_id} 失败: {e}")
            raise

    def _dynamic_import(self, provider_type: str) -> None:
        """动态导入 Provider 模块"""
        # 延迟导入
        if (
            provider_type == "openai_chat_completion"
            or provider_type == "deepseek_chat_completion"
            or provider_type == "anthropic_chat_completion"
            or provider_type in ("siliconflow_chat_completion", "zhipu_chat_completion")
        ):
            pass
        # 可扩展更多 Provider

    async def reload_provider(self, config: Dict) -> None:
        """重新加载 Provider"""
        async with self._load_lock:
            provider_id = config.get("id", "")

            # 终止旧的
            if provider_id in self.inst_map:
                await self.terminate_provider(provider_id)

            # 加载新的
            if config.get("enable", True):
                await self.load_provider(config)

            # 同步配置
            self.provider_config = [c for c in self.provider_config if c.get("id") != provider_id]
            self.provider_config.append(config)

    async def terminate_provider(self, provider_id: str) -> None:
        """终止 Provider"""
        if provider_id not in self.inst_map:
            return

        inst = self.inst_map[provider_id]

        # 移除列表
        if inst in self.provider_insts:
            self.provider_insts.remove(inst)

        # 终止
        if hasattr(inst, "terminate"):
            await inst.terminate()

        # 删除映射
        del self.inst_map[provider_id]

        # 更新当前 Provider
        if self.curr_provider and self.curr_provider.provider_id == provider_id:
            self.curr_provider = self.provider_insts[0] if self.provider_insts else None

        logger.info(f"[ProviderManager] 已终止 Provider: {provider_id}")

    def get_provider(self, provider_id: str = None) -> Optional[Any]:
        """获取 Provider 实例"""
        if provider_id:
            return self.inst_map.get(provider_id)

        return self.curr_provider

    def get_provider_by_id(self, provider_id: str) -> Optional[Any]:
        """根据 ID 获取 Provider"""
        return self.inst_map.get(provider_id)

    def list_providers(self) -> List[Dict]:
        """列出所有 Provider"""
        result = []
        for inst in self.provider_insts:
            meta = inst.meta()
            result.append(
                {
                    "id": meta.id,
                    "type": meta.type,
                    "model": meta.model,
                    "provider_type": meta.provider_type,
                }
            )
        return result

    async def test_all_providers(self) -> Dict[str, bool]:
        """测试所有 Provider"""
        results = {}

        for inst in self.provider_insts:
            provider_id = inst.provider_id
            try:
                await inst.test()
                results[provider_id] = True
                logger.info(f"[ProviderManager] {provider_id} 测试通过")
            except Exception as e:
                results[provider_id] = False
                logger.error(f"[ProviderManager] {provider_id} 测试失败: {e}")

        return results

    def record_usage(
        self,
        provider_id: str,
        input_tokens: int,
        output_tokens: int,
        duration: float,
    ) -> None:
        """记录使用"""
        if provider_id not in self.usage_stats:
            self.usage_stats[provider_id] = {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_duration": 0.0,
                "errors": 0,
            }

        stats = self.usage_stats[provider_id]
        stats["requests"] += 1
        stats["input_tokens"] += input_tokens
        stats["output_tokens"] += output_tokens
        stats["total_duration"] += duration

    def get_usage_stats(self) -> Dict[str, Dict]:
        """获取使用统计"""
        return self.usage_stats.copy()

    def get_total_stats(self) -> Dict:
        """获取总统计"""
        total = {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_duration": 0.0,
            "errors": 0,
        }

        for stats in self.usage_stats.values():
            for key in total:
                total[key] += stats.get(key, 0)

        return total

    async def terminate(self) -> None:
        """终止所有 Provider"""
        for inst in self.provider_insts:
            if hasattr(inst, "terminate"):
                await inst.terminate()

        self.provider_insts.clear()
        self.inst_map.clear()
        self.curr_provider = None


# 全局实例
_provider_manager_instance = None


def get_provider_manager() -> ProviderManager:
    """获取 Provider 管理器实例"""
    global _provider_manager_instance
    if _provider_manager_instance is None:
        _provider_manager_instance = ProviderManager()
    return _provider_manager_instance


def set_provider_manager(
    provider_config: List[Dict],
    provider_settings: Dict,
) -> None:
    """设置并初始化 Provider 管理器"""
    manager = get_provider_manager()
    manager.load_config(provider_config, provider_settings)

"""
热补丁系统 - 运行时代码热更新（来自NagaAgent）

功能：
- 打包后运行时代码热更新
- 无需重新打包即可修复bug
- 支持环境变量自定义补丁目录
"""

import importlib
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

IS_PACKAGED = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


@dataclass
class PatchInfo:
    """补丁信息"""

    name: str
    version: str
    modules: List[str]
    loaded: bool = False


class HotPatchManager:
    """热补丁管理器"""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.patch_dir = self._get_patch_dir()
        self.loaded_patches: Dict[str, PatchInfo] = {}
        self._original_modules: Dict[str, object] = {}

        logger.info(f"[HotPatch] 补丁目录: {self.patch_dir}")

    def _get_patch_dir(self) -> str:
        """获取补丁目录"""
        # 优先使用环境变量
        env_patch_dir = os.environ.get("MIYA_PATCH_DIR", "")
        if env_patch_dir and os.path.isdir(env_patch_dir):
            return env_patch_dir

        # 根据平台确定默认目录
        if sys.platform == "win32":
            base = os.environ.get("APPDATA", "")
            return os.path.join(base, "Miya", "patches", "backend") if base else ""
        elif sys.platform == "darwin":  # macOS
            return os.path.expanduser("~/Library/Application Support/Miya/patches/backend")
        else:  # Linux
            return os.path.expanduser("~/.miya/patches")

    def is_enabled(self) -> bool:
        """检查是否启用热补丁"""
        return bool(self.patch_dir and os.path.isdir(self.patch_dir))

    def scan_patches(self) -> List[str]:
        """扫描可用的补丁"""
        if not self.is_enabled():
            return []

        patches = []
        try:
            for item in os.listdir(self.patch_dir):
                item_path = os.path.join(self.patch_dir, item)
                if os.path.isdir(item_path):
                    patches.append(item)
        except Exception as e:
            logger.error(f"[HotPatch] 扫描补丁失败: {e}")

        return patches

    def load_patch(self, patch_name: str) -> bool:
        """加载指定补丁"""
        if not self.is_enabled():
            logger.warning("[HotPatch] 热补丁未启用")
            return False

        patch_path = os.path.join(self.patch_dir, patch_name)
        if not os.path.isdir(patch_path):
            logger.error(f"[HotPatch] 补丁不存在: {patch_name}")
            return False

        try:
            # 将补丁目录添加到 sys.path
            if patch_path not in sys.path:
                sys.path.insert(0, patch_path)

            # 加载补丁模块
            init_file = os.path.join(patch_path, "__init__.py")
            if os.path.exists(init_file):
                module_name = f"miya_patch.{patch_name}"
                module = importlib.import_module(module_name)

                # 记录已加载的补丁
                self.loaded_patches[patch_name] = PatchInfo(
                    name=patch_name,
                    version=getattr(module, "__version__", "1.0.0"),
                    modules=self._find_modules(patch_path),
                    loaded=True,
                )

                logger.info(f"[HotPatch] 已加载补丁: {patch_name}")
                return True
            else:
                logger.warning(f"[HotPatch] 补丁缺少 __init__.py: {patch_name}")

        except Exception as e:
            logger.error(f"[HotPatch] 加载补丁失败: {e}")

        return False

    def _find_modules(self, patch_path: str) -> List[str]:
        """查找补丁中的模块"""
        modules = []
        for root, _dirs, files in os.walk(patch_path):
            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    rel_path = os.path.relpath(os.path.join(root, file), patch_path)
                    module = rel_path.replace(os.sep, ".").replace(".py", "")
                    modules.append(module)
        return modules

    def unload_patch(self, patch_name: str) -> bool:
        """卸载补丁"""
        if patch_name not in self.loaded_patches:
            return False

        try:
            # 从 sys.path 移除
            patch_path = os.path.join(self.patch_dir, patch_name)
            if patch_path in sys.path:
                sys.path.remove(patch_path)

            # 移除已加载的模块
            for module_name in self.loaded_patches[patch_name].modules:
                full_name = f"miya_patch.{patch_name}.{module_name}"
                if full_name in sys.modules:
                    del sys.modules[full_name]

            del self.loaded_patches[patch_name]
            logger.info(f"[HotPatch] 已卸载补丁: {patch_name}")
            return True

        except Exception as e:
            logger.error(f"[HotPatch] 卸载补丁失败: {e}")
            return False

    def reload_patch(self, patch_name: str) -> bool:
        """重新加载补丁"""
        self.unload_patch(patch_name)
        return self.load_patch(patch_name)

    def get_loaded_patches(self) -> Dict[str, PatchInfo]:
        """获取已加载的补丁信息"""
        return self.loaded_patches.copy()

    def get_status(self) -> Dict:
        """获取热补丁系统状态"""
        return {
            "enabled": self.is_enabled(),
            "patch_dir": self.patch_dir,
            "available_patches": self.scan_patches(),
            "loaded_patches": list(self.loaded_patches.keys()),
        }


# 全局实例
_patch_manager: Optional[HotPatchManager] = None


def get_hot_patch_manager() -> HotPatchManager:
    """获取热补丁管理器全局实例"""
    global _patch_manager
    if _patch_manager is None:
        _patch_manager = HotPatchManager.get_instance()
    return _patch_manager

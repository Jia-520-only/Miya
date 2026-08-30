"""Miya 统一版本号。

所有需要展示版本、写入默认配置或生成构建产物的模块，都应从这里读取版本。
"""

__version__ = "4.1.11"
VERSION = __version__
VERSION_TUPLE = tuple(int(part) for part in __version__.split("."))

__all__ = ["__version__", "VERSION", "VERSION_TUPLE"]

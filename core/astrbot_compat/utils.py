"""
AstrBot 工具函数兼容层

提供 AstrBot 常用工具函数的兼容实现。
"""

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional, Union


# 路径工具
def get_astrbot_root() -> str:
    """获取 AstrBot 根目录"""
    return str(Path(__file__).parent.parent.parent)


def get_astrbot_data_path() -> str:
    """获取 AstrBot 数据目录"""
    return os.path.join(get_astrbot_root(), "data")


def get_astrbot_temp_path() -> str:
    """获取临时文件目录"""
    temp_dir = os.path.join(get_astrbot_data_path(), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def get_astrbot_log_path() -> str:
    """获取日志目录"""
    log_dir = os.path.join(get_astrbot_data_path(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


# 时间工具
def normalize_datetime_utc(dt: Optional[datetime] = None) -> str:
    """将日期时间规范化为 UTC ISO 格式"""
    if dt is None:
        dt = datetime.now(UTC)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


def get_timestamp() -> float:
    """获取当前时间戳"""
    return time.time()


def get_timestamp_ms() -> int:
    """获取当前时间戳（毫秒）"""
    return int(time.time() * 1000)


# 哈希工具
def md5_hash(data: Union[str, bytes]) -> str:
    """计算 MD5 哈希"""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.md5(data).hexdigest()


def sha256_hash(data: Union[str, bytes]) -> str:
    """计算 SHA256 哈希"""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


# JSON 工具
def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """安全地解析 JSON 字符串"""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, default: Any = None) -> str:
    """安全地序列化为 JSON 字符串"""
    try:
        return json.dumps(obj, ensure_ascii=False, default=default)
    except (TypeError, ValueError):
        return "{}"


# 文件工具
def ensure_dir(path: str) -> str:
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)
    return path


def read_file(file_path: str, encoding: str = "utf-8") -> Optional[str]:
    """读取文件内容"""
    try:
        with open(file_path, "r", encoding=encoding) as f:
            return f.read()
    except Exception:
        return None


def write_file(file_path: str, content: str, encoding: str = "utf-8") -> bool:
    """写入文件内容"""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)
        return True
    except Exception:
        return False


# 字符串工具
def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """截断字符串"""
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符"""
    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        filename = filename.replace(char, "_")
    return filename


# 错误处理
def safe_error(error: Exception) -> str:
    """安全地获取错误信息"""
    try:
        return str(error)
    except Exception:
        return f"Unknown error: {type(error).__name__}"


# 导出
__all__ = [
    "get_astrbot_root",
    "get_astrbot_data_path",
    "get_astrbot_temp_path",
    "get_astrbot_log_path",
    "normalize_datetime_utc",
    "get_timestamp",
    "get_timestamp_ms",
    "md5_hash",
    "sha256_hash",
    "safe_json_loads",
    "safe_json_dumps",
    "ensure_dir",
    "read_file",
    "write_file",
    "truncate_string",
    "sanitize_filename",
    "safe_error",
]

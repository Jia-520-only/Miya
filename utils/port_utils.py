"""
端口工具模块 - 提供统一的端口检测和自动切换功能
"""

import json
import socket
from pathlib import Path
from typing import Tuple


# 运行时端口信息文件路径（供前端读取实际端口）
def _get_runtime_ports_path() -> Path:
    """获取运行时端口配置文件的路径"""
    return Path(__file__).parent.parent / "config" / "runtime_ports.json"


def write_runtime_ports(ports: dict) -> None:
    """将实际运行时端口写入配置文件，供前端/Electron 读取"""
    try:
        ports_path = _get_runtime_ports_path()
        ports_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if ports_path.exists():
            try:
                existing = json.loads(ports_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        existing.update(ports)
        ports_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"##MIYA_PORTS##{json.dumps(existing, ensure_ascii=False)}##")
    except Exception:
        pass  # 非关键路径，静默失败


def read_runtime_ports() -> dict:
    """读取运行时端口配置"""
    try:
        ports_path = _get_runtime_ports_path()
        if ports_path.exists():
            return json.loads(ports_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    """
    检查端口是否被占用

    Args:
        port: 端口号
        host: 主机地址

    Returns:
        bool: 端口是否被占用
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return False
        except OSError:
            return True


def find_available_port(start_port: int = 8000, max_attempts: int = 10, host: str = "0.0.0.0") -> int:
    """
    查找可用的端口

    Args:
        start_port: 起始端口
        max_attempts: 最大尝试次数
        host: 主机地址

    Returns:
        int: 可用的端口号
    """
    for port in range(start_port, start_port + max_attempts):
        if not is_port_in_use(port, host):
            return port
    return start_port


def check_and_get_port(
    default_port: int, host: str = "0.0.0.0", max_attempts: int = 10, port_name: str = "服务"
) -> Tuple[int, bool]:
    """
    检查端口并获取可用端口，返回端口和是否需要切换的标志

    Args:
        default_port: 默认端口
        host: 主机地址
        max_attempts: 最大尝试次数
        port_name: 端口名称（用于日志）

    Returns:
        Tuple[int, bool]: (实际使用的端口, 是否切换了端口)
    """
    port = default_port
    port_changed = False

    # 尝试绑定端口以确认是否真的被占用
    # 使用 SO_REUSEADDR 可以避免 TIME_WAIT 状态导致的假阳性
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.bind((host, port))
        # 如果成功绑定，说明端口可用
        test_socket.close()
    except OSError:
        # 端口被占用，查找可用端口
        available_port = find_available_port(port, max_attempts, host)
        if available_port != port:
            print(f"[警告] {port_name}端口 {port} 已被占用，使用端口 {available_port} 代替")
            port = available_port
            port_changed = True
        else:
            print(f"[警告] {port_name}端口 {port} 已被占用，将以后台模式继续")

    return port, port_changed


def get_port_with_fallback(
    preferred_port: int, fallback_ports: list, host: str = "0.0.0.0", port_name: str = "服务"
) -> int:
    """
    获取端口，优先尝试首选端口，失败则尝试备用端口列表

    Args:
        preferred_port: 首选端口
        fallback_ports: 备用端口列表
        host: 主机地址
        port_name: 端口名称（用于日志）

    Returns:
        int: 可用的端口号
    """
    # 尝试首选端口
    all_ports = [preferred_port] + fallback_ports

    for port in all_ports:
        if not is_port_in_use(port, host):
            if port != preferred_port:
                print(f"[警告] {port_name}首选端口 {preferred_port} 已被占用，使用备用端口 {port}")
            return port

    # 所有端口都被占用
    print(f"[警告] {port_name}所有可用端口 {all_ports} 都被占用，使用首选端口 {preferred_port}")
    return preferred_port

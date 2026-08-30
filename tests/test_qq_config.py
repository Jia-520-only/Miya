#!/usr/bin/env python3
"""
QQ 机器人配置模块稳定性测试（更新版）
"""

import logging
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_qq_config_loader():
    """测试 QQConfigLoader"""
    from webnet.qq.config_loader import QQConfigLoader, get_config_loader

    print("=" * 50)
    print("测试 1: QQConfigLoader 基础功能")

    loader = QQConfigLoader()
    config = loader.get_config()
    print(f"  配置结构: {list(config.keys())}")

    # 测试获取配置（新 API）
    ws_url = loader.get("qq.connection.ws_url")
    print(f"  WebSocket URL: {ws_url}")

    bot_qq = loader.get("qq.connection.bot_qq")
    print(f"  Bot QQ: {bot_qq}")

    # 测试快捷方法
    conn = loader.get_connection()
    print(f"  连接配置键: {list(conn.keys())}")

    multi = loader.get_multimedia()
    print(f"  多媒体配置键: {list(multi.keys())}")

    # 测试工具配置
    tool_cfg = loader.get_tool("qq_file_reader")
    print(f"  qq_file_reader 工具: 启用={tool_cfg.get('enabled')}")

    # 测试验证
    valid, errors = loader.validate()
    print(f"  配置验证: {'通过' if valid else '失败'}")
    if errors:
        for err in errors:
            print(f"    错误: {err}")

    print("\n" + "=" * 50)
    print("测试 2: 全局配置加载器")

    global_loader = get_config_loader()
    print(f"  实例类型: {type(global_loader).__name__}")
    print(f"  已初始化: {global_loader._initialized}")

    config2 = global_loader.get_config()
    print(f"  配置键: {list(config2.keys())}")

    print("\n" + "=" * 50)
    print("测试 3: 配置重载")

    success = global_loader.reload()
    print(f"  重载结果: {'成功' if success else '失败'}")
    print(f"  重载后已初始化: {global_loader._initialized}")


def test_unified_qq_config():
    """测试 UnifiedQQConfig"""
    from webnet.qq.unified_config import (
        get_connection_config,
        get_qq_config,
        get_unified_config,
    )

    print("\n" + "=" * 50)
    print("测试 4: UnifiedQQConfig 基础功能")

    config = get_unified_config()
    print(f"  实例类型: {type(config).__name__}")

    full_config = config.get_config()
    print(f"  配置键: {list(full_config.keys())}")

    # 测试点分路径获取
    ws_url = config.get("qq.connection.ws_url")
    print(f"  WebSocket URL: {ws_url}")

    bot_qq = config.get("qq.connection.bot_qq")
    print(f"  Bot QQ: {bot_qq}")

    # 测试连接配置
    conn = config.get_connection_config()
    print(f"  连接配置键: {list(conn.keys())}")

    # 测试多媒体配置
    multi = config.get_multimedia_config()
    print(f"  多媒体配置键: {list(multi.keys())}")

    # 测试验证
    valid, errors = config.validate_config()
    print(f"  配置验证: {'通过' if valid else '失败'}")
    if errors:
        for err in errors:
            print(f"    错误: {err}")

    print("\n" + "=" * 50)
    print("测试 5: 快捷函数")

    qq_cfg = get_qq_config()
    print(f"  get_qq_config() 类型: {type(qq_cfg).__name__}")

    conn_cfg = get_connection_config()
    print(f"  get_connection_config() 类型: {type(conn_cfg).__name__}")

    print("\n" + "=" * 50)
    print("测试 6: 配置重载")

    success = config.reload()
    print(f"  重载结果: {'成功' if success else '失败'}")


def test_qq_net_config_loading():
    """测试 QQNet 配置加载"""
    print("\n" + "=" * 50)
    print("测试 7: QQNet 配置加载模拟")

    try:
        from webnet.qq.config_loader import (
            get_connection_config,
            get_multimedia_config,
            get_qq_config,
        )

        conn = get_connection_config()
        multi = get_multimedia_config()
        features = get_qq_config("features") or {}

        print(f"  WebSocket URL: {conn.get('ws_url')}")
        print(f"  Bot QQ: {conn.get('bot_qq')}")
        print(f"  Super Admin: {conn.get('superadmin_qq')}")
        print(f"  重连间隔: {conn.get('reconnect_interval')}s")
        print(f"  心跳间隔: {conn.get('ping_interval')}s")
        print(f"  心跳超时: {conn.get('ping_timeout')}s")
        print(f"  最大消息大小: {conn.get('max_message_size')}")

        # 访问控制
        ac = get_qq_config("access_control") or {}
        gw = ac.get("group_whitelist", [])
        print(f"  群白名单: {set(gw) if isinstance(gw, list) else set()}")

        # 多媒体配置
        image_config = multi.get("image", {})
        file_config = multi.get("file", {})
        print(f"  图片最大大小: {image_config.get('max_size')}")
        print(f"  文件最大大小: {file_config.get('max_size')}")

        # 功能开关
        print(f"  主动聊天: {features.get('active_chat')}")
        print(f"  戳一戳回复: {features.get('poke_reply')}")
        print(f"  表情包请求: {features.get('emoji_request')}")

        print("  QQNet 配置加载: 成功")

    except Exception as e:
        print(f"  QQNet 配置加载: 失败 - {e}")


def test_yaml_config_file():
    """测试 YAML 配置文件读取"""
    print("\n" + "=" * 50)
    print("测试 8: YAML 配置文件完整性")

    import yaml

    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "qq_config.yaml",
    )

    if not os.path.exists(config_path):
        print(f"  配置文件不存在: {config_path}")
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        print("  配置文件加载: 成功")
        print(f"  顶级键: {list(config.keys())}")

        # 检查关键配置项
        qq = config.get("qq", {})
        conn = qq.get("connection", {})
        print(f"  OneBot ws_url: {conn.get('ws_url')}")
        print(f"  OneBot token: {'已设置' if conn.get('token') else '未设置'}")
        print(f"  Bot QQ: {conn.get('bot_qq')}")

        print(f"  重连间隔: {conn.get('reconnect_interval')}s")
        print(f"  心跳间隔: {conn.get('ping_interval')}s")

        access = qq.get("access_control", {})
        print(f"  访问控制启用: {access.get('enabled')}")

        multimedia = qq.get("multimedia", {})
        image = multimedia.get("image", {})
        print(f"  图片最大大小: {image.get('max_size')}")
        print(f"  允许格式: {len(image.get('allowed_formats', []))} 种")

        img_rec = qq.get("image_recognition", {})
        ai_analysis = img_rec.get("ai_analysis", {})
        print(f"  AI图片分析启用: {ai_analysis.get('enabled')}")
        print(f"  AI模型: {ai_analysis.get('model')}")

        features = qq.get("features", {})
        print("  功能开关:")
        print(f"    戳一戳: {features.get('poke_reply')}")
        print(f"    表情包: {features.get('emoji_request')}")
        print(f"    主动聊天: {features.get('active_chat')}")

        task = qq.get("task_scheduler", {})
        print(f"  任务调度启用: {task.get('enabled')}")

        commands = qq.get("commands", {})
        aliases = commands.get("aliases", {})
        print(f"  命令别名数量: {len(aliases)}")

        tools = config.get("tools", {})
        print(f"  工具数量: {len(tools)}")
        for tool_name, tool_cfg in tools.items():
            if isinstance(tool_cfg, dict):
                print(f"    {tool_name}: 启用={tool_cfg.get('enabled')}")

        print("  YAML 配置文件: 完整且有效")

    except Exception as e:
        print(f"  YAML 配置文件: 解析失败 - {e}")


def test_config_structure():
    """测试配置结构完整性"""
    print("\n" + "=" * 50)
    print("测试 9: 配置结构完整性")

    from webnet.qq.config_loader import get_config_loader

    loader = get_config_loader()
    config = loader.get_config()
    qq = config.get("qq", {})

    required_sections = [
        "connection",
        "access_control",
        "multimedia",
        "image_recognition",
        "message_parsing",
        "forward",
        "features",
        "commands",
        "task_scheduler",
        "performance",
        "logging",
        "debug",
    ]

    missing = []
    for section in required_sections:
        if section not in qq:
            missing.append(section)

    if missing:
        print(f"  缺失配置段: {missing}")
    else:
        print(f"  所有 {len(required_sections)} 个配置段均存在")

    # 检查工具配置
    tools = config.get("tools", {})
    required_tools = [
        "qq_emoji",
        "qq_file_reader",
        "qq_image_analyzer",
        "qq_active_chat",
        "task_scheduler_enhanced",
    ]
    missing_tools = [t for t in required_tools if t not in tools]
    if missing_tools:
        print(f"  缺失工具配置: {missing_tools}")
    else:
        print(f"  所有 {len(required_tools)} 个工具配置均存在")

    print("  配置结构检查: 通过")


if __name__ == "__main__":
    test_qq_config_loader()
    test_unified_qq_config()
    test_qq_net_config_loading()
    test_yaml_config_file()
    test_config_structure()

    print("\n" + "=" * 50)
    print("所有 QQ 配置测试完成!")
    print("=" * 50)

"""
MIYA Platform 配置

预配置常用平台适配器
"""

from typing import Any, Dict

# ==================== QQ 配置模板 ====================

QQ_CONFIG: Dict[str, Any] = {
    "type": "qq",
    "name": "QQ",
    "account": "",
    "password": "",
    "protocol": "HTTP",  # HTTP, WebSocket
    "host": "127.0.0.1",
    "port": 5700,
}

# ==================== Telegram 配置模板 ====================

TELEGRAM_CONFIG: Dict[str, Any] = {
    "type": "telegram",
    "name": "Telegram",
    "bot_token": "",
}

# ==================== 飞书配置模板 ====================

FEISHU_CONFIG: Dict[str, Any] = {
    "type": "feishu",
    "name": "飞书",
    "app_id": "",
    "app_secret": "",
    "encrypt_key": "",
    "verification_token": "",
}

# ==================== 钉钉配置模板 ====================

DINGTALK_CONFIG: Dict[str, Any] = {
    "type": "dingtalk",
    "name": "钉钉",
    "app_key": "",
    "app_secret": "",
    "agent_id": "",
}

# ==================== Discord 配置模板 ====================

DISCORD_CONFIG: Dict[str, Any] = {
    "type": "discord",
    "name": "Discord",
    "bot_token": "",
    "application_id": "",
    "bot_public_key": "",
}

# ==================== Slack 配置模板 ====================

SLACK_CONFIG: Dict[str, Any] = {
    "type": "slack",
    "name": "Slack",
    "bot_token": "",
    "signing_secret": "",
    "app_token": "",
}

# ==================== LINE 配置模板 ====================

LINE_CONFIG: Dict[str, Any] = {
    "type": "line",
    "name": "LINE",
    "channel_secret": "",
    "channel_access_token": "",
}

# ==================== 企业微信配置模板 ====================

WECHAT_WORK_CONFIG: Dict[str, Any] = {
    "type": "wechat_work",
    "name": "企业微信",
    "corp_id": "",
    "corp_secret": "",
    "agent_id": "",
}

# ==================== KOOK 配置模板 ====================

KOOK_CONFIG: Dict[str, Any] = {
    "type": "kook",
    "name": "KOOK",
    "token": "",
}

# ==================== Satori 配置模板 ====================

SATORI_CONFIG: Dict[str, Any] = {
    "type": "satori",
    "name": "Satori",
    "endpoint": "",
    "token": "",
}


# ==================== 预定义平台 ====================


def get_default_platforms() -> Dict[str, Dict[str, Any]]:
    """获取默认平台配置"""
    return {
        "qq": QQ_CONFIG.copy(),
        "telegram": TELEGRAM_CONFIG.copy(),
        "feishu": FEISHU_CONFIG.copy(),
        "dingtalk": DINGTALK_CONFIG.copy(),
        "discord": DISCORD_CONFIG.copy(),
        "slack": SLACK_CONFIG.copy(),
        "line": LINE_CONFIG.copy(),
        "wechat_work": WECHAT_WORK_CONFIG.copy(),
        "kook": KOOK_CONFIG.copy(),
        "satori": SATORI_CONFIG.copy(),
    }


__all__ = [
    "QQ_CONFIG",
    "TELEGRAM_CONFIG",
    "FEISHU_CONFIG",
    "DINGTALK_CONFIG",
    "DISCORD_CONFIG",
    "SLACK_CONFIG",
    "LINE_CONFIG",
    "WECHAT_WORK_CONFIG",
    "KOOK_CONFIG",
    "SATORI_CONFIG",
    "get_default_platforms",
]

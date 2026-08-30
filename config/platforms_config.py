"""
================================================================
        弥娅多平台配置中心 (MIYA Multi-Platform Config)
================================================================

支持的平台列表 (共18个):
  - QQ 官方机器人 (qqofficial)
  - QQ 官方 Webhook (qqofficial_webhook)
  - Telegram (telegram)
  - Discord (discord)
  - 飞书 (lark)
  - 钉钉 (dingtalk)
  - 企业微信 (wecom)
  - 企业微信 AI Bot (wecom_ai_bot)
  - 微信开放平台 (weixin_oc)
  - 微信公众号 (weixin_official_account)
  - Slack (slack)
  - LINE (line)
  - KOOK (kook)
  - Mattermost (mattermost)
  - Misskey (misskey)
  - Satori (satori)
  - OneBot/NapCat (aiocqhttp)

使用方法:
  1. 在对应平台申请机器人凭证
  2. 将 enabled 设为 True
  3. 填入凭证信息
  4. 运行 python start_platforms.py 启动所有平台

作者: 编程大师
===============================================================
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    if not os.environ.get("_MIYA_DOTENV_LOADED"):
        load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# v7.0: 所有凭据从环境变量读取，.env 文件中配置
# 获取环境变量值的辅助函数


def _env(key: str, default: str = "") -> str:
    from config.config_utils import get_api_key

    return get_api_key(key, default)


# ==================== QQ 官方机器人 ====================
# 环境变量: QQ_APPID, QQ_SECRET, QQ_OFFICIAL_BOT_QQ
# 申请地址: https://q.qq.com/
# 文档: https://bot.q.qq.com/wiki/develop/api/

QQ_OFFICIAL_CONFIG = {
    "enabled": True,
    "appid": _env("QQ_APPID"),
    "secret": _env("QQ_SECRET"),
    "bot_qq": _env("QQ_OFFICIAL_BOT_QQ", _env("QQ_BOT_QQ")),
    "enable_group_c2c": True,
    "enable_guild_direct_message": True,
    "sandbox": False,
}

# ==================== QQ 官方 Webhook 模式 ====================
# 申请地址: https://q.qq.com/
# 说明: 使用 Webhook 方式接收消息，无需保持长连接
# 适合: 服务器部署、无固定IP环境

QQ_OFFICIAL_WEBHOOK_CONFIG = {
    "enabled": False,
    "appid": "",
    "secret": "",
    "token": "",
    "bot_qq": "",
    # Webhook 回调地址 (需要公网可访问)
    "callback_url": "https://your-domain.com/qq/webhook",
    # 验证 Token
    "verify_token": "",
    # 沙箱模式
    "sandbox": False,
}

# ==================== Telegram ====================
# 申请地址: https://t.me/BotFather
# 步骤: 发送 /newbot -> 获取 bot_token
# 文档: https://core.telegram.org/bots/api
#
# 功能: 私聊、群组、频道、内联查询

TELEGRAM_CONFIG = {
    "enabled": False,
    "bot_token": "",  # 格式: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
    # 可选: 使用代理 (中国大陆可能需要)
    # "proxy": {
    #     "type": "http",  # http, socks5
    #     "host": "127.0.0.1",
    #     "port": 7890,
    # },
}

# ==================== Discord ====================
# 申请地址: https://discord.com/developers/applications
# 步骤: 创建应用 -> Bot -> 获取 Token
# 文档: https://discord.com/developers/docs/intro
#
# 功能: 服务器消息、私信、斜杠命令

DISCORD_CONFIG = {
    "enabled": False,  # 国内需代理
    "bot_token": _env("DISCORD_BOT_TOKEN"),
    # 可选: 设置 intents
    # "intents": ["guilds", "guild_messages", "direct_messages"],
}

# ==================== 飞书 ====================
# 申请地址: https://open.feishu.cn/
# 步骤: 创建企业自建应用 -> 获取 app_id 和 app_secret
# 文档: https://open.feishu.cn/document/home/index
#
# 功能: 单聊、群聊、消息卡片

FEISHU_CONFIG = {
    "enabled": True,
    "app_id": "",  # 从环境变量或 .env 读取, 勿硬编码
    "app_secret": "",  # 从环境变量或 .env 读取, 勿硬编码
    "verify_token": "",
}

# ==================== 钉钉 ====================
# 申请地址: https://open.dingtalk.com/
# 步骤: 创建应用 -> 获取 app_key 和 app_secret
# 文档: https://open.dingtalk.com/document
#
# 功能: 单聊、群聊、工作通知

DINGDING_CONFIG = {
    "enabled": False,
    "app_key": _env("DINGTALK_APP_KEY"),
    "app_secret": _env("DINGTALK_APP_SECRET"),
    "app_secret": "",  # 应用 App Secret
    # 可选: 机器人 Webhook
    # "webhook": "",
    # "secret": "",
}

# ==================== 企业微信 ====================
# 申请地址: https://work.weixin.qq.com/
# 步骤: 创建应用 -> 获取 corpid 和 corpsecret
# 文档: https://developer.work.weixin.qq.com/document/path/90556
#
# 功能: 应用消息、群机器人

WECOM_CONFIG = {
    "enabled": False,
    "corpid": "",  # 企业 ID
    "corpsecret": "",  # 应用 Secret (注意: 新版配置将 secret 重命名为 corpsecret)
    # 可选: 应用 AgentId (发送消息时需要)
    "agent_id": "",
    # 安全模式 (推荐): 填入后启用消息加解密
    "token": "",
    "encoding_aes_key": "",
}

# ==================== 企业微信 AI Bot ====================
# 申请地址: https://work.weixin.qq.com/
# 说明: 企业微信 AI 机器人模式
# 文档: https://developer.work.weixin.qq.com/document/path/95903

WECOM_AI_BOT_CONFIG = {
    "enabled": False,
    "corpid": "",
    "corpsecret": "",
    "bot_token": "",
    "encoding_aes_key": "",
}

# ==================== 微信开放平台 ====================
# 申请地址: https://open.weixin.qq.com/
# 步骤: 创建网站应用 -> 获取 appid 和 secret
# 文档: https://open.weixin.qq.com/cgi-bin/showdocument
#
# 功能: 微信扫码登录、微信消息

WEIXIN_OC_CONFIG = {
    "enabled": False,
    "appid": "",  # 应用 AppID
    "secret": "",  # 应用 AppSecret
    # 微信开放平台 — 个人微信 (需通过扫码获取 token)
    "weixin_oc_token": "",  # 登录后获取的 bot_token
    "weixin_oc_account_id": "",  # 登录后获取的账号 ID
    "weixin_oc_base_url": "https://ilinkai.weixin.qq.com",  # API 基础地址
    "weixin_oc_poll_interval": 5,  # 轮询间隔 (秒)
    # 可选: 消息加解密
    "token": "",
    "encoding_aes_key": "",
}

# ==================== 微信公众号 ====================
# 申请地址: https://mp.weixin.qq.com/
# 步骤: 注册公众号 -> 开发 -> 基本配置
# 文档: https://developers.weixin.qq.com/doc/offiaccount/GettingStarted/
#
# 功能: 关注回复、消息自动回复、菜单

WEIXIN_OFFICIAL_CONFIG = {
    "enabled": True,
    "appid": _env("WEIXIN_APP_ID"),  # 公众号 AppID
    "secret": _env("WEIXIN_APP_SECRET"),  # 公众号 AppSecret
    "token": _env("WEIXIN_TOKEN", "miya_token_2024"),  # 服务器配置 Token
    "encoding_aes_key": _env("WEIXIN_ENCODING_AES_KEY", ""),  # 消息加解密密钥 (43位)
    "port": 8090,  # webhook 服务端口
    # 主动发送模式 (推荐): 启用后绕过5秒被动回复限制，使用客服消息API主动回复
    "active_send_mode": True,
}

# ==================== 微信 iLink (新版) ====================
# 基于 weixin-ilink-client SDK 的个人微信接入
# 项目地址: https://github.com/69gg/weixin-ilink-client
# 步骤: 首次运行会显示终端 QR 码，微信扫码登录即可
# 文档: 非官方逆向协议，仅供学习实验
#
# 功能: 个人微信消息收发、图片/视频/文件

WEIXIN_ILINK_CONFIG = {
    "enabled": True,
    "account_id": "",  # 扫码登录后自动填充
    "bot_token": "",  # 扫码登录后自动填充
    "user_id": "",  # 扫码登录后自动填充
    "base_url": "https://ilinkai.weixin.qq.com",
    "cdn_base_url": "https://novac2c.cdn.weixin.qq.com/c2c",
    "bot_type": "3",
    "state_dir": "",  # 状态文件目录 (留空用系统默认)
}

# ==================== Slack ====================
# 申请地址: https://api.slack.com/apps
# 步骤: Create New App -> Bot Token Scopes -> Install
# 文档: https://api.slack.com/start/building
#
# 功能: 频道消息、私信、斜杠命令

SLACK_CONFIG = {
    "enabled": False,
    "bot_token": "",  # xoxb-开头的 Bot Token
    # 可选: App Token (用于 Socket Mode)
    # "app_token": "",
}

# ==================== LINE ====================
# 申请地址: https://developers.line.biz/console/
# 步骤: 创建 Channel -> Messaging API -> 获取 Token
# 文档: https://developers.line.biz/en/docs/messaging-api/overview/
#
# 功能: 单聊、群聊、Rich Menu

LINE_CONFIG = {
    "enabled": False,
    "channel_access_token": "",  # 长期 Channel Access Token
    "channel_secret": "",  # Channel Secret
}

# ==================== KOOK ====================
# 申请地址: https://developer.kookapp.cn/
# 步骤: 创建应用 -> 获取 token
# 文档: https://developer.kookapp.cn/doc/intro
#
# 功能: 频道消息、私信、卡片消息

KOOK_CONFIG = {
    "enabled": False,
    "token": "",  # Bot Token
    # 可选: Webhook 模式
    # "webhook_verify_key": "",
}

# ==================== Mattermost ====================
# 申请地址: 自建服务器管理后台
# 步骤: System Console -> Integrations -> Bot Accounts
# 文档: https://developers.mattermost.com/integrate/reference/
#
# 功能: 频道消息、私信

MATTERMOST_CONFIG = {
    "enabled": False,
    "server_url": "",  # Mattermost 服务器地址
    "token": "",  # Bot Access Token
    # 可选: 团队和频道
    # "team": "",
    # "channel": "",
}

# ==================== Misskey ====================
# 申请地址: Misskey 实例管理后台
# 步骤: 设置 -> 开发者 -> 创建应用
# 文档: https://misskey-hub.net/docs/
#
# 功能: 时间线、私信、通知

MISSKEY_CONFIG = {
    "enabled": False,
    "instance_url": "",  # Misskey 实例地址 (如: https://misskey.io)
    "token": "",  # Access Token
}

# ==================== Satori ====================
# 说明: Satori 是通用聊天平台协议
# 文档: https://satori.js.org/zh-CN/
#
# 支持: Koishi、OneBot、Telegram 等多种协议

SATORI_CONFIG = {
    "enabled": False,
    "host": "127.0.0.1",
    "port": 5500,
    # 可选: 认证
    # "token": "",
}

# ==================== OneBot / NapCat ====================
# 说明: 使用 OneBot v11 协议连接 NapCat/go-cqhttp
# NapCat: https://github.com/NapNeko/NapCatQQ
# go-cqhttp: https://github.com/Mrs4s/go-cqhttp
#
# 功能: 群聊、私聊、消息段、闪照、撤回
#
# 注意: 此平台通过 run/qq_main.py 单独启动
# 配置在 config/.env 中

AIOCQHTTP_CONFIG = {
    "enabled": True,
    # WebSocket 反向连接地址 (NapCat 连接到弥娅)
    "ws_reverse_host": "127.0.0.1",
    "ws_reverse_port": 8095,
    # 或者正向连接 (弥娅连接到 NapCat)
    # "ws_url": "ws://127.0.0.1:3001",
    # 访问令牌
    "token": "",
}


# ==================== 桌面端 ====================
# 弥娅桌面应用前端 (Electron + Vue 3)
# 通过 Web API (/api/chat) 连接，通过 WebSocket 接收主动消息推送
# v4.1.11: 支持 WS 直推主动消息 (management_api.push_proactive_message)

DESKTOP_CONFIG = {
    "enabled": True,
    "name": "桌面端",
    "description": "弥娅桌面应用 - MIYA Desktop",
    "delivery_mode": "ws_push",
    "support_proactive_message": True,
}


# ==================== 手机端 ====================
# 弥娅手机端应用 (React Native / Expo)
# 通过 Web API (/api/chat/send) 发送用户消息
# v4.1.11: 主动消息通过 WS 推送通知 + GET /api/chat/pending/ 拉取
#       手机端连接 WS 时会收到 mobile_pending 通知，然后拉取消息

MOBILE_CONFIG = {
    "enabled": True,
    "name": "手机端",
    "description": "弥娅手机端 - MIYA Mobile",
    "delivery_mode": "ws_poll",
    "support_proactive_message": True,
}


# =================================================================
#                      平台汇总配置
# =================================================================

ALL_PLATFORMS = {
    # QQ 系列
    "qqofficial": QQ_OFFICIAL_CONFIG,
    "qqofficial_webhook": QQ_OFFICIAL_WEBHOOK_CONFIG,
    "aiocqhttp": AIOCQHTTP_CONFIG,
    # 国际平台
    "telegram": TELEGRAM_CONFIG,
    "discord": DISCORD_CONFIG,
    "slack": SLACK_CONFIG,
    "line": LINE_CONFIG,
    # 国内平台
    "lark": FEISHU_CONFIG,
    "dingtalk": DINGDING_CONFIG,
    "wecom": WECOM_CONFIG,
    "wecom_ai_bot": WECOM_AI_BOT_CONFIG,
    "weixin_oc": WEIXIN_OC_CONFIG,
    "weixin_official_account": WEIXIN_OFFICIAL_CONFIG,
    "weixin_ilink": WEIXIN_ILINK_CONFIG,
    # 社区平台
    "kook": KOOK_CONFIG,
    "mattermost": MATTERMOST_CONFIG,
    "misskey": MISSKEY_CONFIG,
    "satori": SATORI_CONFIG,
    # 内置平台
    "desktop": DESKTOP_CONFIG,
    "mobile": MOBILE_CONFIG,
}


def get_enabled_platforms():
    """获取所有启用的平台"""
    return {platform_id: config for platform_id, config in ALL_PLATFORMS.items() if config.get("enabled", False)}


def get_platform_config(platform_id: str):
    """获取指定平台的配置"""
    return ALL_PLATFORMS.get(platform_id, {})


def list_all_platforms():
    """列出所有可用平台及其状态"""
    result = []
    for platform_id, config in ALL_PLATFORMS.items():
        status = "✅ 已启用" if config.get("enabled", False) else "❌ 未启用"
        result.append(
            {
                "id": platform_id,
                "status": status,
                "enabled": config.get("enabled", False),
            }
        )
    return result


# =================================================================
#                      平台申请指南
# =================================================================

PLATFORM_GUIDE = {
    "qqofficial": {
        "name": "QQ 官方机器人",
        "url": "https://q.qq.com/",
        "credentials": ["appid", "secret"],
        "docs": "https://bot.q.qq.com/wiki/develop/api/",
    },
    "telegram": {
        "name": "Telegram",
        "url": "https://t.me/BotFather",
        "credentials": ["bot_token"],
        "docs": "https://core.telegram.org/bots/api",
    },
    "discord": {
        "name": "Discord",
        "url": "https://discord.com/developers/applications",
        "credentials": ["bot_token"],
        "docs": "https://discord.com/developers/docs/intro",
    },
    "lark": {
        "name": "飞书",
        "url": "https://open.feishu.cn/",
        "credentials": ["app_id", "app_secret"],
        "docs": "https://open.feishu.cn/document/home/index",
    },
    "dingtalk": {
        "name": "钉钉",
        "url": "https://open.dingtalk.com/",
        "credentials": ["app_key", "app_secret"],
        "docs": "https://open.dingtalk.com/document",
    },
    "wecom": {
        "name": "企业微信",
        "url": "https://work.weixin.qq.com/",
        "credentials": ["corpid", "corpsecret"],
        "docs": "https://developer.work.weixin.qq.com/document/path/90556",
    },
    "slack": {
        "name": "Slack",
        "url": "https://api.slack.com/apps",
        "credentials": ["bot_token"],
        "docs": "https://api.slack.com/start/building",
    },
    "line": {
        "name": "LINE",
        "url": "https://developers.line.biz/console/",
        "credentials": ["channel_access_token", "channel_secret"],
        "docs": "https://developers.line.biz/en/docs/messaging-api/overview/",
    },
    "kook": {
        "name": "KOOK",
        "url": "https://developer.kookapp.cn/",
        "credentials": ["token"],
        "docs": "https://developer.kookapp.cn/doc/intro",
    },
    "mattermost": {
        "name": "Mattermost",
        "url": "自建服务器",
        "credentials": ["server_url", "token"],
        "docs": "https://developers.mattermost.com/integrate/reference/",
    },
    "misskey": {
        "name": "Misskey",
        "url": "Misskey 实例",
        "credentials": ["instance_url", "token"],
        "docs": "https://misskey-hub.net/docs/",
    },
}


def get_platform_guide(platform_id: str = None):
    """获取平台申请指南"""
    if platform_id:
        return PLATFORM_GUIDE.get(platform_id)
    return PLATFORM_GUIDE

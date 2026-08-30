"""
QQ 配置与记忆命令模块

历史遗留的 QQNet / QQOneBotClient 客户端已废弃并清理，
OneBot 平台接入现由 core/unified_platform_impl/onebot_platform.py 负责。

保留的活跃模块：
- config_loader.py: QQ 配置加载（config/settings.py 依赖）
- unified_config.py: 统一 QQ 配置（.env + qq_config.yaml）
- memory_commands.py: 记忆查询快捷命令（decision_hub 依赖）
"""

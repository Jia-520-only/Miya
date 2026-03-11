"""
权限节点定义 - Miya系统完整权限列表

为每个Miya功能和工具定义权限节点
"""

TOOL_PERMISSIONS = {
    # 工具权限节点
    "tool.web_search": "网页搜索工具",
    "tool.file_access": "文件访问工具",
    "tool.code_generator": "代码生成工具",
    "tool.data_analyze": "数据分析工具",
    "tool.chart_generate": "图表生成工具",
    "tool.terminal_command": "终端命令执行工具",
    "tool.memory_search": "记忆搜索工具",
    "tool.github_push": "GitHub代码推送工具",
    "tool.github_pull": "GitHub代码拉取工具",
    "tool.send_message": "发送消息工具",
    "tool.system_info": "系统信息查询工具",

    # Agent权限节点
    "agent.task.create": "创建任务",
    "agent.task.execute": "执行任务",
    "agent.task.manage": "管理任务",
    "agent.multi_agent": "多Agent协作",

    # API权限节点
    "api.access": "基础API访问",
    "api.read": "读取数据",
    "api.write": "写入数据",
    "api.github.push": "GitHub推送权限",
    "api.github.pull": "GitHub拉取权限",

    # 系统权限节点
    "system.config.read": "读取系统配置",
    "system.config.write": "修改系统配置",
    "system.manage": "系统管理",

    # 用户权限节点
    "user.manage.*": "用户管理（所有权限）",
    "user.manage.add": "添加用户",
    "user.manage.remove": "移除用户",
    "user.manage.list": "列出用户",

    # 权限管理节点
    "permission.check": "检查权限",
    "permission.grant": "授予权限",
    "permission.revoke": "撤销权限",
    "permission.list": "列出权限",

    # 游戏权限节点
    "game.trpg.start": "启动TRPG游戏",
    "game.trpg.join": "加入TRPG游戏",
    "game.trpg.manage": "管理TRPG游戏",

    # 群组权限节点
    "group.chat": "群组聊天",
    "group.manage": "群组管理",
}


# 默认权限组定义（已在subnet.py中定义，此处仅作为参考）
DEFAULT_PERMISSION_GROUPS = {
    "SuperAdmin": {
        "description": "超级管理员",
        "permissions": ["*"]
    },
    "Admin": {
        "description": "管理员",
        "permissions": [
            "system.config.*",
            "user.manage.*",
            "tool.*",
            "agent.*",
            "api.*"
        ]
    },
    "Developer": {
        "description": "开发者",
        "permissions": [
            "tool.code_generator",
            "tool.file_access",
            "api.github.push",
            "agent.task.execute",
            "tool.terminal_command"
        ]
    },
    "User": {
        "description": "普通用户",
        "permissions": [
            "tool.web_search",
            "tool.data_analyze",
            "tool.chart_generate",
            "api.read",
            "agent.task.create",
            "api.access"
        ]
    },
    "Guest": {
        "description": "访客",
        "permissions": [
            "tool.web_search",
            "api.read"
        ]
    }
}


def get_tool_permission(tool_name: str) -> str:
    """获取工具对应的权限节点"""
    # 简单的映射规则：tool.工具名
    return f"tool.{tool_name}"


def check_tool_permission(user_id: str, tool_name: str) -> bool:
    """
    检查用户是否有工具权限

    Args:
        user_id: 用户ID（统一格式）
        tool_name: 工具名称

    Returns:
        是否有权限
    """
    from .permission_core import PermissionCore
    perm_core = PermissionCore()
    permission = get_tool_permission(tool_name)
    return perm_core.check_permission(user_id, permission)

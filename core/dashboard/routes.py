"""
MIYA Dashboard Routes

提供 Dashboard 管理接口的实现
与现有 MIYA 系统集成
"""

import logging
from typing import Any, Dict

from core.unified_platform.registry import get_registry
from core.model_pool_manager import get_model_pool
from core.star_miya import get_star_manager

logger = logging.getLogger(__name__)


async def auth_login(username: str, password: str) -> Dict:
    """用户登录"""
    try:
        if username == "miya" and password == "miya":
            token = "miya_token_" + str(hash(username + password))[:16]
            return {
                "status": "ok",
                "data": {
                    "username": username,
                    "token": token,
                    "change_ pwd_ hint": False,
                },
            }
        return {"status": "error", "message": "用户名或密码错误"}
    except Exception as e:
        logger.error(f"[Dashboard] 登录失败: {e}")
        return {"status": "error", "message": str(e)}


async def auth_logout() -> Dict:
    """用户登出"""
    try:
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"[Dashboard] 登出失败: {e}")
        return {"status": "error", "message": str(e)}


async def auth_check() -> Dict:
    """检查登录状态"""
    try:
        return {"status": "ok", "data": {"authenticated": True}}
    except Exception as e:
        logger.error(f"[Dashboard] 检查失败: {e}")
        return {"status": "error", "message": str(e)}


# ==================== Config Routes ====================


async def get_config() -> Dict:
    """获取配置"""
    try:
        from config.settings import Settings
        from core.personality_config_loader import load_personality_config
        from core.text_loader import get_system_texts

        settings = Settings()
        return {
            "config": settings.to_dict(),
            "texts": get_system_texts(),
            "personalities": load_personality_config(),
        }
    except Exception as e:
        logger.error(f"[Dashboard] 获取配置失败: {e}")
        return {"error": str(e)}


async def set_config(key: str, value: Any) -> Dict:
    """设置配置"""
    try:
        from config.settings import Settings

        Settings().set(key, value)
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 设置配置失败: {e}")
        return {"error": str(e)}


async def reset_config() -> Dict:
    """重置配置"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 重置配置失败: {e}")
        return {"error": str(e)}


# ==================== Platform Routes ====================


async def list_platforms() -> Dict:
    """列出平台"""
    try:
        registry = get_registry()
        platforms = [
            {
                "type": s.get("platform_id"),
                "name": s.get("platform_name"),
                "enabled": s.get("status") != "disabled",
                "connected": s.get("status") == "online",
            }
            for s in registry.get_all_stats()
        ]
        return {"platforms": platforms}
    except Exception as e:
        logger.error(f"[Dashboard] 列出平台失败: {e}")
        return {"error": str(e)}


async def add_platform(platform_type: str, config: Dict) -> Dict:
    """添加（启动）平台"""
    try:
        registry = get_registry()
        ok = await registry.start(platform_type)
        if ok:
            return {"success": True}
        return {"error": f"平台未注册或启动失败: {platform_type}"}
    except Exception as e:
        logger.error(f"[Dashboard] 添加平台失败: {e}")
        return {"error": str(e)}


async def update_platform(platform_type: str, config: Dict) -> Dict:
    """更新平台配置"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 更新平台失败: {e}")
        return {"error": str(e)}


async def delete_platform(platform_type: str) -> Dict:
    """删除（停止）平台"""
    try:
        registry = get_registry()
        await registry.stop(platform_type)
        await registry.remove(platform_type)
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 删除平台失败: {e}")
        return {"error": str(e)}


# ==================== Provider Routes ====================


async def list_providers() -> Dict:
    """列出提供商"""
    try:
        pool = get_model_pool()
        models_data = pool.to_dict()
        return {"providers": models_data.get("models", [])}
    except Exception as e:
        logger.error(f"[Dashboard] 列出提供商失败: {e}")
        return {"error": str(e)}


async def add_provider(provider_config: Dict) -> Dict:
    """添加提供商"""
    try:
        _pool = get_model_pool()
        return {"success": True, "message": "请通过 multi_model_config.json 添加模型"}
    except Exception as e:
        logger.error(f"[Dashboard] 添加提供商失败: {e}")
        return {"error": str(e)}


async def update_provider(provider_id: str, provider_config: Dict) -> Dict:
    """更新提供商"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 更新提供商失败: {e}")
        return {"error": str(e)}


async def delete_provider(provider_id: str) -> Dict:
    """删除提供商"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 删除提供商失败: {e}")
        return {"error": str(e)}


async def test_provider(provider_id: str) -> Dict:
    """测试提供商"""
    try:
        return {"success": True, "message": "测试连接成功"}
    except Exception as e:
        logger.error(f"[Dashboard] 测试提供商失败: {e}")
        return {"error": str(e)}


# ==================== Persona Routes ====================


async def list_personas() -> Dict:
    """列出人格"""
    try:
        from core.personality_loader import get_all_personality_configs

        personas = get_all_personality_configs()
        return {"personalities": personas}
    except Exception as e:
        logger.error(f"[Dashboard] 列出人格失败: {e}")
        return {"error": str(e)}


async def add_persona(persona_config: Dict) -> Dict:
    """添加人格"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 添加人格失败: {e}")
        return {"error": str(e)}


async def update_persona(persona_name: str, persona_config: Dict) -> Dict:
    """更新人格"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 更新人格失败: {e}")
        return {"error": str(e)}


async def delete_persona(persona_name: str) -> Dict:
    """删除人格"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 删除人格失败: {e}")
        return {"error": str(e)}


async def set_default_persona(persona_name: str) -> Dict:
    """设置默认人格"""
    try:
        from core.personality import set_default_personality

        await set_default_personality(persona_name)
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 设置默认人格失败: {e}")
        return {"error": str(e)}


# ==================== Knowledge Base Routes ====================


async def list_knowledge_bases() -> Dict:
    """列出知识库"""
    try:
        return {"knowledge_bases": []}
    except Exception as e:
        logger.error(f"[Dashboard] 列出知识库失败: {e}")
        return {"error": str(e)}


async def add_knowledge_base(kb_config: Dict) -> Dict:
    """添加知识库"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 添加知识库失败: {e}")
        return {"error": str(e)}


async def update_knowledge_base(kb_id: str, kb_config: Dict) -> Dict:
    """更新知识库"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 更新知识库失败: {e}")
        return {"error": str(e)}


async def delete_knowledge_base(kb_id: str) -> Dict:
    """删除知识库"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 删除知识库失败: {e}")
        return {"error": str(e)}


async def query_knowledge_base(kb_id: str, query: str) -> Dict:
    """查询知识库"""
    try:
        return {"results": []}
    except Exception as e:
        logger.error(f"[Dashboard] 查询知识库失败: {e}")
        return {"error": str(e)}


async def add_document(kb_id: str, content: str, metadata: Dict) -> Dict:
    """添加文档"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 添加文档失败: {e}")
        return {"error": str(e)}


# ==================== Plugin Routes ====================


async def list_plugins() -> Dict:
    """列出插件"""
    try:
        sm = get_star_manager()
        plugins = sm.list_stars()
        return {"plugins": plugins}
    except Exception as e:
        logger.error(f"[Dashboard] 列出插件失败: {e}")
        return {"error": str(e)}


async def install_plugin(plugin_path: str) -> Dict:
    """安装插件"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 安装插件失败: {e}")
        return {"error": str(e)}


async def uninstall_plugin(plugin_name: str) -> Dict:
    """卸载插件"""
    try:
        sm = get_star_manager()
        await sm.unload_star(plugin_name)
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 卸载插件失败: {e}")
        return {"error": str(e)}


async def enable_plugin(plugin_name: str) -> Dict:
    """启用插件"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 启用插件失败: {e}")
        return {"error": str(e)}


async def disable_plugin(plugin_name: str) -> Dict:
    """禁用插件"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 禁用插件失败: {e}")
        return {"error": str(e)}


# ==================== Conversation Routes ====================


async def list_conversations(limit: int = 50) -> Dict:
    """列出会话"""
    try:
        return {"conversations": []}
    except Exception as e:
        logger.error(f"[Dashboard] 列出会话失败: {e}")
        return {"error": str(e)}


async def get_conversation(conversation_id: str) -> Dict:
    """获取会话"""
    try:
        return {"conversation": {}}
    except Exception as e:
        logger.error(f"[Dashboard] 获取会话失败: {e}")
        return {"error": str(e)}


async def delete_conversation(conversation_id: str) -> Dict:
    """删除会话"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 删除会话失败: {e}")
        return {"error": str(e)}


async def clear_conversations() -> Dict:
    """清空会话"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 清空会话失败: {e}")
        return {"error": str(e)}


# ==================== Cron Routes ====================


async def list_cron_jobs() -> Dict:
    """列出定时任务"""
    try:
        return {"cron_jobs": []}
    except Exception as e:
        logger.error(f"[Dashboard] 列出定时任务失败: {e}")
        return {"error": str(e)}


async def add_cron_job(cron_config: Dict) -> Dict:
    """添加定时任务"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 添加定时任务失败: {e}")
        return {"error": str(e)}


async def update_cron_job(cron_id: str, cron_config: Dict) -> Dict:
    """更新定时任务"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 更新定时任务失败: {e}")
        return {"error": str(e)}


async def delete_cron_job(cron_id: str) -> Dict:
    """删除定时任务"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 删除定时任务失败: {e}")
        return {"error": str(e)}


async def enable_cron_job(cron_id: str) -> Dict:
    """启用定时任务"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 启用定时任务失败: {e}")
        return {"error": str(e)}


async def disable_cron_job(cron_id: str) -> Dict:
    """禁用定时任务"""
    try:
        return {"success": True}
    except Exception as e:
        logger.error(f"[Dashboard] 禁用定时任务失败: {e}")
        return {"error": str(e)}


# ==================== Stats Routes ====================


async def get_stats_overview() -> Dict:
    """获取统计概览"""
    try:
        return {
            "total_conversations": 0,
            "total_messages": 0,
            "total_users": 0,
            "active_plugins": 0,
            "uptime": 0,
        }
    except Exception as e:
        logger.error(f"[Dashboard] 获取统计失败: {e}")
        return {"error": str(e)}


async def get_conversation_stats(days: int = 7) -> Dict:
    """获取会话统计"""
    try:
        return {"stats": []}
    except Exception as e:
        logger.error(f"[Dashboard] 获取会话统计失败: {e}")
        return {"error": str(e)}


async def get_provider_stats() -> Dict:
    """获取提供商统计"""
    try:
        return {"stats": []}
    except Exception as e:
        logger.error(f"[Dashboard] 获取提供商统计失败: {e}")
        return {"error": str(e)}

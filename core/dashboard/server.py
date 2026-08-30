"""
MIYA Dashboard API Server

提供 Web API 接口，复用 AstrBot 设计
"""

import logging

from quart import Quart, jsonify, request

from core.dashboard import get_dashboard_api
from core.dashboard import routes as dashboard_routes

logger = logging.getLogger(__name__)


class DashboardServer:
    """Dashboard API 服务器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, host: str = "0.0.0.0", port: int = 6185):
        if self._initialized:
            return

        self.host = host
        self.port = port
        self.app = Quart(__name__)
        self._api = get_dashboard_api()

        # 注册路由
        self._register_routes()

        self._initialized = True
        logger.info(f"[DashboardServer] 初始化完成 {host}:{port}")

    def _register_auth_routes(self):
        """注册认证路由"""

        @self.app.route("/api/auth/login", methods=["POST", "OPTIONS"])
        async def login():
            if request.method == "OPTIONS":
                return jsonify({"status": "ok"})
            data = await request.json
            username = data.get("username", "")
            password = data.get("password", "")
            result = await dashboard_routes.auth_login(username, password)
            return jsonify(result)

        @self.app.route("/api/auth/logout", methods=["POST"])
        async def logout():
            result = await dashboard_routes.auth_logout()
            return jsonify(result)

        @self.app.route("/api/auth/check", methods=["GET"])
        async def auth_check():
            result = await dashboard_routes.auth_check()
            return jsonify(result)

        @self.app.route("/api/config/get", methods=["GET"])
        async def get_config_api():
            return jsonify(await dashboard_routes.get_config())

        @self.app.route("/api/config/provider/template", methods=["GET"])
        async def get_provider_template():
            return jsonify(await dashboard_routes.list_providers())

    def _register_routes(self):
        """注册 Quart 路由"""
        self._register_auth_routes()

        @self.app.route("/api/config", methods=["GET"])
        async def get_config():
            return jsonify(await dashboard_routes.get_config())

        @self.app.route("/api/config", methods=["POST"])
        async def set_config():
            data = await request.json
            key = data.get("key")
            value = data.get("value")
            return jsonify(await dashboard_routes.set_config(key, value))

        @self.app.route("/api/platforms", methods=["GET"])
        async def list_platforms():
            return jsonify(await dashboard_routes.list_platforms())

        @self.app.route("/api/platforms", methods=["POST"])
        async def add_platform():
            data = await request.json
            platform_type = data.get("type")
            config = data.get("config", {})
            return jsonify(await dashboard_routes.add_platform(platform_type, config))

        @self.app.route("/api/platforms/<platform_type>", methods=["PUT"])
        async def update_platform(platform_type: str):
            data = await request.json
            return jsonify(await dashboard_routes.update_platform(platform_type, data))

        @self.app.route("/api/platforms/<platform_type>", methods=["DELETE"])
        async def delete_platform(platform_type: str):
            return jsonify(await dashboard_routes.delete_platform(platform_type))

        @self.app.route("/api/providers", methods=["GET"])
        async def list_providers():
            return jsonify(await dashboard_routes.list_providers())

        @self.app.route("/api/providers", methods=["POST"])
        async def add_provider():
            data = await request.json
            return jsonify(await dashboard_routes.add_provider(data))

        @self.app.route("/api/providers/<provider_id>", methods=["PUT"])
        async def update_provider(provider_id: str):
            data = await request.json
            return jsonify(await dashboard_routes.update_provider(provider_id, data))

        @self.app.route("/api/providers/<provider_id>", methods=["DELETE"])
        async def delete_provider(provider_id: str):
            return jsonify(await dashboard_routes.delete_provider(provider_id))

        @self.app.route("/api/providers/<provider_id>/test", methods=["POST"])
        async def test_provider(provider_id: str):
            return jsonify(await dashboard_routes.test_provider(provider_id))

        @self.app.route("/api/personalities", methods=["GET"])
        async def list_personas():
            return jsonify(await dashboard_routes.list_personas())

        @self.app.route("/api/personalities", methods=["POST"])
        async def add_persona():
            data = await request.json
            return jsonify(await dashboard_routes.add_persona(data))

        @self.app.route("/api/personalities/<persona_name>", methods=["PUT"])
        async def update_persona(persona_name: str):
            data = await request.json
            return jsonify(await dashboard_routes.update_persona(persona_name, data))

        @self.app.route("/api/personalities/<persona_name>", methods=["DELETE"])
        async def delete_persona(persona_name: str):
            return jsonify(await dashboard_routes.delete_persona(persona_name))

        @self.app.route("/api/personalities/<persona_name>/default", methods=["POST"])
        async def set_default_persona(persona_name: str):
            return jsonify(await dashboard_routes.set_default_persona(persona_name))

        @self.app.route("/api/knowledge_bases", methods=["GET"])
        async def list_knowledge_bases():
            return jsonify(await dashboard_routes.list_knowledge_bases())

        @self.app.route("/api/knowledge_bases", methods=["POST"])
        async def add_knowledge_base():
            data = await request.json
            return jsonify(await dashboard_routes.add_knowledge_base(data))

        @self.app.route("/api/knowledge_bases/<kb_id>", methods=["PUT"])
        async def update_knowledge_base(kb_id: str):
            data = await request.json
            return jsonify(await dashboard_routes.update_knowledge_base(kb_id, data))

        @self.app.route("/api/knowledge_bases/<kb_id>", methods=["DELETE"])
        async def delete_knowledge_base(kb_id: str):
            return jsonify(await dashboard_routes.delete_knowledge_base(kb_id))

        @self.app.route("/api/knowledge_bases/<kb_id>/query", methods=["POST"])
        async def query_knowledge_base(kb_id: str):
            data = await request.json
            query = data.get("query", "")
            return jsonify(await dashboard_routes.query_knowledge_base(kb_id, query))

        @self.app.route("/api/knowledge_bases/<kb_id>/documents", methods=["POST"])
        async def add_document(kb_id: str):
            data = await request.json
            content = data.get("content", "")
            metadata = data.get("metadata", {})
            return jsonify(await dashboard_routes.add_document(kb_id, content, metadata))

        @self.app.route("/api/plugins", methods=["GET"])
        async def list_plugins():
            return jsonify(await dashboard_routes.list_plugins())

        @self.app.route("/api/plugins", methods=["POST"])
        async def install_plugin():
            data = await request.json
            plugin_path = data.get("path", "")
            return jsonify(await dashboard_routes.install_plugin(plugin_path))

        @self.app.route("/api/plugins/<plugin_name>", methods=["DELETE"])
        async def uninstall_plugin(plugin_name: str):
            return jsonify(await dashboard_routes.uninstall_plugin(plugin_name))

        @self.app.route("/api/plugins/<plugin_name>/enable", methods=["POST"])
        async def enable_plugin(plugin_name: str):
            return jsonify(await dashboard_routes.enable_plugin(plugin_name))

        @self.app.route("/api/plugins/<plugin_name>/disable", methods=["POST"])
        async def disable_plugin(plugin_name: str):
            return jsonify(await dashboard_routes.disable_plugin(plugin_name))

        @self.app.route("/api/conversations", methods=["GET"])
        async def list_conversations():
            limit = request.args.get("limit", 50, type=int)
            return jsonify(await dashboard_routes.list_conversations(limit))

        @self.app.route("/api/conversations/<conversation_id>", methods=["GET"])
        async def get_conversation(conversation_id: str):
            return jsonify(await dashboard_routes.get_conversation(conversation_id))

        @self.app.route("/api/conversations/<conversation_id>", methods=["DELETE"])
        async def delete_conversation(conversation_id: str):
            return jsonify(await dashboard_routes.delete_conversation(conversation_id))

        @self.app.route("/api/conversations", methods=["DELETE"])
        async def clear_conversations():
            return jsonify(await dashboard_routes.clear_conversations())

        @self.app.route("/api/cron", methods=["GET"])
        async def list_cron_jobs():
            return jsonify(await dashboard_routes.list_cron_jobs())

        @self.app.route("/api/cron", methods=["POST"])
        async def add_cron_job():
            data = await request.json
            return jsonify(await dashboard_routes.add_cron_job(data))

        @self.app.route("/api/cron/<cron_id>", methods=["PUT"])
        async def update_cron_job(cron_id: str):
            data = await request.json
            return jsonify(await dashboard_routes.update_cron_job(cron_id, data))

        @self.app.route("/api/cron/<cron_id>", methods=["DELETE"])
        async def delete_cron_job(cron_id: str):
            return jsonify(await dashboard_routes.delete_cron_job(cron_id))

        @self.app.route("/api/cron/<cron_id>/enable", methods=["POST"])
        async def enable_cron_job(cron_id: str):
            return jsonify(await dashboard_routes.enable_cron_job(cron_id))

        @self.app.route("/api/cron/<cron_id>/disable", methods=["POST"])
        async def disable_cron_job(cron_id: str):
            return jsonify(await dashboard_routes.disable_cron_job(cron_id))

        @self.app.route("/api/stats", methods=["GET"])
        async def get_stats():
            return jsonify(await dashboard_routes.get_stats_overview())

        @self.app.route("/api/stats/conversations", methods=["GET"])
        async def get_conversation_stats():
            days = request.args.get("days", 7, type=int)
            return jsonify(await dashboard_routes.get_conversation_stats(days))

        @self.app.route("/api/stats/providers", methods=["GET"])
        async def get_provider_stats():
            return jsonify(await dashboard_routes.get_provider_stats())

        # 健康检查
        @self.app.route("/health", methods=["GET"])
        async def health():
            return jsonify({"status": "ok"})

    async def run(self):
        """运行服务器"""
        await self.app.run(host=self.host, port=self.port)

    async def start(self):
        """启动服务器"""
        logger.info(f"[DashboardServer] 启动服务器 {self.host}:{self.port}")
        await self.run()


def get_dashboard_server(host: str = "0.0.0.0", port: int = 6185) -> DashboardServer:
    """获取Dashboard服务器实例"""
    return DashboardServer(host, port)


# 便捷启动函数
async def start_dashboard_server(host: str = "0.0.0.0", port: int = 6185):
    """启动Dashboard服务器"""
    server = get_dashboard_server(host, port)
    await server.start()

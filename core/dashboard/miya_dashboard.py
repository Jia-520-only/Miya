"""
弥娅系统 - Dashboard 服务器 v2

完整功能:
- 系统状态面板
- 配置管理
- 平台管理
- 会话管理
"""

import logging
import os
from typing import Optional

logger = logging.getLogger("Miya.Dashboard")


# 尝试导入 Quart
try:
    from quart import Quart, jsonify, request, send_from_directory, websocket

    HAS_QUART = True
except ImportError:
    HAS_QUART = False
    Quart = None


class MiyaDashboard:
    """弥娅 Dashboard - WebUI 管理界面"""

    VERSION = "4.1.11"

    def __init__(self, core_lifecycle, shutdown_event, webui_dir: str = None):
        from core.miya_config import get_miya_config

        self.core_lifecycle = core_lifecycle
        self.shutdown_event = shutdown_event
        self.webui_dir = webui_dir
        self.config = get_miya_config()

        self.app = None
        self.port = self.config.get("dashboard", {}).get("port", 6185)
        self.host = self.config.get("dashboard", {}).get("host", "0.0.0.0")

        # 检查环境变量
        self.port = int(os.environ.get("MIYA_DASHBOARD_PORT", self.port))
        self.host = os.environ.get("MIYA_DASHBOARD_HOST", self.host)

    def run(self):
        """启动 Dashboard"""
        if not HAS_QUART:
            logger.warning("Quart 未安装，Dashboard 不可用")
            logger.info("请运行: pip install quart hypercorn")
            return None

        # 确定 WebUI 目录
        webui_path = self._get_webui_path()

        # 创建 Quart 应用
        self.app = Quart("MiyaDashboard", static_folder=webui_path)

        # 检查是否启用
        if not self.config.get("dashboard", {}).get("enable", False):
            logger.info("Dashboard 已禁用")
            return None

        # 初始化路由
        self._setup_routes()

        # 启动服务器
        return self._start_server()

    def _get_webui_path(self) -> Optional[str]:
        """获取 WebUI 目录"""
        if self.webui_dir:
            return self.webui_dir

        # 检查 data/dist
        from core.miya_config import get_data_dir

        dist_dir = get_data_dir() / "dist"
        if dist_dir.exists():
            return str(dist_dir)

        return None

    def _setup_routes(self):
        """设置路由"""
        if not self.app:
            return

        @self.app.route("/")
        async def index():
            """主页 - 跳转到 /dashboard"""
            return await self._render_main()

        @self.app.route("/dashboard")
        async def dashboard():
            """主仪表板"""
            return await self._render_dashboard()

        @self.app.route("/api/status")
        async def api_status():
            """状态 API"""
            status = self.core_lifecycle.get_status()
            return jsonify({"status": "ok", "data": status})

        @self.app.route("/api/config")
        async def api_config():
            """配置 API"""
            return jsonify(self.config)

        @self.app.route("/api/config", methods=["POST"])
        async def api_config_save():
            """保存配置"""
            data = await request.get_json()
            self.config.update(data)
            return jsonify({"status": "ok"})

        @self.app.route("/api/platforms")
        async def api_platforms():
            """平台 API"""
            platforms = self.config.get("platform", [])
            return jsonify({"status": "ok", "data": platforms})

        @self.app.route("/api/providers")
        async def api_providers():
            """AI 提供商 API"""
            providers = self.config.get("provider", [])
            return jsonify({"status": "ok", "data": providers})

        @self.app.route("/api/chat", methods=["POST"])
        async def api_chat():
            """聊天 API"""
            data = await request.get_json()
            data.get("message", "")
            # TODO: 连接 Miya 核心处理消息
            return jsonify({"status": "ok", "response": "处理中..."})

    async def _render_main(self):
        """渲染主页"""
        status = self.core_lifecycle.get_status()

        platforms = status.get("platforms", False)
        providers = status.get("providers", False)
        knowledge = status.get("knowledge", False)
        status.get("plugins", False)
        miya_core = status.get("miya_core", False)

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>弥娅系统 v6.0</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f1a; color: #e0e0e0; min-height: 100vh; }}
        
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px 40px; display: flex; justify-content: space-between; align-items: center; }}
        .logo {{ font-size: 28px; font-weight: bold; color: white; }}
        .version {{ color: rgba(255,255,255,0.8); font-size: 14px; }}
        
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
        
        .card {{ background: #1a1a2e; border-radius: 16px; padding: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }}
        .card-title {{ font-size: 18px; font-weight: 600; margin-bottom: 16px; color: #e94560; }}
        
        .status-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }}
        .status-item {{ background: #16213e; padding: 16px; border-radius: 12px; text-align: center; }}
        .status-item.active {{ border: 2px solid #4caf50; }}
        .status-item.inactive {{ border: 2px solid #f44336; }}
        .status-label {{ font-size: 12px; color: #888; margin-bottom: 4px; }}
        .status-value {{ font-size: 24px; font-weight: bold; }}
        
        .platform-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px; }}
        .platform-item {{ background: #16213e; padding: 12px; border-radius: 8px; text-align: center; font-size: 13px; }}
        
        .nav {{ display: flex; gap: 10px; margin-bottom: 20px; }}
        .nav-btn {{ background: #16213e; border: none; color: #e0e0e0; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 14px; }}
        .nav-btn:hover {{ background: #e94560; }}
        
        .terminal {{ background: #0a0a15; border-radius: 12px; padding: 20px; font-family: 'Consolas', monospace; min-height: 300px; }}
        .terminal-input {{ display: flex; gap: 10px; }}
        .terminal-input input {{ flex: 1; background: #1a1a2e; border: none; color: #4caf50; padding: 12px 16px; border-radius: 8px; font-family: inherit; }}
        .terminal-input button {{ background: #4caf50; border: none; color: white; padding: 12px 24px; border-radius: 8px; cursor: pointer; }}
        
        .provider-list {{ background: #16213e; border-radius: 8px; padding: 12px; font-size: 13px; }}
        .provider-item {{ padding: 8px 12px; border-bottom: 1px solid #2a2a4e; }}
        
        .footer {{ text-align: center; padding: 40px; color: #666; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🤖 弥娅系统</div>
        <div class="version">v{self.VERSION}</div>
    </div>
    
    <div class="container">
        <div class="nav">
            <button class="nav-btn" onclick="location.href='/dashboard'">仪表板</button>
            <button class="nav-btn" onclick="alert('开发中')">配置</button>
            <button class="nav-btn" onclick="alert('开发中')">平台</button>
            <button class="nav-btn" onclick="alert('开发中')">AI 商</button>
            <button class="nav-btn" onclick="alert('开发中')">知识库</button>
        </div>
        
        <div class="grid">
            <div class="card">
                <div class="card-title">系统状态</div>
                <div class="status-grid">
                    <div class="status-item {"active" if miya_core else "inactive"}">
                        <div class="status-label">Miya 核心</div>
                        <div class="status-value">{"✓" if miya_core else "✗"}</div>
                    </div>
                    <div class="status-item {"active" if platforms else "inactive"}">
                        <div class="status-label">平台适配</div>
                        <div class="status-value">{"✓" if platforms else "✗"}</div>
                    </div>
                    <div class="status-item {"active" if providers else "inactive"}">
                        <div class="status-label">AI 提供商</div>
                        <div class="status-value">{"✓" if providers else "✗"}</div>
                    </div>
                    <div class="status-item {"active" if knowledge else "inactive"}">
                        <div class="status-label">知识库</div>
                        <div class="status-value">{"✓" if knowledge else "✗"}</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-title">已配置平台</div>
                <div class="platform-grid">
                    <div class="platform-item">终端</div>
                    <div class="platform-item">Telegram</div>
                    <div class="platform-item">Discord</div>
                    <div class="platform-item">Slack</div>
                    <div class="platform-item">KOOK</div>
                    <div class="platform-item">钉钉</div>
                    <div class="platform-item">飞书</div>
                    <div class="platform-item">企业微信</div>
                    <div class="platform-item">+ 更多</div>
                </div>
            </div>
        </div>
        
        <div class="card" style="margin-top: 20px;">
            <div class="card-title">终端对话</div>
            <div class="terminal">
                <div id="chat-log" style="margin-bottom: 16px; color: #888;">
                    <div>弥娅: 你好！我是弥娅 v6.0，有什么想和我聊的呢？</div>
                </div>
                <div class="terminal-input">
                    <input type="text" id="chat-input" placeholder="输入消息..." onkeypress="if(event.key==='Enter')sendMessage()">
                    <button onclick="sendMessage()">发��</button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="footer">
        基于 AstrBot 架构设计 |
        <a href="https://github.com/AstrBotDevs/AstrBot" style="color: #e94560;">AstrBot</a>
    </div>
    
    <script>
        async function sendMessage() {{
            const input = document.getElementById('chat-input');
            const message = input.value.trim();
            if (!message) return;
            
            const log = document.getElementById('chat-log');
            log.innerHTML += '<div style="color: #4caf50;">你: ' + message + '</div>';
            input.value = '';
            
            try {{
                const res = await fetch('/api/chat', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{message}})
                }});
                const data = await res.json();
                log.innerHTML += '<div>弥娅: ' + data.response + '</div>';
            }} catch(e) {{
                log.innerHTML += '<div style="color: #f44336;">错误: ' + e.message + '</div>';
            }}
            
            log.scrollTop = log.scrollHeight;
        }}
    </script>
</body>
</html>"""

    async def _render_dashboard(self):
        """渲染仪表板"""
        return await self._render_main()

    async def _start_server(self):
        """启动服务器"""
        try:
            from hypercorn.asyncio import serve
            from hypercorn.config import Config

            config = Config()
            config.bind = [f"{self.host}:{self.port}"]
            if self.webui_dir:
                config.static_folder = self.webui_dir

            logger.info("=" * 50)
            logger.info(f"Dashboard 启动: http://{self.host}:{self.port}")
            logger.info(f"访问地址: http://localhost:{self.port}")
            logger.info("=" * 50)

            return serve(self.app, config)

        except ImportError:
            logger.warning("Hypercorn 未安装")
            logger.info("请运行: pip install hypercorn")
            return None


__all__ = ["MiyaDashboard"]

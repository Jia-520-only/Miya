#!/usr/bin/env python3
"""
弥娅PC端主程序
基于Electron + FastAPI的桌面应用

整合 NagaAgent / VCPToolBox / VCPChat 功能
"""

import asyncio
import sys
import os
import json
import logging
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from core.identity import get_identity
from core.personality import get_personality
from hub.memory_engine import MemoryEngine
from hub.emotion import EmotionManager
from webnet.pc_ui import create_pc_ui_net
from mlink.mlink_core import MLinkCore

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MiyaPCApp:
    """弥娅PC端应用主类"""
    
    def __init__(self):
        self.app = FastAPI(title="弥娅PC端", version="1.0.0")
        self.mlink: Optional[MLinkCore] = None
        self.memory_engine: Optional[MemoryEngine] = None
        self.emotion_manager: Optional[EmotionManager] = None
        self.pc_ui: Optional[PCUINet] = None
        self.active_websockets: List[WebSocket] = []
        
        # 配置CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # 注册路由
        self._register_routes()
    
    def _register_routes(self):
        """注册所有路由"""
        
        @self.app.get("/")
        async def index():
            """返回前端入口"""
            frontend_path = PROJECT_ROOT / "pc_ui" / "frontend" / "index.html"
            if frontend_path.exists():
                return FileResponse(str(frontend_path))
            return {"message": "弥娅PC端 API服务"}
        
        @self.app.get("/api/health")
        async def health_check():
            """健康检查"""
            return {
                "status": "healthy",
                "identity": get_identity().to_dict(),
                "personality": get_personality().to_dict()
            }
        
        @self.app.get("/api/state")
        async def get_state():
            """获取应用状态"""
            if self.pc_ui:
                return {
                    "sessions": self.pc_ui.sessions,
                    "agents": self.pc_ui.agents,
                    "plugins": self.pc_ui.plugins,
                    "ui_state": self.pc_ui.ui_state
                }
            return {}
        
        @self.app.post("/api/chat")
        async def chat(request: dict):
            """对话接口"""
            from mlink.message import Message, MessageType
            
            message = Message(
                type=MessageType.CONTROL,
                source="api",
                target="pc_ui",
                content={
                    "action": "send_message",
                    **request
                }
            )
            
            if self.pc_ui:
                response = await self.pc_ui.handle_message(message)
                if response:
                    return response.content
                return {"error": "无响应"}
            return {"error": "PC UI未初始化"}
        
        @self.app.post("/api/agent/switch")
        async def switch_agent(request: dict):
            """切换Agent"""
            from mlink.message import Message, MessageType
            
            message = Message(
                type=MessageType.CONTROL,
                source="api",
                target="pc_ui",
                content={
                    "action": "switch_agent",
                    **request
                }
            )
            
            if self.pc_ui:
                response = await self.pc_ui.handle_message(message)
                if response:
                    return response.content
                return {"error": "无响应"}
            return {"error": "PC UI未初始化"}
        
        @self.app.post("/api/group/create")
        async def create_group(request: dict):
            """创建群聊"""
            from mlink.message import Message, MessageType
            
            message = Message(
                type=MessageType.CONTROL,
                source="api",
                target="pc_ui",
                content={
                    "action": "create_group",
                    **request
                }
            )
            
            if self.pc_ui:
                response = await self.pc_ui.handle_message(message)
                if response:
                    return response.content
                return {"error": "无响应"}
            return {"error": "PC UI未初始化"}
        
        @self.app.post("/api/note/create")
        async def create_note(request: dict):
            """创建笔记"""
            from mlink.message import Message, MessageType
            
            message = Message(
                type=MessageType.CONTROL,
                source="api",
                target="pc_ui",
                content={
                    "action": "create_note",
                    **request
                }
            )
            
            if self.pc_ui:
                response = await self.pc_ui.handle_message(message)
                if response:
                    return response.content
                return {"error": "无响应"}
            return {"error": "PC UI未初始化"}
        
        @self.app.get("/api/note/search")
        async def search_notes(query: str):
            """搜索笔记"""
            from mlink.message import Message, MessageType
            
            message = Message(
                type=MessageType.CONTROL,
                source="api",
                target="pc_ui",
                content={
                    "action": "search_notes",
                    "query": query
                }
            )
            
            if self.pc_ui:
                response = await self.pc_ui.handle_message(message)
                if response:
                    return response.content
                return {"error": "无响应"}
            return {"error": "PC UI未初始化"}
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket连接 - 用于实时通信"""
            await websocket.accept()
            self.active_websockets.append(websocket)
            
            try:
                # 发送欢迎消息
                await websocket.send_json({
                    "type": "connected",
                    "message": "弥娅已连接",
                    "identity": get_identity().to_dict()
                })
                
                # 监听消息
                while True:
                    data = await websocket.receive_json()
                    
                    # 转发到PC UI处理
                    from mlink.message import Message, MessageType
                    
                    message = Message(
                        type=MessageType.CONTROL,
                        source="websocket",
                        target="pc_ui",
                        content=data
                    )
                    
                    if self.pc_ui:
                        response = await self.pc_ui.handle_message(message)
                        if response:
                            await websocket.send_json(response.content)
                            
            except WebSocketDisconnect:
                logger.info("WebSocket断开连接")
            except Exception as e:
                logger.error(f"WebSocket错误: {e}")
            finally:
                if websocket in self.active_websockets:
                    self.active_websockets.remove(websocket)
    
    async def broadcast(self, message: dict):
        """广播消息到所有WebSocket连接"""
        disconnected = []
        for ws in self.active_websockets:
            try:
                await ws.send_json(message)
            except:
                disconnected.append(ws)
        
        for ws in disconnected:
            self.active_websockets.remove(ws)
    
    async def initialize(self):
        """初始化所有模块"""
        try:
            logger.info("正在初始化弥娅PC端...")
            
            # 1. 初始化M-Link
            self.mlink = MLinkCore()
            await self.mlink.initialize()
            logger.info("M-Link初始化完成")
            
            # 2. 初始化记忆引擎
            self.memory_engine = MemoryEngine()
            await self.memory_engine.initialize()
            logger.info("记忆引擎初始化完成")
            
            # 3. 初始化情绪管理器
            self.emotion_manager = EmotionManager()
            await self.emotion_manager.initialize()
            logger.info("情绪管理器初始化完成")
            
            # 4. 初始化PC UI子网
            self.pc_ui = await create_pc_ui_net(
                self.mlink,
                self.memory_engine,
                self.emotion_manager
            )
            logger.info("PC UI子网初始化完成")
            
            logger.info("弥娅PC端初始化完成！")
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            raise


async def main():
    """主函数"""
    app = MiyaPCApp()
    await app.initialize()
    
    # 启动服务器
    config = uvicorn.Config(
        app.app,
        host="127.0.0.1",
        port=8888,
        log_level="info"
    )
    
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())

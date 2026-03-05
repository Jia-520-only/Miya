"""
弥娅PC端交互UI子网
整合 NagaAgent / VCPToolBox / VCPChat 所有能力

核心能力：
- 桌面交互窗口 (Electron)
- 对话与记忆系统
- Agent管理与工具调用
- 插件系统与技能工坊
- 群聊与多Agent协作
- 笔记与知识管理
- 媒体播放与画布
- 文件管理与操作系统控制
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from pathlib import Path
import json

from ..mlink.message import Message, MessageType, FlowType
from ..mlink.mlink_core import MLinkCore
from core.identity import get_identity
from core.personality import get_personality
from hub.memory_engine import MemoryEngine
from hub.emotion import EmotionManager
from core.constants import Encoding

logger = logging.getLogger(__name__)


class PCUINet:
    """
    PC端交互UI子网 - 弥娅的桌面界面
    
    融合能力：
    1. NagaAgent - 流式工具调用、Live2D虚拟形象、语音交互、Agent系统
    2. VCPToolBox - 插件系统、知识库管理、向量搜索、任务调度
    3. VCPChat - 群聊协作、笔记系统、画布、媒体播放器、文件管理
    """
    
    def __init__(self, mlink: MLinkCore, memory_engine: MemoryEngine, 
                 emotion_manager: EmotionManager):
        self.mlink = mlink
        self.memory_engine = memory_engine
        self.emotion_manager = emotion_manager
        self.identity = get_identity()
        
        # UI状态管理
        self.ui_state = {
            "window_visible": False,
            "current_session": None,
            "active_agent": "miya_default",
            "group_chat_active": False,
            "canvas_active": False,
            "music_playing": False,
            "notes_active": False
        }
        
        # 会话管理（内存缓存，持久化通过 MemoryNet）
        self.sessions: Dict[str, Dict] = {}  # session_id -> session_data
        self.group_sessions: Dict[str, Dict] = {}  # group_id -> group_data
        
        # Agent管理 (吸收NagaAgent)
        self.agents: Dict[str, Dict] = {
            "miya_default": {
                "name": "弥娅默认",
                "description": "弥娅主人格",
                "avatar": "miya_default.png",
                "system_prompt": "你是弥娅，一个温暖、智慧、富有同理心的AI伴侣。",
                "skills": ["对话", "记忆", "情绪感知", "跨子网推理"],
                "enabled": True
            }
        }
        
        # 插件系统 (吸收VCPToolBox)
        self.plugins: Dict[str, Dict] = {}
        self.plugin_manifests: Dict[str, Dict] = {}
        self.plugin_order: List[str] = []
        
        # 笔记系统 (吸收VCPChat)
        self.notes: Dict[str, Dict] = {}
        self.note_categories: List[str] = ["工作", "学习", "生活", "创意", "技术"]
        
        # 媒体管理
        self.music_playlist: List[Dict] = []
        self.current_track: Optional[Dict] = None
        
        # 画布系统
        self.canvas_states: Dict[str, Dict] = {}
        
        # 任务调度 (吸收VCPToolBox)
        self.scheduled_tasks: Dict[str, Dict] = {}
        
        logger.info("弥娅PC端交互UI子网初始化完成")
    
    async def initialize(self):
        """初始化PC UI子网所有模块"""
        try:
            # 注册M-Link消息处理器
            await self.mlink.register_handler(
                "pc_ui", 
                self.handle_message,
                [FlowType.CONTROL, FlowType.PERCEPTION]
            )
            
            # 加载插件
            await self.load_plugins()
            
            # 加载笔记
            await self.load_notes()
            
            # 加载Agent配置
            await self.load_agents()
            
            logger.info("PC UI子网初始化成功")
        except Exception as e:
            logger.error(f"PC UI子网初始化失败: {e}")
            raise
    
    async def handle_message(self, message: Message) -> Optional[Message]:
        """处理来自M-Link的消息"""
        try:
            action = message.content.get("action")
            
            if action == "show_window":
                return await self.show_window()
            
            elif action == "send_message":
                return await self.handle_user_message(message)
            
            elif action == "switch_agent":
                return await self.switch_agent(message.content.get("agent_id"))
            
            elif action == "create_group":
                return await self.create_group(message.content)
            
            elif action == "send_group_message":
                return await self.handle_group_message(message)
            
            elif action == "create_note":
                return await self.create_note(message.content)
            
            elif action == "search_notes":
                return await self.search_notes(message.content.get("query", ""))
            
            elif action == "music_play":
                return await self.music_control("play", message.content)
            
            elif action == "music_pause":
                return await self.music_control("pause")
            
            elif action == "canvas_update":
                return await self.update_canvas(message.content)
            
            elif action == "execute_plugin":
                return await self.execute_plugin(message.content)
            
            elif action == "schedule_task":
                return await self.schedule_task(message.content)
            
            elif action == "get_ui_state":
                return Message(
                    type=MessageType.RESPONSE,
                    source="pc_ui",
                    target=message.source,
                    content={
                        "action": "ui_state",
                        "state": self.ui_state
                    }
                )
            
            else:
                logger.warning(f"未知的PC UI操作: {action}")
                return None
                
        except Exception as e:
            logger.error(f"处理PC UI消息失败: {e}")
            return Message(
                type=MessageType.ERROR,
                source="pc_ui",
                target=message.source,
                content={"error": str(e)}
            )
    
    async def show_window(self) -> Message:
        """显示主窗口"""
        self.ui_state["window_visible"] = True
        
        # 通过M-Link发送感知流
        await self.mlink.send_message(Message(
            type=MessageType.SYNC,
            source="pc_ui",
            target="perceive",
            content={
                "event": "window_shown",
                "timestamp": datetime.now().isoformat()
            }
        ))
        
        return Message(
            type=MessageType.RESPONSE,
            source="pc_ui",
            content={
                "action": "show_window",
                "success": True,
                "ui_state": self.ui_state
            }
        )
    
    async def handle_user_message(self, message: Message) -> Message:
        """
        处理用户消息 - 核心对话能力
        
        融合NagaAgent的对话核心 + VCPChat的消息处理
        """
        user_input = message.content.get("message", "")
        session_id = message.content.get("session_id", "default")
        agent_id = message.content.get("agent_id", self.ui_state["active_agent"])
        images = message.content.get("images", [])
        
        try:
            # 1. 获取或创建会话
            session = await self.get_or_create_session(session_id, agent_id)
            
            # 2. 情绪感知与染色
            current_emotion = self.emotion_manager.get_current_emotion()
            emotion_coloring = self.emotion_manager.compute_coloring(user_input, current_emotion)
            
            # 3. 记忆检索 (吸收NagaAgent的GRAG记忆)
            relevant_memory = await self.memory_engine.retrieve(
                query=user_input,
                limit=5,
                session_id=session_id
            )
            
            # 4. 构建上下文
            context = await self.build_conversation_context(session, relevant_memory, emotion_coloring)
            
            # 5. 发送到决策引擎处理
            decision_message = Message(
                type=MessageType.CONTROL,
                source="pc_ui",
                target="hub",
                content={
                    "action": "process_conversation",
                    "context": context,
                    "user_input": user_input,
                    "session_id": session_id,
                    "agent_id": agent_id,
                    "images": images,
                    "emotion": current_emotion.to_dict()
                }
            )
            
            response = await self.mlink.send_and_wait(decision_message, timeout=NetworkTimeout.API_REQUEST_TIMEOUT)
            
            # 6. 更新会话历史（保存到全局记忆）
            if response and response.type == MessageType.RESPONSE:
                ai_response = response.content.get("response", "")

                session["history"].append({
                    "role": "user",
                    "content": user_input,
                    "images": images,
                    "timestamp": datetime.now().isoformat()
                })

                session["history"].append({
                    "role": "assistant",
                    "content": ai_response,
                    "timestamp": datetime.now().isoformat(),
                    "agent_id": agent_id
                })

                # 通过 M-Link memory_flow 保存到全局记忆系统
                try:
                    # 保存用户消息
                    await self.mlink.send_message(Message(
                        type=MessageType.CONTROL,
                        source="pc_ui",
                        target="memory",
                        content={
                            "action": "add_conversation",
                            "session_id": session_id,
                            "role": "user",
                            "content": user_input,
                            "images": images,
                            "agent_id": agent_id,
                            "metadata": {"source": "pc_ui"}
                        },
                        flow_type=FlowType.MEMORY
                    ))

                    # 保存 AI 消息
                    await self.mlink.send_message(Message(
                        type=MessageType.CONTROL,
                        source="pc_ui",
                        target="memory",
                        content={
                            "action": "add_conversation",
                            "session_id": session_id,
                            "role": "assistant",
                            "content": ai_response,
                            "agent_id": agent_id,
                            "metadata": {"source": "pc_ui"}
                        },
                        flow_type=FlowType.MEMORY
                    ))

                    logger.debug(f"对话已保存到全局记忆: {session_id}")

                except Exception as e:
                    logger.error(f"保存到全局记忆失败: {e}")
                
                # 7. 存储记忆 (情绪耦合)
                await self.memory_engine.store(
                    content=f"用户: {user_input}\n弥娅: {ai_response}",
                    session_id=session_id,
                    emotion=current_emotion.to_dict(),
                    tags=["conversation", "pc_ui"]
                )
                
                return Message(
                    type=MessageType.RESPONSE,
                    source="pc_ui",
                    target=message.source,
                    content={
                        "action": "response",
                        "response": ai_response,
                        "session_id": session_id,
                        "agent_id": agent_id
                    }
                )
            
            return None
            
        except Exception as e:
            logger.error(f"处理用户消息失败: {e}")
            return Message(
                type=MessageType.ERROR,
                source="pc_ui",
                target=message.source,
                content={"error": str(e)}
            )
    
    async def get_or_create_session(self, session_id: str, agent_id: str) -> Dict:
        """获取或创建会话"""
        if session_id not in self.sessions:
            agent = self.agents.get(agent_id, self.agents["miya_default"])
            self.sessions[session_id] = {
                "id": session_id,
                "agent_id": agent_id,
                "history": [],
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "context": {}
            }

            # 从全局记忆系统加载历史（通过 M-Link memory_flow）
            try:
                request_message = Message(
                    type=MessageType.CONTROL,
                    source="pc_ui",
                    target="memory",
                    content={
                        "action": "get_conversation",
                        "session_id": session_id,
                        "limit": 100
                    },
                    flow_type=FlowType.MEMORY
                )

                response = await self.mlink.send_and_wait(request_message, timeout=10)

                if response and response.type == MessageType.RESPONSE:
                    messages = response.content.get("messages", [])
                    self.sessions[session_id]["history"] = messages
                    logger.info(f"从全局记忆加载会话 {session_id}: {len(messages)} 条消息")
                else:
                    logger.warning(f"从全局记忆加载会话失败: {session_id}")

            except Exception as e:
                logger.error(f"从全局记忆加载会话异常: {e}")
                # 继续使用空会话

        else:
            self.sessions[session_id]["last_active"] = datetime.now().isoformat()

        return self.sessions[session_id]
    
    async def build_conversation_context(self, session: Dict, 
                                          memory: List[Dict],
                                          emotion_coloring: float) -> Dict:
        """构建对话上下文"""
        # 获取人格基底
        personality = get_personality()
        agent = self.agents.get(session["agent_id"], self.agents["miya_default"])
        
        context = {
            "personality": personality.to_dict(),
            "agent": agent,
            "emotion_coloring": emotion_coloring,
            "history": session["history"][-10:],  # 最近10轮对话
            "memory": memory,
            "session_id": session["id"],
            "timestamp": datetime.now().isoformat()
        }
        
        return context
    
    async def switch_agent(self, agent_id: str) -> Message:
        """切换活跃Agent"""
        if agent_id in self.agents:
            self.ui_state["active_agent"] = agent_id
            
            # 更新人格 (如果Agent有独立人格)
            agent = self.agents[agent_id]
            
            await self.mlink.send_message(Message(
                type=MessageType.SYNC,
                source="pc_ui",
                target="core",
                content={
                    "event": "agent_switched",
                    "agent_id": agent_id,
                    "agent": agent
                }
            ))
            
            return Message(
                type=MessageType.RESPONSE,
                source="pc_ui",
                content={
                    "action": "switch_agent",
                    "success": True,
                    "agent_id": agent_id,
                    "agent": agent
                }
            )
        else:
            return Message(
                type=MessageType.ERROR,
                source="pc_ui",
                content={"error": f"Agent不存在: {agent_id}"}
            )
    
    # ========== 群聊功能 (吸收VCPChat) ==========
    
    async def create_group(self, content: Dict) -> Message:
        """创建群聊"""
        group_id = content.get("group_id", f"group_{datetime.now().timestamp()}")
        group_name = content.get("name", "新群聊")
        agent_ids = content.get("agents", ["miya_default"])
        
        if group_id in self.group_sessions:
            return Message(
                type=MessageType.ERROR,
                source="pc_ui",
                content={"error": "群组已存在"}
            )
        
        self.group_sessions[group_id] = {
            "id": group_id,
            "name": group_name,
            "agents": agent_ids,
            "history": [],
            "topics": {},
            "created_at": datetime.now().isoformat()
        }
        
        # 创建默认话题
        self.group_sessions[group_id]["topics"]["default"] = {
            "id": "default",
            "name": "主要话题",
            "history": []
        }
        
        self.ui_state["group_chat_active"] = True
        
        return Message(
            type=MessageType.RESPONSE,
            source="pc_ui",
            content={
                "action": "create_group",
                "success": True,
                "group_id": group_id,
                "group": self.group_sessions[group_id]
            }
        )
    
    async def handle_group_message(self, message: Message) -> Message:
        """处理群聊消息"""
        group_id = message.content.get("group_id")
        topic_id = message.content.get("topic_id", "default")
        user_input = message.content.get("message", "")
        sender = message.content.get("sender", "user")
        
        if group_id not in self.group_sessions:
            return Message(
                type=MessageType.ERROR,
                source="pc_ui",
                content={"error": "群组不存在"}
            )
        
        group = self.group_sessions[group_id]
        if topic_id not in group["topics"]:
            return Message(
                type=MessageType.ERROR,
                source="pc_ui",
                content={"error": "话题不存在"}
            )
        
        topic = group["topics"][topic_id"]
        
        # 添加用户消息
        topic["history"].append({
            "role": "user",
            "sender": sender,
            "content": user_input,
            "timestamp": datetime.now().isoformat()
        })
        
        # 让所有Agent轮流回复
        responses = []
        for agent_id in group["agents"]:
            if agent_id in self.agents:
                # 为每个Agent构建消息
                agent_message = Message(
                    type=MessageType.CONTROL,
                    source="pc_ui",
                    target="hub",
                    content={
                        "action": "process_conversation",
                        "context": {
                            "agent": self.agents[agent_id],
                            "history": topic["history"][-5:],
                            "group_chat": True,
                            "group_id": group_id,
                            "topic_id": topic_id
                        },
                        "user_input": user_input,
                        "session_id": f"{group_id}_{topic_id}_{agent_id}",
                        "agent_id": agent_id
                    }
                )
                
                response = await self.mlink.send_and_wait(agent_message, timeout=NetworkTimeout.API_REQUEST_TIMEOUT)
                
                if response and response.type == MessageType.RESPONSE:
                    ai_response = response.content.get("response", "")
                    responses.append({
                        "agent_id": agent_id,
                        "response": ai_response
                    })
                    
                    topic["history"].append({
                        "role": "assistant",
                        "agent_id": agent_id,
                        "content": ai_response,
                        "timestamp": datetime.now().isoformat()
                    })
        
        return Message(
            type=MessageType.RESPONSE,
            source="pc_ui",
            content={
                "action": "group_response",
                "responses": responses,
                "group_id": group_id,
                "topic_id": topic_id
            }
        )
    
    # ========== 笔记系统 (吸收VCPChat TagMemo) ==========
    
    async def create_note(self, content: Dict) -> Message:
        """创建笔记"""
        note_id = content.get("note_id", f"note_{datetime.now().timestamp()}")
        title = content.get("title", "新笔记")
        body = content.get("body", "")
        tags = content.get("tags", [])
        category = content.get("category", "未分类")
        
        self.notes[note_id] = {
            "id": note_id,
            "title": title,
            "body": body,
            "tags": tags,
            "category": category,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # 存储到记忆系统
        await self.memory_engine.store(
            content=f"笔记: {title}\n{body}",
            session_id="notes",
            tags=tags + ["note", category],
            metadata={
                "note_id": note_id,
                "category": category
            }
        )
        
        return Message(
            type=MessageType.RESPONSE,
            source="pc_ui",
            content={
                "action": "create_note",
                "success": True,
                "note_id": note_id,
                "note": self.notes[note_id]
            }
        )
    
    async def search_notes(self, query: str) -> Message:
        """搜索笔记 (使用记忆引擎的向量搜索)"""
        # 从记忆系统搜索
        memory_results = await self.memory_engine.retrieve(
            query=query,
            limit=10,
            session_id="notes"
        )
        
        # 转换为笔记格式
        notes = []
        for mem in memory_results:
            if "note_id" in mem.metadata:
                note_id = mem.metadata["note_id"]
                if note_id in self.notes:
                    notes.append(self.notes[note_id])
        
        return Message(
            type=MessageType.RESPONSE,
            source="pc_ui",
            content={
                "action": "search_notes",
                "query": query,
                "results": notes
            }
        )
    
    # ========== 媒体控制 ==========
    
    async def music_control(self, action: str, content: Dict = None) -> Message:
        """音乐播放控制"""
        if action == "play":
            track = content.get("track") if content else None
            if track:
                self.current_track = track
                self.music_playlist.append(track)
            elif self.music_playlist and not self.current_track:
                self.current_track = self.music_playlist[0]
            
            self.ui_state["music_playing"] = True
            
        elif action == "pause":
            self.ui_state["music_playing"] = False
        
        return Message(
            type=MessageType.RESPONSE,
            source="pc_ui",
            content={
                "action": "music_control",
                "playing": self.ui_state["music_playing"],
                "current_track": self.current_track
            }
        )
    
    # ========== 画布系统 ==========
    
    async def update_canvas(self, content: Dict) -> Message:
        """更新画布状态"""
        canvas_id = content.get("canvas_id", "default")
        canvas_data = content.get("data")
        
        self.canvas_states[canvas_id] = {
            "id": canvas_id,
            "data": canvas_data,
            "updated_at": datetime.now().isoformat()
        }
        
        return Message(
            type=MessageType.RESPONSE,
            source="pc_ui",
            content={
                "action": "canvas_update",
                "canvas_id": canvas_id,
                "success": True
            }
        )
    
    # ========== 插件系统 (吸收VCPToolBox) ==========
    
    async def load_plugins(self):
        """加载所有插件"""
        plugin_dir = Path("plugins")
        if not plugin_dir.exists():
            plugin_dir.mkdir(parents=True)
            return
        
        for manifest_path in plugin_dir.glob("*/plugin-manifest.json"):
            try:
                with open(manifest_path, 'r', encoding=Encoding.UTF8) as f:
                    manifest = json.load(f)
                
                plugin_id = manifest.get("id", manifest_path.parent.name)
                self.plugins[plugin_id] = {
                    "id": plugin_id,
                    "manifest": manifest,
                    "base_path": str(manifest_path.parent),
                    "enabled": True
                }
                
                logger.info(f"加载插件: {plugin_id}")
                
            except Exception as e:
                logger.error(f"加载插件失败 {manifest_path}: {e}")
    
    async def execute_plugin(self, content: Dict) -> Message:
        """执行插件命令"""
        plugin_id = content.get("plugin_id")
        command = content.get("command")
        params = content.get("params", {})
        
        if plugin_id not in self.plugins:
            return Message(
                type=MessageType.ERROR,
                source="pc_ui",
                content={"error": f"插件不存在: {plugin_id}"}
            )
        
        plugin = self.plugins[plugin_id]
        
        # 这里实现插件执行逻辑
        # 实际实现需要根据插件类型（静态/动态）执行不同的逻辑
        
        return Message(
            type=MessageType.RESPONSE,
            source="pc_ui",
            content={
                "action": "plugin_executed",
                "plugin_id": plugin_id,
                "command": command,
                "result": "执行成功"  # 占位
            }
        )
    
    # ========== 任务调度 (吸收VCPToolBox) ==========
    
    async def schedule_task(self, content: Dict) -> Message:
        """调度定时任务"""
        task_id = content.get("task_id", f"task_{datetime.now().timestamp()}")
        schedule = content.get("schedule", {})
        action = content.get("action")
        
        self.scheduled_tasks[task_id] = {
            "id": task_id,
            "schedule": schedule,
            "action": action,
            "created_at": datetime.now().isoformat()
        }
        
        return Message(
            type=MessageType.RESPONSE,
            source="pc_ui",
            content={
                "action": "task_scheduled",
                "task_id": task_id,
                "success": True
            }
        )
    
    # ========== 配置加载 ==========
    
    async def load_notes(self):
        """加载笔记数据"""
        notes_file = Path("storage/notes.json")
        if notes_file.exists():
            try:
                with open(notes_file, 'r', encoding=Encoding.UTF8) as f:
                    self.notes = json.load(f)
                logger.info(f"加载笔记: {len(self.notes)} 条")
            except Exception as e:
                logger.error(f"加载笔记失败: {e}")
    
    async def load_agents(self):
        """加载Agent配置"""
        agents_dir = Path("storage/agents")
        if agents_dir.exists():
            for agent_file in agents_dir.glob("*.json"):
                try:
                    with open(agent_file, 'r', encoding=Encoding.UTF8) as f:
                        agent = json.load(f)
                        agent_id = agent_file.stem
                        self.agents[agent_id] = agent
                    logger.info(f"加载Agent: {agent_id}")
                except Exception as e:
                    logger.error(f"加载Agent失败 {agent_file}: {e}")
    
    async def save_state(self):
        """保存状态"""
        # 保存笔记
        notes_file = Path("storage/notes.json")
        notes_file.parent.mkdir(parents=True, exist_ok=True)
        with open(notes_file, 'w', encoding=Encoding.UTF8) as f:
            json.dump(self.notes, f, ensure_ascii=False, indent=2)
        
        # 保存会话
        sessions_file = Path("storage/sessions.json")
        with open(sessions_file, 'w', encoding=Encoding.UTF8) as f:
            json.dump(self.sessions, f, ensure_ascii=False, indent=2)
        
        logger.info("PC UI状态保存完成")


# 便捷函数
async def create_pc_ui_net(mlink: MLinkCore, memory_engine: MemoryEngine,
                          emotion_manager: EmotionManager) -> PCUINet:
    """创建PC UI子网实例"""
    pc_ui = PCUINet(mlink, memory_engine, emotion_manager)
    await pc_ui.initialize()
    return pc_ui

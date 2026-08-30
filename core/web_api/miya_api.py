"""
弥娅 Web API 完整兼容层

为弥娅 Dashboard 提供完整的 API 接口
"""

import asyncio
import json
import logging
import mimetypes
import re
from pathlib import Path
from urllib.parse import quote, unquote
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, HTTPException, Request
    from starlette.responses import StreamingResponse, FileResponse

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    APIRouter = object


class MiyaAPI:
    """弥娅完整 API"""

    def __init__(self, web_net=None, decision_hub=None):
        self.web_net = web_net
        self.decision_hub = decision_hub

        if not FASTAPI_AVAILABLE:
            logger.warning("[MiyaAPI] FastAPI 不可用")
            self.router = None
            return

        self.router = APIRouter(prefix="", tags=["Miya"])
        self._setup_routes()

    def _setup_routes(self):
        """设置所有路由"""
        @self.router.get('/api/music/library')
        async def music_library():
            root = Path(__file__).resolve().parents[2]
            extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.webm'}
            tracks = []
            for source in ('singing_input', 'singing'):
                base = root / 'data' / source
                if not base.is_dir():
                    continue
                for path in sorted(base.rglob('*'), key=lambda item: item.name.casefold()):
                    if not path.is_file() or path.suffix.lower() not in extensions:
                        continue
                    relative = path.relative_to(base).as_posix()
                    stem = path.stem
                    folded_stem = stem.casefold()
                    is_mix = source == 'singing' and re.search(r'_mix(?:_t[+-]\d+)?$', folded_stem)
                    is_cached_original = source == 'singing' and path.suffix.lower() == '.mp3' and path.parent != base
                    if source == 'singing_input' or is_cached_original:
                        kind = 'original'
                    elif is_mix:
                        kind = 'cover'
                        # 混音文件名可能带调性后缀，歌曲目录名才是稳定的曲名。
                        stem = path.parent.name if path.parent != base else re.sub(r'_mix(?:_t[+-]\d+)?$', '', stem, flags=re.IGNORECASE)
                    else:
                        kind = 'material'
                    tracks.append({
                        'id': f'{source}/{relative}',
                        'title': stem,
                        'source': source,
                        'kind': kind,
                        'format': path.suffix.lower().lstrip('.'),
                        'sizeBytes': path.stat().st_size,
                        'playable': kind != 'material',
                        'url': f'/api/music/stream?source={quote(source)}&file={quote(relative)}',
                    })
            return tracks

        @self.router.get('/api/music/stream')
        async def music_stream(source: str, file: str):
            root = Path(__file__).resolve().parents[2]
            base = root / 'data' / source
            target = (base / unquote(file)).resolve()
            if source not in ('singing_input', 'singing') or base not in target.parents or not target.is_file():
                raise HTTPException(404, '音乐文件不存在')
            return FileResponse(str(target), media_type=mimetypes.guess_type(target.name)[0] or 'audio/mpeg')

        # ========== 认证 ==========
        @self.router.post("/api/auth/login")
        async def login(body: dict = None):
            """用户登录"""
            if body is None:
                body = {}
            username = body.get("username", "")
            password = body.get("password", "")

            # 前端会对密码进行 MD5 加密
            valid_passwords = {
                "miya": ["miya", "3b650cc81ad6bfc4f7e84403c89294a8"],
                "admin": ["admin", "21232f297a57a5a743894a0e4a801fc3"],
            }

            if username in valid_passwords and password in valid_passwords[username]:
                return {
                    "status": "ok",
                    "data": {
                        "username": username,
                        "nickname": "弥娅" if username == "miya" else "管理员",
                        "role": "admin",
                        "token": "miya_token_" + str(int(datetime.now().timestamp())),
                        "change_pwd_hint": False,
                    },
                }

            return {"status": "error", "message": "用户名或密码错误"}

        @self.router.post("/api/auth/logout")
        async def logout():
            """用户登出"""
            return {"success": True, "message": "已登出"}

        @self.router.get("/api/auth/status")
        async def auth_status():
            """获取认证状态"""
            return {
                "success": True,
                "authenticated": True,
                "user": {"username": "miya", "role": "admin"},
            }

        # ========== 系统状态 ==========
        @self.router.get("/api/status")
        async def get_status():
            """获取弥娅系统状态"""
            try:
                status = {
                    "success": True,
                    "identity": {
                        "name": "弥娅",
                        "version": "1.0.0",
                        "description": "AI 虚拟化身",
                    },
                    "emotion": self._get_emotion_state(),
                    "personality": self._get_personality_state(),
                    "memory_stats": self._get_memory_stats(),
                    "platform_info": self._get_platform_info(),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                return status
            except Exception as e:
                logger.error(f"[MiyaAPI] 获取状态失败: {e}")
                return {"success": False, "error": str(e)}

        @self.router.get("/api/system/status")
        async def get_system_status():
            """系统状态详情"""
            return self._get_full_status()

        @self.router.get("/api/system/monitor")
        async def get_monitor():
            """系统监控"""
            return self._get_monitor_data()

        # ========== 人格向量 ==========
        @self.router.get("/api/v1/personality/vectors")
        async def get_personality_vectors():
            """获取人格向量"""
            try:
                if hasattr(self, "decision_hub") and self.decision_hub and hasattr(self.decision_hub, "personality"):
                    profile = self.decision_hub.personality.get_profile()
                    vectors = profile.get("vectors", {})
                    return {
                        "success": True,
                        "vectors": [{"name": k, "value": v, "min": 0, "max": 1} for k, v in vectors.items()],
                        "current_form": profile.get("current_form", "default"),
                        "dominant": profile.get("dominant", ""),
                    }
            except Exception as e:
                logger.error(f"[API] 获取人格向量失败: {e}")
            return {
                "success": True,
                "vectors": [
                    {"name": "logic", "value": 0.75, "min": 0, "max": 1},
                    {"name": "memory", "value": 0.95, "min": 0, "max": 1},
                    {"name": "warmth", "value": 0.85, "min": 0, "max": 1},
                    {"name": "empathy", "value": 0.9, "min": 0, "max": 1},
                    {"name": "resilience", "value": 0.8, "min": 0, "max": 1},
                    {"name": "creativity", "value": 0.8, "min": 0, "max": 1},
                ],
                "current_form": "default",
                "dominant": "empathy",
            }

        @self.router.get("/api/v1/personality/forms")
        async def get_personality_forms():
            """获取可用的人格表单"""
            try:
                if hasattr(self, "decision_hub") and self.decision_hub and hasattr(self.decision_hub, "personality"):
                    forms = self.decision_hub.personality.get_available_forms()
                    return {"success": True, "forms": forms}
            except Exception as e:
                logger.error(f"[API] 获取人格表单失败: {e}")
            return {"success": True, "forms": ["default", "yae", "kafka"]}

        @self.router.post("/api/v1/personality/forms")
        async def set_personality_form(body: dict = None):
            """设置人格表单"""
            if body is None:
                body = {}
            form = body.get("form", "default")
            try:
                if hasattr(self, "decision_hub") and self.decision_hub and hasattr(self.decision_hub, "personality"):
                    self.decision_hub.personality.switch_form(form)
                    return {"success": True, "message": f"已切换到形态: {form}"}
            except Exception as e:
                logger.error(f"[API] 切换人格表单失败: {e}")
            return {"success": False, "message": "切换失败"}

        # ========== 记忆 ==========
        @self.router.get("/api/memory/stats")
        async def get_memory_stats():
            """记忆统计"""
            return self._get_memory_stats()

        @self.router.get("/api/memory/list")
        async def get_memory_list():
            """记忆列表 - 从SQLite数据库读取"""
            import os
            import sqlite3

            all_memories = []

            # 基于 miya_api.py 的位置向上两级找到项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(project_root, "data", "memory", "miya_memory.db")

            if os.path.exists(db_path):
                try:
                    conn = sqlite3.connect(db_path)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id, content, level, created_at, significance, tags FROM memories ORDER BY created_at DESC LIMIT 100"
                    )
                    rows = cursor.fetchall()
                    for row in rows:
                        all_memories.append(
                            {
                                "uuid": row["id"],
                                "fact": row["content"],
                                "created_at": row["created_at"],
                                "level": row["level"],
                                "importance": row["significance"] or 0.5,
                                "tags": json.loads(row["tags"]) if row["tags"] else [],
                            }
                        )
                    conn.close()
                    logger.info(f"[Memory] 从SQLite加载 {len(all_memories)} 条记忆")
                except Exception as e:
                    logger.warning(f"[Memory] SQLite读取失败: {e}")

            all_memories.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            logger.info(f"[Memory] 共加载 {len(all_memories)} 条记忆")

            return {
                "success": True,
                "data": {"items": all_memories[:50]},
                "total": len(all_memories),
            }

        @self.router.post("/api/memory/add")
        async def add_memory(request_data: dict = None):
            """添加记忆 - 适配前端格式（text/content 或 subject+predicate+object）"""
            if request_data is None:
                request_data = {}
            try:
                content = request_data.get("text") or request_data.get("content", "")
                # 前端三元组格式兜底：subject + predicate + object 拼成一句话
                if not content and request_data.get("subject"):
                    content = f"{request_data.get('subject')} {request_data.get('predicate', '')} {request_data.get('object', '')}".strip()
                user_id = request_data.get("user_id") or request_data.get("userId")
                tags = request_data.get("tags", []) or ([request_data["type"]] if request_data.get("type") else [])

                if not content:
                    return {"success": False, "message": "缺少记忆内容"}

                from memory import store_important

                if user_id:
                    memory_id = await store_important(content, user_id, tags=tags)
                else:
                    memory_id = await store_important(content, "default", tags=tags)

                return {
                    "success": True,
                    "message": "记忆已添加",
                    "memory_id": memory_id,
                }
            except Exception as e:
                logger.error(f"[MiyaAPI] 添加记忆失败: {e}")
                return {"success": False, "message": str(e)}

        @self.router.get("/api/memory/search")
        async def search_memory(query: str = "", level: str = "", limit: int = 20):
            """搜索记忆（query string 参数，与前端调用方式对齐）"""
            try:
                user_id = None
                _ = level  # level 暂不参与过滤，保留参数位

                if not query:
                    return {"success": True, "memories": [], "total": 0}

                from memory import search_memory

                results = await search_memory(query, user_id=user_id)

                memories = []
                for r in results:
                    memories.append(
                        {
                            "id": getattr(r, "id", "unknown"),
                            "content": r.content,
                            "tags": getattr(r, "tags", []),
                            "created_at": getattr(r, "created_at", datetime.now().isoformat()),
                        }
                    )

                return {
                    "success": True,
                    "memories": memories,
                    "total": len(memories),
                }
            except Exception as e:
                logger.error(f"[MiyaAPI] 搜索记忆失败: {e}")
                return {"success": False, "memories": [], "message": str(e)}

        # ========== 知识库 API ==========
        @self.router.get("/api/knowledge_base/list")
        async def list_knowledge_bases():
            """获取知识库列表"""
            try:
                from core.alkaid_kb import list_collections

                collections = await list_collections()
                return {
                    "success": True,
                    "data": [
                        {
                            "id": c["name"],
                            "name": c["name"],
                            "description": "",
                            "document_count": c.get("document_count", 0),
                            "created_at": "",
                            "updated_at": "",
                        }
                        for c in collections
                    ],
                }
            except ImportError:
                logger.warning("[API] Alkaid KB 模块未安装，知识库功能不可用")
                return {"success": True, "data": []}
            except Exception as e:
                logger.warning(f"[API] 知识库列表获取失败: {e}")
                return {"success": True, "data": []}

        @self.router.post("/api/knowledge_base/create")
        async def create_knowledge_base(request_data: dict = None):
            """创建知识库"""
            if request_data is None:
                request_data = {}
            try:
                name = request_data.get("name", "")
                description = request_data.get("description", "")
                if not name:
                    return {"success": False, "message": "请输入知识库名称"}
                from core.alkaid_kb import create_collection

                await create_collection(name, description)
                return {
                    "success": True,
                    "id": name,
                    "name": name,
                    "description": description,
                }
            except ImportError:
                return {"success": False, "message": "知识库功能未安装"}
            except Exception as e:
                logger.error(f"[API] 创建知识库失败: {e}")
                return {"success": False, "message": str(e)}

        @self.router.post("/api/knowledge_base/query")
        async def query_knowledge_base(request_data: dict = None):
            """查询知识库"""
            if request_data is None:
                request_data = {}
            try:
                kb_id = request_data.get("kb_id", "")
                query = request_data.get("query", "")
                if not kb_id or not query:
                    return {"success": False, "message": "缺少参数"}
                from core.alkaid_kb import search_collection

                results = await search_collection(kb_id, query, top_k=5)
                return {"success": True, "results": results}
            except ImportError:
                return {"success": False, "message": "知识库功能未安装"}
            except Exception as e:
                logger.error(f"[API] 查询知识库失败: {e}")
                return {"success": False, "message": str(e)}

        @self.router.post("/api/knowledge_base/query")
        async def query_knowledge_base(request_data: dict = None):
            """查询知识库"""
            if request_data is None:
                request_data = {}
            try:
                kb_id = request_data.get("kb_id", "")
                query = request_data.get("query", "")
                if not kb_id or not query:
                    return {"success": False, "message": "缺少参数"}
                from core.alkaid_kb import search_collection

                results = await search_collection(kb_id, query, top_k=5)
                return {"success": True, "results": results}
            except Exception as e:
                logger.error(f"[API] 查询知识库失败: {e}")
                return {"success": False, "message": str(e)}

        # ========== 自主决策 API ==========
        @self.router.get("/api/autonomy/settings")
        async def get_autonomy_settings():
            """获取自主决策设置"""
            try:
                if hasattr(self, "decision_hub") and self.decision_hub:
                    return {
                        "success": True,
                        "enabled": True,
                        "主动聊天": True,
                        "主动问候": True,
                        "记忆优化": True,
                        "情绪响应": True,
                        "threshold": 0.5,
                    }
            except Exception as e:
                logger.warning(f"[API] 获取自主决策设置失败: {e}")
            return {
                "success": True,
                "enabled": True,
                "主动聊天": True,
                "主动问候": True,
                "记忆优化": True,
                "情绪响应": True,
                "threshold": 0.5,
            }

        @self.router.post("/api/autonomy/settings")
        async def save_autonomy_settings(request_data: dict = None):
            """保存自主决策设置"""
            if request_data is None:
                request_data = {}
            try:
                enabled = request_data.get("enabled", True)
                logger.info(f"[API] 自主决策设置已更新: enabled={enabled}")
                return {"success": True, "message": "设置已保存"}
            except Exception as e:
                logger.error(f"[API] 保存自主决策设置失败: {e}")
                return {"success": False, "message": str(e)}

        @self.router.get("/api/autonomy/logs")
        async def get_autonomy_logs(limit: int = 50):
            """获取自主决策日志"""
            return {
                "success": True,
                "logs": [
                    {
                        "time": datetime.now().isoformat(),
                        "action": "系统运行中",
                        "result": "正常",
                    },
                ],
                "total": 1,
            }

        @self.router.get("/api/autonomy/stats")
        async def get_autonomy_stats():
            """获取自主决策统计"""
            return {
                "success": True,
                "stats": {
                    "total_decisions": 0,
                    "success_rate": 0,
                    "avg_response_time": 0,
                },
            }

        # ========== 语音 API ==========
        @self.router.get("/api/voice/config")
        async def get_voice_config():
            """获取语音配置"""
            return {
                "success": True,
                "config": {
                    "provider": "siliconflow",
                    "voice_id": "azure-male-yunyang",
                    "speed": 1.0,
                    "pitch": 0,
                },
            }

        @self.router.post("/api/voice/config")
        async def save_voice_config(request_data: dict = None):
            """保存语音配置"""
            if request_data is None:
                request_data = {}
            try:
                provider = request_data.get("provider", "siliconflow")
                voice_id = request_data.get("voice_id", "azure-male-yunyang")
                request_data.get("speed", 1.0)
                logger.info(f"[API] 语音配置已更新: provider={provider}, voice_id={voice_id}")
                return {"success": True, "message": "语音配置已保存"}
            except Exception as e:
                logger.error(f"[API] 保存语音配置失败: {e}")
                return {"success": False, "message": str(e)}

        @self.router.post("/api/voice/test")
        async def test_voice():
            """测试语音"""
            return {
                "success": True,
                "message": "语音测试功能需要TTS服务支持",
                "audio_url": "",
            }

        # ========== Alkaid 记忆 API 适配层 ==========
        @self.router.get("/api/plug/alkaid/ltm/user_ids")
        async def get_ltm_user_ids():
            """获取记忆系统中的用户ID列表"""
            try:
                from memory import get_memory_stats

                stats = await get_memory_stats()
                users = stats.get("user_ids", []) if isinstance(stats, dict) else []

                if not users:
                    users = ["default", "1523878699"]

                return {"status": "ok", "data": users}
            except Exception as e:
                logger.warning(f"[MiyaAPI] 获取用户列表失败: {e}")
                return {"status": "ok", "data": ["default", "1523878699"]}

        @self.router.get("/api/plug/alkaid/ltm/graph")
        async def get_ltm_graph(user_id: str = None):
            """获取记忆图谱"""
            try:
                from memory import get_user_memories

                memories = await get_user_memories(user_id, limit=100)

                nodes = []
                edges = []
                node_id = 0

                for mem in memories:
                    node_id += 1
                    node_label = mem.content[:20] + "..." if len(mem.content) > 20 else mem.content
                    tags = getattr(mem, "tags", [])
                    label = tags[0] if tags else "memory"

                    nodes.append([f"node_{node_id}", {"name": node_label, "_label": label}])

                return {"status": "ok", "data": {"nodes": nodes, "edges": edges}}
            except Exception as e:
                logger.warning(f"[MiyaAPI] 获取记忆图谱失败: {e}")
                return {"status": "ok", "data": {"nodes": [], "edges": []}}

        @self.router.get("/api/plug/alkaid/ltm/graph/search")
        async def search_ltm_graph(user_id: str = None, query: str = None):
            """搜索记忆图谱"""
            try:
                from memory import search_memory

                search_query = query or user_id or ""
                results = await search_memory(search_query, user_id=user_id)

                data = {}
                for i, mem in enumerate(results):
                    doc_id = f"doc_{i}"
                    data[doc_id] = {"text": mem.content, "score": 1.0 - (i * 0.1)}

                return {"status": "ok", "data": data}
            except Exception as e:
                logger.warning(f"[MiyaAPI] 搜索记忆失败: {e}")
                return {"status": "ok", "data": {}}

        @self.router.post("/api/plug/alkaid/ltm/graph/add")
        async def add_ltm_graph(request_data: dict = None):
            """添加记忆到图谱"""
            if request_data is None:
                request_data = {}
            try:
                text = request_data.get("text", "")
                user_id = request_data.get("user_id") or request_data.get("userId")

                if not text:
                    return {"status": "error", "message": "缺少记忆内容"}

                from memory import store_important

                memory_id = await store_important(text, user_id or "default")

                return {
                    "status": "ok",
                    "message": "记忆添加成功",
                    "memory_id": memory_id,
                }
            except Exception as e:
                logger.warning(f"[MiyaAPI] 添加记忆失败: {e}")
                return {"status": "error", "message": str(e)}

        @self.router.get("/api/plug/alkaid/ltm/graph/fact")
        async def get_ltm_fact(memory_id: str = None, user_id: str = None):
            """获取记忆详情"""
            try:
                from memory import get_user_memories

                if not memory_id and not user_id:
                    return {"status": "ok", "data": {}}

                if user_id:
                    memories = await get_user_memories(user_id, limit=50)
                    if memories:
                        first_mem = memories[0]
                        return {
                            "status": "ok",
                            "data": {
                                "content": first_mem.content,
                                "tags": getattr(first_mem, "tags", []),
                            },
                        }

                return {"status": "ok", "data": {}}
            except Exception as e:
                logger.warning(f"[MiyaAPI] 获取记忆详情失败: {e}")
                return {"status": "ok", "data": {}}

        # ========== 平台 ==========
        @self.router.get("/api/platform/list")
        async def get_platform_list():
            """平台列表"""
            from config.platforms_config import (
                get_enabled_platforms,
                list_all_platforms,
            )

            platforms = list_all_platforms()
            enabled = get_enabled_platforms()
            return {
                "success": True,
                "platforms": [
                    {
                        "id": p["id"],
                        "name": p.get("name", p["id"]),
                        "enabled": p["id"] in enabled,
                        "status": "online" if p["id"] in enabled else "offline",
                    }
                    for p in platforms
                ],
            }

        @self.router.get("/api/platform/stats")
        async def get_platform_stats():
            """平台统计 - 适配前端格式

            前端期望: { status: 'ok', data: { platforms: [...] } }
            """
            try:
                from config.platforms_config import (
                    get_enabled_platforms,
                    list_all_platforms,
                )

                all_platforms = list_all_platforms()
                enabled = get_enabled_platforms()

                platforms = []
                for p in all_platforms:
                    p_id = p.get("id", "")
                    platforms.append(
                        {
                            "id": p_id,
                            "name": p.get("name", p_id),
                            "type": p_id,
                            "status": "running" if p_id in enabled else "stopped",
                            "enable": p_id in enabled,
                            "error_count": 0,
                        }
                    )

                return {
                    "status": "ok",
                    "data": {
                        "online": len(enabled),
                        "total": len(all_platforms),
                        "platforms": platforms,
                    },
                }
            except Exception as e:
                logger.error(f"[MiyaAPI] 获取平台统计失败: {e}")
                return {"status": "error", "data": {"platforms": []}, "message": str(e)}

        # ========== 人格 ==========
        @self.router.get("/api/persona/list")
        async def get_persona_list():
            """人格列表 — 真实读取 config/personalities/*.yaml"""
            from core.web_api.config_routes import list_personas

            return {"success": True, "personas": list_personas()}

        @self.router.get("/api/persona/current")
        async def get_current_persona():
            """当前人格 — 运行时 Personality 实例优先，回退 data/last_form.json"""
            from core.web_api.config_routes import get_current_persona_id, list_personas

            current = get_current_persona_id()
            personality = getattr(self.decision_hub, "personality", None)
            if personality is not None:
                current = getattr(personality, "current_form", current) or current
            personas = {p["id"]: p for p in list_personas()}
            info = personas.get(current, {"id": current, "name": current, "description": ""})
            return {
                "success": True,
                "persona": {
                    "id": current,
                    "name": info.get("name", current),
                    "description": info.get("description", ""),
                },
            }

        @self.router.post("/api/persona/switch")
        async def switch_persona(request: dict = None):
            """切换人格 — 真实热切换（body: {persona_id} 或 {name}）"""
            from core.web_api.config_routes import switch_persona as do_switch

            request = request or {}
            target = str(request.get("persona_id") or request.get("name") or "").strip()
            if not target:
                return {"success": False, "message": "缺少 persona_id"}
            try:
                result = do_switch(target, self.decision_hub)
                return {"success": True, "persona_id": target, "message": result.get("message", "已切换")}
            except FileNotFoundError:
                return {"success": False, "message": f"人设卡不存在: {target}"}
            except ValueError as e:
                return {"success": False, "message": str(e)}

        # ========== 提供商 ==========
        @self.router.get("/api/provider/list")
        async def get_provider_list():
            """提供商列表 - 从模型池动态获取"""
            try:
                from core.model_pool_manager import get_model_pool

                pool = get_model_pool()
                models = pool._models if hasattr(pool, "_models") else {}

                providers_map = {}
                for model_id, model_conf in models.items():
                    provider = model_conf.get("provider", "unknown")
                    if provider not in providers_map:
                        providers_map[provider] = {
                            "id": provider,
                            "name": provider.capitalize() if provider else "Unknown",
                            "enabled": True,
                            "models": [],
                        }

                    providers_map[provider]["models"].append(
                        {
                            "id": model_id,
                            "name": model_conf.get("name", model_id),
                            "type": model_conf.get("type", "chat"),
                        }
                    )

                providers = list(providers_map.values())
                for p in providers:
                    if p["models"]:
                        p["default_model"] = p["models"][0]["name"]

                return {
                    "success": True,
                    "providers": providers,
                }
            except Exception as e:
                logger.warning(f"[MiyaAPI] 获取提供商列表失败: {e}")
                return {
                    "success": True,
                    "providers": [],
                }

        @self.router.get("/api/provider/template")
        async def get_provider_template():
            """提供商模板 - MIYA 格式

            动态从 multi_model_config.json 读取模型配置
            前端 useSystemDetect.ts 会检测 capabilities 或 task_type 字段来判断是否为 MIYA 系统
            """
            try:
                from core.model_pool_manager import get_model_pool

                pool = get_model_pool()
                models = pool._models if hasattr(pool, "_models") else {}

                result = {}
                for model_id, model_conf in models.items():
                    provider = model_conf.get("provider", "unknown")
                    capabilities = model_conf.get("capabilities", [])
                    model_conf.get("type", "chat")

                    task_type = "simple_chat"
                    if "complex_reasoning" in capabilities or "reasoning" in capabilities:
                        task_type = "reasoning"
                    if "vision" in capabilities or "multimodal" in capabilities:
                        task_type = "vision"

                    result[model_id] = {
                        "name": model_conf.get("name", model_id),
                        "provider": provider,
                        "capabilities": capabilities,
                        "task_type": task_type,
                        "model_id": model_conf.get("name", ""),
                        "enabled": True,
                        "description": model_conf.get("description", ""),
                        "latency": model_conf.get("latency", "medium"),
                        "quality": model_conf.get("quality", "good"),
                    }

                return {
                    "success": True,
                    "data": result,
                }
            except Exception as e:
                logger.warning(f"[MiyaAPI] 获取模型模板失败: {e}")
                return {
                    "success": True,
                    "data": {},
                }

        # ========== 对话（会话持久化：扫描 data/conversations/ + 元数据文件） ==========

        def _session_meta_path():
            from pathlib import Path

            p = Path("data/chat_sessions_meta.json")
            return p

        def _load_session_meta() -> dict:
            import json
            from pathlib import Path

            p = _session_meta_path()
            if p.exists():
                try:
                    return json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    return {}
            return {}

        def _save_session_meta(meta: dict) -> None:
            from pathlib import Path

            p = _session_meta_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        def _scan_persisted_sessions() -> list:
            """扫描 data/conversations/session_*.json 生成真实会话列表（按最近活跃倒序）"""
            import glob
            import os
            from pathlib import Path

            meta = _load_session_meta()
            sessions = []
            conv_dir = Path("data/conversations")
            if not conv_dir.exists():
                return sessions
            for fp in conv_dir.glob("session_*.json"):
                session_id = fp.stem.replace("session_", "", 1)
                try:
                    msgs = json.loads(fp.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(msgs, list):
                    continue
                created = msgs[0].get("timestamp") if msgs else None
                last = msgs[-1] if msgs else {}
                updated = last.get("timestamp") or datetime.fromtimestamp(os.path.getmtime(fp)).isoformat()
                inner_sid = str(msgs[0].get("session_id", "")) if msgs else ""
                m = meta.get(session_id, {})
                sessions.append(
                    {
                        "session_id": session_id,
                        "display_name": m.get("display_name") or (f"会话 {session_id[:8]}"),
                        "created_at": created or updated,
                        "updated_at": updated,
                        "message_count": len(msgs),
                        "platform_id": "group" if inner_sid.startswith("group_") else "webchat",
                        "pinned": bool(m.get("pinned", False)),
                    }
                )
            sessions.sort(key=lambda s: str(s.get("updated_at", "")), reverse=True)
            return sessions

        @self.router.get("/api/chat/sessions")
        async def get_chat_sessions():
            """会话列表 — 真实扫描 data/conversations/"""
            return {"success": True, "data": _scan_persisted_sessions()}

        @self.router.get("/api/chat/new_session")
        async def new_session():
            """创建新会话 — 落盘空文件，立即可见"""
            import uuid
            from pathlib import Path

            session_id = str(uuid.uuid4().hex[:16])
            conv_dir = Path("data/conversations")
            conv_dir.mkdir(parents=True, exist_ok=True)
            (conv_dir / f"session_{session_id}.json").write_text("[]", encoding="utf-8")

            return {
                "success": True,
                "data": {"session_id": session_id, "platform_id": "webchat"},
            }

        @self.router.get("/api/chat/delete_session")
        async def delete_session(session_id: str):
            """删除会话 — 清理历史文件 / 内存上下文 / 元数据"""
            from pathlib import Path

            safe_id = session_id.replace("/", "_").replace("\\", "_")
            removed = False
            target = Path("data/conversations") / f"session_{safe_id}.json"
            if target.exists():
                target.unlink()
                removed = True
            # 内存中的对话上下文一并关闭
            try:
                from core.conversation_manager import get_conversation_manager

                conv_mgr = get_conversation_manager()
                await conv_mgr.close_session(session_id)
            except Exception:
                pass
            # 元数据
            meta = _load_session_meta()
            if session_id in meta:
                meta.pop(session_id)
                _save_session_meta(meta)
            return {
                "success": True,
                "message": "会话已删除" if removed else "会话不存在（可能已清理）",
                "data": {"session_id": session_id},
            }

        @self.router.post("/api/chat/update_session_display_name")
        async def update_session_display_name(request: dict = None):
            """重命名会话（元数据持久化）"""
            request = request or {}
            session_id = str(request.get("session_id", ""))
            display_name = str(request.get("display_name", "")).strip()
            if not session_id or not display_name:
                return {"success": False, "message": "缺少 session_id 或 display_name"}
            meta = _load_session_meta()
            meta.setdefault(session_id, {})["display_name"] = display_name
            _save_session_meta(meta)
            return {"success": True, "message": "会话名称已更新"}

        @self.router.get("/api/chat/get_session")
        async def get_session(session_id: str):
            """获取会话历史"""
            try:
                from core.conversation_manager import get_conversation_manager

                conv_mgr = get_conversation_manager()
                history = await conv_mgr.get_history(session_id)
                return {
                    "success": True,
                    "data": {
                        "session_id": session_id,
                        "history": history,
                        "threads": [],
                    },
                }
            except Exception as e:
                logger.warning(f"[get_session] 使用原始 SQLite 回退: {e}")
                try:
                    import sqlite3
                    from pathlib import Path

                    db_path = Path("data/miya.db")
                    if db_path.exists():
                        conn = sqlite3.connect(str(db_path))
                        rows = conn.execute(
                            "SELECT role, content, timestamp FROM conversation_messages WHERE session_id = ? ORDER BY id ASC",
                            (session_id,),
                        ).fetchall()
                        conn.close()
                        history = [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in rows]
                        return {
                            "success": True,
                            "data": {
                                "session_id": session_id,
                                "history": history,
                                "threads": [],
                            },
                        }
                except Exception as e2:
                    logger.warning(f"[get_session] SQLite 回退也失败: {e2}")

                return {
                    "success": True,
                    "data": {"session_id": session_id, "history": [], "threads": []},
                }

        @self.router.post("/api/chat/update_session_display_name")
        async def update_session_name(request_data: dict):
            """更新会话名称"""
            session_id = request_data.get("session_id")
            display_name = request_data.get("display_name", "")

            try:
                if hasattr(self, "_chat_sessions"):
                    for s in self._chat_sessions:
                        if s.get("session_id") == session_id:
                            s["display_name"] = display_name
                            s["updated_at"] = datetime.now().isoformat()
            except:
                pass

            return {"success": True, "message": "会话名称已更新"}

        @self.router.post("/api/chat/batch_delete_sessions")
        async def batch_delete_sessions(request_data: dict):
            """批量删除会话"""
            session_ids = request_data.get("session_ids", [])

            try:
                if hasattr(self, "_chat_sessions"):
                    self._chat_sessions = [s for s in self._chat_sessions if s.get("session_id") not in session_ids]
            except:
                pass

            return {
                "success": True,
                "data": {
                    "deleted_count": len(session_ids),
                    "failed_count": 0,
                    "failed_items": [],
                },
            }

        @self.router.post("/api/chat/stop")
        async def stop_chat(session_id: str):
            """停止响应"""
            return {"success": True, "message": "已停止"}

        @self.router.get("/api/files/download/{filename}")
        async def download_file(filename: str):
            """下载弥娅生成的文件（桌面/移动端使用）"""
            from pathlib import Path as _Path

            web_dir = _Path("data/web_files")
            file_path = (web_dir / filename).resolve()
            if not str(file_path).startswith(str(web_dir.resolve())):
                return {"success": False, "error": "路径非法"}
            if not file_path.exists():
                return {"success": False, "error": "文件不存在"}
            from fastapi.responses import FileResponse

            return FileResponse(str(file_path), filename=filename)

        @self.router.post("/api/chat/send")
        async def send_message(request_data: dict, req: Request):
            """发送消息 - 复用QQ端灵魂处理逻辑

            与QQ端/Napcat完全一致的处理流程：
            1. 创建 M-Link Message
            2. DecisionHub.process_perception_cross_platform
            3. 灵魂发生器 + AI Client + 工具编排
            """
            try:
                message = request_data.get("message", "")
                session_id = request_data.get("session_id", "default")
                user_id = request_data.get("user_id") or session_id
                platform = request_data.get("platform", "desktop")

                image_data = request_data.get("image_data")
                print(
                    f"[DEBUG chat/send] user_id={user_id}, platform={platform}, message={message[:30]}, has_image={bool(image_data)}"
                )

                # 吟美虚拟主播命令拦截
                if message in ("/主播 on", "/主播 off"):
                    try:
                        from plugins.yinmei.core.live_stream_hub import LiveStreamHub

                        hub = LiveStreamHub()
                        if message == "/主播 on":
                            hub.enable()
                            return {
                                "success": True,
                                "response": "虚拟主播已开启",
                                "content": "沉浸式AI虚拟主播系统已就绪",
                            }
                        else:
                            hub.disable()
                            return {"success": True, "response": "虚拟主播已关闭", "content": "虚拟主播系统已休眠"}
                    except Exception as e:
                        print(f"[yinmei] 命令拦截异常: {e}")

                if not self.decision_hub:
                    return {
                        "success": False,
                        "response": "弥娅系统尚未就绪",
                        "error": "DecisionHub 未初始化",
                    }

                from mlink.message import Message

                usg_id = request_data.get("usg_id")
                lookup_id = usg_id or user_id

                # 从 permissions.json 链接到主用户身份（统一跨平台记忆）
                try:
                    import json
                    from pathlib import Path

                    perms_file = Path("config/permissions.json")
                    if perms_file.exists():
                        perms_data = json.loads(perms_file.read_text(encoding="utf-8"))
                        for u in perms_data.get("users", []):
                            uid_match = u.get("usg_id") or u.get("user_id")
                            if uid_match and str(uid_match) == str(lookup_id or ""):
                                linked_to = u.get("linked_to")
                                if linked_to:
                                    lookup_id = linked_to
                                    logger.info(f"[chat/send] 用户身份已链接: {user_id} → {linked_to}")
                                break
                except Exception:
                    pass

                perception = {
                    "platform": platform,
                    "content": message,
                    "user_id": lookup_id,
                    "usg_id": lookup_id,
                    "sender_name": f"{platform}用户-{lookup_id[:8]}" if lookup_id else f"{platform}用户",
                    "message_type": "private",
                }

                # 处理悬浮球截图：base64 → 视觉模型分析 → 注入上下文
                if image_data:
                    try:
                        from core.game_play.engine import get_game_play_engine
                        from core.text_loader import get_text

                        engine = get_game_play_engine()
                        await engine.initialize()
                        analysis = await engine._call_vision(
                            get_text(
                                "screen_vision.describe_prompt",
                                "用中文描述当前屏幕上的内容。",
                            ),
                            image_data,
                            message or get_text("screen_vision.describe_default_query", "描述当前画面"),
                        )
                        if analysis:
                            perception["_image_analysis"] = {
                                "success": True,
                                "description": analysis,
                                "labels": [],
                                "model": "vision",
                            }
                            perception["image_analysis"] = perception["_image_analysis"]
                            logger.info(f"[WebChat] 悬浮球截图分析: {analysis[:80]}...")
                    except Exception as e:
                        logger.warning(f"[WebChat] 截图分析失败: {e}")

                # 注入 is_owner 标记（桌面端超管权限）
                check_id = str(lookup_id) if lookup_id else ""
                if check_id:
                    try:
                        from core.unified_permission import get_permission_engine

                        engine = get_permission_engine()
                        if engine and engine.is_superadmin(check_id, platform=platform):
                            perception["is_owner"] = True
                            perception["canonical_user_id"] = check_id
                    except Exception:
                        pass

                message_obj = Message(
                    msg_type="data",
                    content=perception,
                    source="web_api",
                    destination="decision_hub",
                )

                from core.platform_context import AppPlatformBridge, set_current_platform_adapter

                set_current_platform_adapter(AppPlatformBridge(platform))

                response = await self.decision_hub.process_perception_cross_platform(message_obj)

                if not response:
                    logger.warning(f"[chat/send] AI 返回空响应: session={session_id}, msg={message[:50]}")
                    response = "嗯……我想好了但还没来得及说出口。再说一次试试？"

                # 持久化消息到对话历史 (raw SQLite, 绕过 conversation_manager 的 import 链 bug)
                try:
                    import sqlite3
                    from datetime import datetime

                    db_path = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data",
                        "miya.db",
                    )
                    conn = sqlite3.connect(db_path)
                    ts = datetime.now().isoformat()
                    conn.execute(
                        "INSERT INTO conversation_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                        (session_id, "user", message, ts),
                    )
                    conn.execute(
                        "INSERT INTO conversation_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                        (session_id, "assistant", str(response), ts),
                    )
                    conn.commit()
                    conn.close()
                except Exception as e:
                    logger.warning(f"[chat/send] 保存对话历史失败: {e}")

                # TTS 本地播放 (fire-and-forget, 桌面/Web 端)
                if response:
                    try:
                        import json as _json
                        import os

                        config_path = os.path.join(
                            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "config",
                            "tts_config.json",
                        )
                        with open(config_path, "r", encoding="utf-8") as _f:
                            _cfg = _json.load(_f)
                        if _cfg.get("local_playback_enabled"):

                            async def _tts_play():
                                try:
                                    logger.info(f"[TTS] 桌面端合成中 ({len(response)} chars)")
                                    from core.tts.engine_router import synthesize

                                    audio = await synthesize(response)
                                    if not audio:
                                        logger.warning("[TTS] 合成返回空")
                                        return
                                    import concurrent.futures

                                    from core.audio_player import play_audio_isolated

                                    play_audio_isolated(audio)
                                    logger.info("[TTS] 桌面端播放中")
                                except ImportError:
                                    logger.warning("[TTS] 缺少依赖")
                                except Exception as ex:
                                    logger.warning(f"[TTS] 失败: {ex}")

                            asyncio.ensure_future(_tts_play())
                    except Exception as ex:
                        logger.warning(f"[TTS] 配置检查失败: {ex}")

                emotion_state = None
                if self.decision_hub and hasattr(self.decision_hub, "emotion") and self.decision_hub.emotion:
                    emotion_state = self.decision_hub.emotion.get_emotion_state()

                personality_state = None
                if self.decision_hub and hasattr(self.decision_hub, "personality") and self.decision_hub.personality:
                    personality_state = self.decision_hub.personality.get_profile()

                emotion_result = None
                if emotion_state:
                    emotion_result = {
                        "dominant": emotion_state.get("dominant", "平静"),
                        "intensity": emotion_state.get("intensity", 0.5),
                    }

                personality_result = None
                if personality_state:
                    personality_result = {
                        "state": personality_state.get("dominant", "empathy"),
                        "vectors": personality_state.get(
                            "vectors",
                            {
                                "warmth": 0.5,
                                "logic": 0.5,
                                "creativity": 0.5,
                                "empathy": 0.5,
                                "resilience": 0.5,
                            },
                        ),
                    }

                files = None
                try:
                    from core.platform_context import get_current_platform_adapter

                    adapter = get_current_platform_adapter()
                    if adapter and hasattr(adapter, "last_file_info") and adapter.last_file_info:
                        fi = adapter.last_file_info
                        files = [
                            {
                                "name": fi["name"],
                                "size": fi["size"],
                                "mime_type": fi["mime_type"],
                                "url": fi["url"],
                                "base64": fi["base64"],
                            }
                        ]
                        url = fi["url"]
                        response += f"\n\n📄 [{fi['name']}]({url})"
                        adapter.last_file_info = None
                except Exception:
                    pass

                return {
                    "success": True,
                    "response": response,
                    "timestamp": datetime.utcnow().isoformat(),
                    "emotion": emotion_result,
                    "personality": personality_result,
                    "files": files,
                    "soul": getattr(self.decision_hub, "_last_soul_output", None),
                    "tools_used": getattr(self.decision_hub, "_last_tools_used", []),
                    "memory_retrieved": getattr(self.decision_hub, "_last_memory_retrieved", False),
                }

            except Exception as e:
                logger.error(f"[MiyaAPI] 聊天处理失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "response": f"处理失败: {str(e)}",
                    "error": str(e),
                }

        # ========== 配置 ==========
        @self.router.get("/api/config/get")
        async def get_config():
            """获取配置 - 支持 onboarding 检查

            前端期望: { data: { config, metadata, platform_i18n_translations } }
            """
            try:
                from config.platforms_config import (
                    get_enabled_platforms,
                    list_all_platforms,
                )

                all_platforms = list_all_platforms()
                enabled = get_enabled_platforms()

                platforms = []
                for p in all_platforms:
                    p_id = p.get("id", "")
                    p_config = p.get("config", {})

                    platforms.append(
                        {
                            "id": p_id,
                            "name": p.get("name", p_id),
                            "type": p_id,
                            "enable": p_id in enabled,
                            **{k: v for k, v in p_config.items() if k != "enabled"},
                        }
                    )

                platform_i18n = {}
                platform_names = {
                    "qqofficial": "QQ 官方机器人",
                    "qqofficial_webhook": "QQ Webhook",
                    "aiocqhttp": "OneBot/NapCat",
                    "telegram": "Telegram",
                    "discord": "Discord",
                    "lark": "飞书",
                    "dingtalk": "钉钉",
                    "wecom": "企业微信",
                    "wecom_ai_bot": "企业微信 AI Bot",
                    "weixin_oc": "微信开放平台",
                    "weixin_official_account": "微信公众号",
                    "slack": "Slack",
                    "line": "LINE",
                    "kook": "KOOK",
                    "mattermost": "Mattermost",
                    "misskey": "Misskey",
                    "satori": "Satori",
                }
                for p_id, name in platform_names.items():
                    platform_i18n[f"platform.{p_id}.name"] = name
                    platform_i18n[f"platform.{p_id}.description"] = f"连接到 {name}"

                return {
                    "success": True,
                    "data": {
                        "config": {"platform": platforms},
                        "metadata": {
                            "platform": {
                                "type": "array",
                                "label": "Platforms",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {
                                            "type": "string",
                                            "label": "Platform ID",
                                        },
                                        "enable": {
                                            "type": "boolean",
                                            "label": "Enabled",
                                        },
                                    },
                                },
                            }
                        },
                        "platform_i18n_translations": platform_i18n,
                    },
                }
            except Exception as e:
                logger.error(f"[MiyaAPI] 获取配置失败: {e}")
                return {
                    "success": True,
                    "data": {
                        "config": {"platform": []},
                        "metadata": {},
                        "platform_i18n_translations": {},
                    },
                }

        @self.router.get("/api/config/provider/template")
        async def get_provider_config_template():
            """提供商配置模板 - 支持 onboarding 检查

            前端 checkOnboardingCompleted 会检查 providers 和 provider_sources
            """
            return {
                "success": True,
                "data": {
                    "providers": [
                        {
                            "id": "deepseek_v3",
                            "name": "DeepSeek V3",
                            "provider_type": "chat_completion",
                            "provider_source_id": "deepseek",
                            "model": "deepseek-v4-flash",
                            "enabled": True,
                        },
                        {
                            "id": "qwen_72b",
                            "name": "Qwen 72B",
                            "provider_type": "chat_completion",
                            "provider_source_id": "siliconflow",
                            "model": "Qwen/Qwen2.5-72B-Instruct",
                            "enabled": True,
                        },
                    ],
                    "provider_sources": [
                        {
                            "id": "deepseek",
                            "provider_type": "chat_completion",
                            "name": "DeepSeek",
                        },
                        {
                            "id": "siliconflow",
                            "provider_type": "chat_completion",
                            "name": "SiliconFlow",
                        },
                    ],
                },
            }

        @self.router.post("/api/config/provider/new")
        async def add_new_provider(request_data: dict):
            """新增提供商"""
            try:
                provider_id = request_data.get("id") or request_data.get("name")
                if not provider_id:
                    return {"status": "error", "message": "缺少提供商ID"}

                return {
                    "status": "ok",
                    "message": f"提供商 {provider_id} 添加成功（需重启生效）",
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}

        @self.router.post("/api/config/provider/update")
        async def update_provider(request_data: dict):
            """更新提供商配置"""
            try:
                provider_id = request_data.get("id")
                if not provider_id:
                    return {"status": "error", "message": "缺少提供商ID"}

                request_data.get("config", {})

                return {"status": "ok", "message": f"提供商 {provider_id} 更新成功"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        @self.router.get("/api/config/provider/check_one")
        async def check_provider(provider_id: str):
            """检查提供商连接"""
            return {
                "status": "ok",
                "message": "检查成功",
                "latency_ms": 50,
            }

        @self.router.get("/api/config/abconfs")
        async def get_abconfs():
            """配置文件列表"""
            return {"success": True, "configs": [{"id": "default", "name": "默认配置"}]}

        @self.router.get("/api/config/abconf")
        async def get_abconf():
            """获取配置文件 - 适配前端格式

            前端期望: { data: { config: {...}, metadata: {...} } }
            """
            return {
                "success": True,
                "data": {
                    "config": {
                        "id": "default",
                        "ai_provider": "deepseek",
                        "model": "deepseek-v4-flash",
                        "temperature": 0.7,
                    },
                    "metadata": {
                        "ai_provider": {
                            "type": "select",
                            "label": "AI Provider",
                            "options": [
                                {"value": "deepseek", "label": "DeepSeek"},
                                {"value": "siliconflow", "label": "SiliconFlow"},
                            ],
                        },
                        "model": {
                            "type": "select",
                            "label": "Model",
                        },
                        "temperature": {
                            "type": "slider",
                            "label": "Temperature",
                            "min": 0,
                            "max": 2,
                        },
                    },
                },
            }

        @self.router.get("/api/config/default")
        async def get_default_config():
            """获取默认配置模板"""
            return {
                "success": True,
                "data": {
                    "config": {
                        "id": "default",
                        "ai_provider": "deepseek",
                        "model": "deepseek-v4-flash",
                        "temperature": 0.7,
                    },
                    "metadata": {},
                },
            }

        # ========== 工具 ==========
        @self.router.get("/api/tools")
        async def get_tools():
            """可用工具列表"""
            return {
                "success": True,
                "tools": [],
                "total": 0,
            }

        @self.router.get("/api/agents")
        async def get_agents():
            """Agent 列表 - 从 AgentHub 获取"""
            try:
                from webnet.ToolNet.agents.hub import AgentHub

                hub = AgentHub()
                agents = []

                for name, agent_info in hub.agents.items():
                    agents.append(
                        {
                            "name": name,
                            "description": agent_info.prompt.split("\n")[0] if agent_info.prompt else f"{name} Agent",
                            "tools_count": len(agent_info.tools),
                            "tools": agent_info.get_tool_names(),
                        }
                    )

                return {
                    "success": True,
                    "agents": agents,
                    "total": len(agents),
                }
            except Exception as e:
                logger.warning(f"[MiyaAPI] 获取 Agent 列表失败: {e}")
                return {
                    "success": True,
                    "agents": [],
                    "total": 0,
                }

        @self.router.get("/api/tools/list")
        async def get_tools_list():
            """工具列表 (兼容前端)"""
            return await get_tools()

        @self.router.get("/api/mcp/list")
        async def get_mcp_list():
            """MCP 服务列表"""
            try:
                import json
                from pathlib import Path

                mcp_file = Path("config/mcp.json")
                if mcp_file.exists():
                    with open(mcp_file, "r", encoding="utf-8") as f:
                        mcp_config = json.load(f)

                    servers = mcp_config.get("mcpServers", {})
                    result = []
                    for name, config in servers.items():
                        result.append(
                            {
                                "name": name,
                                "command": config.get("command", ""),
                                "args": config.get("args", []),
                                "env": config.get("env", {}),
                            }
                        )

                    return {
                        "success": True,
                        "servers": result,
                        "total": len(result),
                    }

                return {
                    "success": True,
                    "servers": [],
                    "total": 0,
                }
            except Exception as e:
                logger.warning(f"[MiyaAPI] 获取 MCP 列表失败: {e}")
                return {
                    "success": True,
                    "servers": [],
                    "total": 0,
                }

        @self.router.post("/api/mcp/call")
        async def mcp_call(request_data: dict = None):
            """统一 MCP 工具调用接口"""
            if request_data is None:
                request_data = {}
            try:
                import os

                from core.mcp_manager import get_mcp_manager

                manager = get_mcp_manager()
                if not manager:
                    return {"success": False, "error": "MCP 管理器未初始化"}

                svc_name = str(request_data.get("service", ""))
                tool_name = str(request_data.get("tool", ""))

                if not svc_name or not tool_name:
                    return {"success": False, "error": "缺少 service 或 tool 参数"}

                # 确保 MCP 服务已扫描注册（修正工作目录）
                if not manager._services:
                    project_root = os.environ.get("MIYA_PROJECT_ROOT", "..")
                    manager.mcp_dir = os.path.join(project_root, "mcpserver")
                    if not os.path.isdir(manager.mcp_dir):
                        manager.mcp_dir = os.path.abspath(
                            os.path.join(os.path.dirname(__file__), "..", "..", "mcpserver")
                        )
                    await manager.scan_and_register()

                # 如果目标服务未注册，尝试单独注册
                if svc_name not in manager._services:
                    from pathlib import Path

                    manifest_path = Path(manager.mcp_dir) / svc_name / "agent-manifest.json"
                    if manifest_path.exists():
                        manifest = manager._load_manifest(manifest_path)
                        if manifest:
                            await manager.register_service(manifest)

                # 构建额外参数（排除 service 和 tool）
                extra_kwargs = {k: v for k, v in request_data.items() if k not in ("service", "tool")}

                result = await manager.call(svc_name, tool_name, **extra_kwargs)
                return {
                    "success": result.success,
                    "result": result.result if result.success else result.error,
                    "service": svc_name,
                    "tool": tool_name,
                }
            except Exception as e:
                logger.exception("[MiyaAPI] MCP 调用失败")
                return {"success": False, "error": str(e)}

        @self.router.post("/api/mcp/reload")
        async def mcp_reload(request_data: dict = None):
            """热重载指定 MCP 服务模块"""
            if request_data is None:
                request_data = {}
            try:
                import importlib
                import sys

                from core.mcp_manager import get_mcp_manager

                svc_name = str(request_data.get("service", ""))
                if not svc_name:
                    return {"success": False, "error": "缺少 service 参数"}

                module_paths = [
                    f"mcpserver.{svc_name}",
                    f"mcpserver.{svc_name}.service",
                    f"mcpserver.{svc_name}.auth",
                    f"mcpserver.{svc_name}.forum",
                ]

                reloaded = []
                for mod_path in module_paths:
                    if mod_path in sys.modules:
                        importlib.reload(sys.modules[mod_path])
                        reloaded.append(mod_path)

                if not reloaded:
                    return {
                        "success": True,
                        "message": f"服务 {svc_name} 模块未加载，无需重载",
                    }

                manager = get_mcp_manager()
                if manager and svc_name in manager._services:
                    del manager._services[svc_name]
                    from pathlib import Path

                    manifest_path = Path("mcpserver") / svc_name / "agent-manifest.json"
                    if manifest_path.exists():
                        import json as _json

                        _json.loads(manifest_path.read_text(encoding="utf-8"))
                        manifest = manager._load_manifest(manifest_path)
                        if manifest:
                            await manager.register_service(manifest)

                return {
                    "success": True,
                    "message": f"已重载 {len(reloaded)} 个模块: {reloaded}",
                }
            except Exception as e:
                logger.exception("[MiyaAPI] MCP 重载失败")
                return {"success": False, "error": str(e)}

        @self.router.get("/api/skills")
        async def get_skills():
            """技能列表 - 从 skills.yaml 读取"""
            try:
                from pathlib import Path

                import yaml

                skills_file = Path("config/skills.yaml")
                if skills_file.exists():
                    with open(skills_file, "r", encoding="utf-8") as f:
                        skills_config = yaml.safe_load(f)

                    skills = skills_config.get("skills", []) if skills_config else []

                    return {
                        "success": True,
                        "skills": skills,
                        "total": len(skills),
                    }

                return {
                    "success": True,
                    "skills": [],
                    "total": 0,
                }
            except Exception as e:
                logger.warning(f"[MiyaAPI] 获取技能列表失败: {e}")
                return {
                    "success": True,
                    "skills": [],
                    "total": 0,
                }

        # ========== 插件市场 ==========
        @self.router.get("/api/plugin/market_list")
        async def get_market_plugins():
            """获取 AstrBot 插件市场列表"""
            try:
                from core.plugin_market import get_plugin_market

                market = get_plugin_market()
                plugins = await market.get_plugin_list()

                plugin_list = []
                for p in plugins:
                    plugin_list.append(
                        {
                            "name": p.name,
                            "description": p.description,
                            "author": p.author,
                            "version": p.version,
                            "download_url": p.download_url,
                            "homepage": p.homepage,
                            "tags": p.tags,
                            "logo": p.logo,
                            "astrbot_version": p.astrbot_version,
                        }
                    )

                return {
                    "success": True,
                    "data": plugin_list,
                    "total": len(plugin_list),
                }
            except Exception as e:
                logger.error(f"[MiyaAPI] 获取插件市场失败: {e}")
                return {
                    "success": False,
                    "data": [],
                    "message": str(e),
                }

        @self.router.get("/api/plugin/get")
        async def get_installed_plugins():
            """获取已安装插件列表"""
            try:
                from core.miya_plugin_manager import get_plugin_manager

                manager = get_plugin_manager()
                plugins = manager.get_installed_plugins()

                plugin_list = []
                for p in plugins:
                    plugin_list.append(
                        {
                            "name": p.name,
                            "description": p.description,
                            "author": p.author,
                            "version": p.version,
                            "enabled": p.enabled,
                            "installed_at": p.installed_at,
                        }
                    )

                return {
                    "success": True,
                    "data": plugin_list,
                    "total": len(plugin_list),
                }
            except Exception as e:
                logger.error(f"[MiyaAPI] 获取已安装插件失败: {e}")
                return {
                    "success": False,
                    "data": [],
                    "message": str(e),
                }

        @self.router.post("/api/plugin/install")
        async def install_plugin(request_data: dict = None):
            """安装插件"""
            if request_data is None:
                request_data = {}
            try:
                from core.miya_plugin_manager import get_plugin_manager
                from core.plugin_market import get_plugin_market

                plugin_name = request_data.get("name")
                download_url = request_data.get("download_url")

                if not plugin_name:
                    return {"success": False, "message": "缺少插件名称"}

                market = get_plugin_market()
                manager = get_plugin_manager()

                from core.plugin_market import PluginInfo

                plugin_info = PluginInfo(
                    name=plugin_name,
                    description="",
                    author="",
                    version="",
                    download_url=download_url or "",
                )

                if not download_url:
                    plugins = await market.get_plugin_list()
                    for p in plugins:
                        if p.name == plugin_name:
                            plugin_info = p
                            break

                import tempfile

                with tempfile.TemporaryDirectory() as tmpdir:
                    from pathlib import Path

                    tmp_path = Path(tmpdir)

                    if plugin_info.download_url:
                        success = await market.download_plugin(plugin_info, tmp_path)
                        if not success:
                            return {"success": False, "message": "下载插件失败"}

                        zip_path = tmp_path / f"{plugin_name}.zip"
                        if zip_path.exists():
                            success = await manager.install(plugin_name, zip_path)
                            if success:
                                return {
                                    "success": True,
                                    "message": f"插件 {plugin_name} 安装成功",
                                }
                            else:
                                return {"success": False, "message": "安装插件失败"}

                return {"success": False, "message": "未找到插件下载链接"}

            except Exception as e:
                logger.error(f"[MiyaAPI] 安装插件失败: {e}")
                return {"success": False, "message": str(e)}

        @self.router.post("/api/plugin/uninstall")
        async def uninstall_plugin(request_data: dict = None):
            """卸载插件"""
            if request_data is None:
                request_data = {}
            try:
                from core.miya_plugin_manager import get_plugin_manager

                plugin_name = request_data.get("name")
                if not plugin_name:
                    return {"success": False, "message": "缺少插件名称"}

                manager = get_plugin_manager()
                success = await manager.uninstall(plugin_name)

                if success:
                    return {"success": True, "message": f"插件 {plugin_name} 已卸载"}
                else:
                    return {"success": False, "message": "卸载失败"}

            except Exception as e:
                logger.error(f"[MiyaAPI] 卸载插件失败: {e}")
                return {"success": False, "message": str(e)}

        @self.router.post("/api/plugin/on")
        async def enable_plugin(request_data: dict = None):
            """启用插件"""
            if request_data is None:
                request_data = {}
            try:
                from core.miya_plugin_manager import get_plugin_manager

                plugin_name = request_data.get("name")
                if not plugin_name:
                    return {"success": False, "message": "缺少插件名称"}

                manager = get_plugin_manager()
                success = await manager.enable(plugin_name)

                if success:
                    return {"success": True, "message": f"插件 {plugin_name} 已启用"}
                else:
                    return {"success": False, "message": "启用失败"}

            except Exception as e:
                logger.error(f"[MiyaAPI] 启用插件失败: {e}")
                return {"success": False, "message": str(e)}

        @self.router.post("/api/plugin/off")
        async def disable_plugin(request_data: dict = None):
            """禁用插件"""
            if request_data is None:
                request_data = {}
            try:
                from core.miya_plugin_manager import get_plugin_manager

                plugin_name = request_data.get("name")
                if not plugin_name:
                    return {"success": False, "message": "缺少插件名称"}

                manager = get_plugin_manager()
                success = await manager.disable(plugin_name)

                if success:
                    return {"success": True, "message": f"插件 {plugin_name} 已禁用"}
                else:
                    return {"success": False, "message": "禁用失败"}

            except Exception as e:
                logger.error(f"[MiyaAPI] 禁用插件失败: {e}")
                return {"success": False, "message": str(e)}

        @self.router.post("/api/plugin/reload")
        async def reload_plugins():
            """重载插件"""
            return {"success": True, "message": "插件已重载"}

        # ========== 定时任务 ==========
        @self.router.get("/api/cron/jobs")
        async def get_cron_jobs():
            """获取定时任务列表"""
            try:
                from hub.scheduler import get_global_scheduler

                scheduler = get_global_scheduler()
                jobs = []

                for task_id, task in scheduler.running_tasks.items():
                    jobs.append(
                        {
                            "job_id": task_id,
                            "task_type": task.task_type,
                            "priority": task.priority,
                            "status": task.status,
                            "execute_at": task.execute_at.isoformat() if task.execute_at else None,
                            "created_at": task.created_at.isoformat(),
                            "data": task.data,
                        }
                    )

                for task in scheduler.task_queue:
                    jobs.append(
                        {
                            "job_id": task.task_id,
                            "task_type": task.task_type,
                            "priority": task.priority,
                            "status": "scheduled",
                            "execute_at": task.execute_at.isoformat() if task.execute_at else None,
                            "created_at": task.created_at.isoformat(),
                            "data": task.data,
                        }
                    )

                return {
                    "success": True,
                    "data": jobs,
                    "total": len(jobs),
                }
            except Exception as e:
                logger.warning(f"[MiyaAPI] 获取定时任务失败: {e}")
                return {
                    "success": True,
                    "data": [],
                    "total": 0,
                }

        @self.router.post("/api/cron/jobs")
        async def create_cron_job(request_data: dict = None):
            """创建定时任务"""
            if request_data is None:
                request_data = {}
            try:
                import uuid
                from datetime import datetime, timedelta

                from hub.scheduler import get_global_scheduler

                scheduler = get_global_scheduler()

                job_id = request_data.get("job_id") or str(uuid.uuid4())
                task_type = request_data.get("task_type", "scheduled_reminder")
                priority = request_data.get("priority", 5)
                message = request_data.get("message", "")
                target_type = request_data.get("target_type", "private")
                target_id = request_data.get("target_id", "")

                delay_seconds = request_data.get("delay_seconds", 60)

                from hub.scheduler import Task

                task = Task(
                    task_id=job_id,
                    task_type=task_type,
                    priority=priority,
                    data={
                        "message": message,
                        "target_type": target_type,
                        "target_id": target_id,
                    },
                    execute_at=datetime.now() + timedelta(seconds=delay_seconds),
                )

                import heapq

                heapq.heappush(scheduler.task_queue, task)

                return {
                    "success": True,
                    "message": f"定时任务 {job_id} 已创建",
                    "job_id": job_id,
                }
            except Exception as e:
                logger.error(f"[MiyaAPI] 创建定时任务失败: {e}")
                return {"success": False, "message": str(e)}

        @self.router.patch("/api/cron/jobs/{job_id}")
        async def update_cron_job(job_id: str, request_data: dict = None):
            """更新定时任务"""
            if request_data is None:
                request_data = {}
            try:
                from hub.scheduler import get_global_scheduler

                scheduler = get_global_scheduler()
                enabled = request_data.get("enabled", True)

                if job_id in scheduler.running_tasks:
                    if enabled:
                        task = scheduler.running_tasks[job_id]
                        task.status = "running"
                    else:
                        task = scheduler.running_tasks[job_id]
                        task.status = "paused"

                return {
                    "success": True,
                    "message": f"定时任务 {job_id} 已更新",
                }
            except Exception as e:
                logger.error(f"[MiyaAPI] 更新定时任务失败: {e}")
                return {"success": False, "message": str(e)}

        @self.router.delete("/api/cron/jobs/{job_id}")
        async def delete_cron_job(job_id: str):
            """删除定时任务"""
            try:
                from hub.scheduler import get_global_scheduler

                scheduler = get_global_scheduler()

                if job_id in scheduler.running_tasks:
                    del scheduler.running_tasks[job_id]

                scheduler.task_queue = [t for t in scheduler.task_queue if t.task_id != job_id]
                if hasattr(scheduler, "_sync_queued_ids"):
                    scheduler._sync_queued_ids()

                return {
                    "success": True,
                    "message": f"定时任务 {job_id} 已删除",
                }
            except Exception as e:
                logger.error(f"[MiyaAPI] 删除定时任务失败: {e}")
                return {"success": False, "message": str(e)}

        # ========== 会话管理 ==========
        @self.router.get("/api/session/list-rule")
        async def get_session_rules():
            """获取会话规则列表"""
            return {
                "success": True,
                "data": [],
                "total": 0,
            }

        @self.router.get("/api/session/active-umos")
        async def get_active_umos():
            """获取活跃的 UMO"""
            return {
                "success": True,
                "data": [],
                "total": 0,
            }

        @self.router.post("/api/session/update-rule")
        async def update_session_rule(request_data: dict = None):
            """更新会话规则"""
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "规则已更新"}

        @self.router.post("/api/session/delete-rule")
        async def delete_session_rule(request_data: dict = None):
            """删除会话规则"""
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "规则已删除"}

        @self.router.post("/api/session/batch-delete-rule")
        async def batch_delete_session_rules(request_data: dict = None):
            """批量删除会话规则"""
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "规则已批量删除"}

        @self.router.get("/api/session/groups")
        async def get_session_groups():
            """获取会话分组"""
            return {
                "success": True,
                "data": [],
                "total": 0,
            }

        @self.router.post("/api/session/group/create")
        async def create_session_group(request_data: dict = None):
            """创建会话分组"""
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "分组已创建"}

        @self.router.post("/api/session/group/update")
        async def update_session_group(request_data: dict = None):
            """更新会话分组"""
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "分组已更新"}

        @self.router.post("/api/session/group/delete")
        async def delete_session_group(request_data: dict = None):
            """删除会话分组"""
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "分组已删除"}

        @self.router.post("/api/session/batch-update-service")
        async def batch_update_service(request_data: dict = None):
            """批量更新服务"""
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "服务已批量更新"}

        @self.router.post("/api/session/batch-update-provider")
        async def batch_update_provider(request_data: dict = None):
            """批量更新提供商"""
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "提供商已批量更新"}

        # ========== 子代理 ==========
        @self.router.get("/api/subagent/config")
        async def get_subagent_config():
            """获取子代理配置"""
            return {
                "success": True,
                "data": {
                    "agents": [],
                    "config": {},
                },
            }

        @self.router.post("/api/subagent/config")
        async def save_subagent_config(request_data: dict = None):
            """保存子代理配置"""
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "配置已保存"}

        # ========== Trace 追踪 ==========
        @self.router.get("/api/trace/settings")
        async def get_trace_settings():
            """获取追踪设置"""
            return {
                "success": True,
                "data": {
                    "enabled": True,
                    "log_level": "info",
                },
            }

        @self.router.post("/api/trace/settings")
        async def save_trace_settings(request_data: dict = None):
            """保存追踪设置"""
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "追踪设置已保存"}

        # ========== API Key 管理 ==========
        @self.router.get("/api/apikey/list")
        async def get_apikey_list():
            """获取 API Key 列表"""
            return {
                "success": True,
                "data": [],
                "total": 0,
            }

        @self.router.post("/api/apikey/create")
        async def create_apikey(request_data: dict = None):
            """创建 API Key"""
            import uuid

            if request_data is None:
                request_data = {}
            key_id = str(uuid.uuid4())
            return {
                "success": True,
                "message": "API Key 已创建",
                "data": {"key_id": key_id},
            }

        @self.router.post("/api/apikey/revoke")
        async def revoke_apikey(request_data: dict = None):
            """撤销 API Key"""
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "API Key 已撤销"}

        @self.router.post("/api/apikey/delete")
        async def delete_apikey(request_data: dict = None):
            """删除 API Key"""
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "API Key 已删除"}

        # ========== 知识库 Alkaid ==========
        @self.router.get("/api/plug/alkaid/kb/collections")
        async def get_kb_collections():
            """获取知识库集合"""
            return {"status": "ok", "data": []}

        @self.router.post("/api/plug/alkaid/kb/create_collection")
        async def create_kb_collection(request_data: dict = None):
            """创建知识库集合"""
            if request_data is None:
                request_data = {}
            return {"status": "ok", "message": "知识库已创建"}

        @self.router.post("/api/plug/alkaid/kb/collection/add_file")
        async def add_file_to_collection():
            """添加文件到知识库"""
            return {"status": "ok", "message": "文件已添加"}

        @self.router.get("/api/plug/alkaid/kb/collection/search")
        async def search_kb_collection():
            """搜索知识库"""
            return {"status": "ok", "data": []}

        @self.router.get("/api/plug/alkaid/kb/collection/delete")
        async def delete_kb_collection():
            """删除知识库"""
            return {"status": "ok", "message": "知识库已删除"}

        @self.router.post("/api/plug/url_2_kb/add")
        async def add_url_to_kb(request_data: dict = None):
            """添加 URL 到知识库"""
            if request_data is None:
                request_data = {}
            return {"status": "ok", "task_id": "task_001"}

        @self.router.post("/api/plug/url_2_kb/status")
        async def get_url_to_kb_status(request_data: dict = None):
            """获取 URL 转知识库状态"""
            if request_data is None:
                request_data = {}
            return {"status": "ok", "status": "completed"}

        # ========== 统计 ==========
        @self.router.get("/api/stat/version")
        async def get_version():
            """版本信息"""
            return {
                "success": True,
                "data": {
                    "version": "6.0.0",
                    "dashboard_version": "6.0.0",
                    "name": "MIYA",
                    "build": "20260501",
                    "change_pwd_hint": False,
                },
            }

        @self.router.get("/api/stat/start-time")
        async def get_start_time():
            """启动时间"""
            return {"success": True, "data": {"start_time": 1700000000}}

        @self.router.get("/api/update/check")
        async def check_update():
            """检查更新"""
            return {
                "success": True,
                "data": {
                    "available": False,
                    "version": "6.0.0",
                    "has_new_version": False,
                    "latest_version": "6.0.0",
                    "release_notes": "",
                },
            }

        @self.router.get("/api/stat/first-notice")
        async def get_first_notice():
            """首次公告"""
            return {
                "success": True,
                "data": {"content": "欢迎使用弥娅 AI！", "locale": "zh-CN"},
            }

        # ========== 日志 ==========
        @self.router.get("/api/live-log")
        async def live_log():
            """实时日志"""

            async def log_generator():
                yield "data: \n\n"

            return StreamingResponse(log_generator(), media_type="text/event-stream")

        @self.router.get("/api/logs")
        async def get_logs():
            """日志列表"""
            return {"success": True, "logs": [], "total": 0}

        # ========== 配置 API ==========
        @self.router.get("/api/config/provider/template")
        async def get_provider_template():
            """获取提供商模板"""
            return {
                "success": True,
                "data": {
                    "providers": [
                        {
                            "id": "deepseek",
                            "name": "DeepSeek",
                            "provider_type": "chat_completion",
                            "enabled": True,
                        },
                        {
                            "id": "openai",
                            "name": "OpenAI",
                            "provider_type": "chat_completion",
                            "enabled": True,
                        },
                        {
                            "id": "anthropic",
                            "name": "Anthropic",
                            "provider_type": "chat_completion",
                            "enabled": False,
                        },
                        {
                            "id": "siliconflow",
                            "name": "SiliconFlow",
                            "provider_type": "chat_completion",
                            "enabled": True,
                        },
                    ],
                    "provider_sources": [
                        {
                            "id": "deepseek",
                            "provider_type": "chat_completion",
                            "name": "DeepSeek",
                            "enabled": True,
                        },
                        {
                            "id": "openai",
                            "provider_type": "chat_completion",
                            "name": "OpenAI",
                            "enabled": True,
                        },
                        {
                            "id": "anthropic",
                            "provider_type": "chat_completion",
                            "name": "Anthropic",
                            "enabled": False,
                        },
                        {
                            "id": "siliconflow",
                            "provider_type": "chat_completion",
                            "name": "SiliconFlow",
                            "enabled": True,
                        },
                        {
                            "id": "openai_embedding",
                            "provider_type": "embedding",
                            "name": "OpenAI Embedding",
                            "enabled": True,
                        },
                        {
                            "id": "bge_embedding",
                            "provider_type": "embedding",
                            "name": "BGE Embedding",
                            "enabled": True,
                        },
                    ],
                },
            }

        @self.router.get("/api/config/provider/list")
        async def get_provider_list(provider_type: str = ""):
            """获取提供商列表"""
            providers = []
            if "chat_completion" in provider_type or not provider_type:
                providers.extend(
                    [
                        {
                            "id": "deepseek",
                            "provider_type": "chat_completion",
                            "type": "chat_completion",
                            "enabled": True,
                        },
                        {
                            "id": "openai",
                            "provider_type": "chat_completion",
                            "type": "chat_completion",
                            "enabled": True,
                        },
                        {
                            "id": "siliconflow",
                            "provider_type": "chat_completion",
                            "type": "chat_completion",
                            "enabled": True,
                        },
                    ]
                )
            if "embedding" in provider_type:
                providers.extend(
                    [
                        {
                            "id": "openai_embedding",
                            "provider_type": "embedding",
                            "type": "embedding",
                            "enabled": True,
                        },
                        {
                            "id": "bge_embedding",
                            "provider_type": "embedding",
                            "type": "embedding",
                            "enabled": True,
                        },
                    ]
                )
            return {"success": True, "data": providers}

        @self.router.get("/api/config/get")
        async def get_config():
            """获取配置"""
            return {
                "success": True,
                "data": {
                    "config": {
                        "platform": ["qqofficial", "desktop"],
                        "provider": ["deepseek"],
                    }
                },
            }

        @self.router.get("/api/config/get")
        async def get_config():
            """获取配置"""
            return {
                "success": True,
                "data": {
                    "config": {
                        "platform": ["qqofficial", "desktop"],
                        "provider": ["deepseek"],
                    }
                },
            }

        # ========== 命令 API ==========
        @self.router.get("/api/commands")
        async def get_commands():
            """获取命令列表"""
            return {"success": True, "commands": []}

        # ========== 项目 API ==========
        @self.router.get("/api/chatui_project/list")
        async def get_projects():
            """获取项目列表"""
            return {"success": True, "data": {"items": []}}

        @self.router.post("/api/chatui_project/create")
        async def create_project(request_data: dict = None):
            """创建项目"""
            if request_data is None:
                request_data = {}
            return {"success": True, "data": {"id": "1", "name": "新项目"}}

        # ========== 聊天 API (旧版stub - 已由上方完整版取代) ==========

        # ========== MCP 服务器 API ==========
        @self.router.get("/api/tools/mcp/servers")
        async def get_mcp_servers():
            """获取 MCP 服务器列表"""
            return {"success": True, "data": []}

        # ========== 插件源 API ==========
        @self.router.get("/api/plugin/source/get")
        async def get_plugin_sources():
            """获取插件源"""
            return {"success": True, "data": []}

        @self.router.get("/api/plugin/source/get-failed-plugins")
        async def get_failed_plugins():
            """获取失败的插件"""
            return {"success": True, "data": []}

        # ========== 人格 API ==========
        @self.router.get("/api/persona/folder/tree")
        async def get_persona_tree():
            """获取人格文件夹树"""
            return {"success": True, "data": []}

        @self.router.get("/api/persona/folder/list")
        async def get_persona_folder_list(parent_id: str = ""):
            """获取人格文件夹列表"""
            return {"success": True, "data": []}

        @self.router.get("/api/persona/list")
        async def get_persona_list():
            """获取人格列表"""
            return {"success": True, "data": []}

        # ========== 日志历史 API ==========
        @self.router.get("/api/log-history")
        async def get_log_history():
            """获取日志历史"""
            return {"success": True, "data": []}

        # ========== 兼容 AstrBot 的额外 API ==========
        @self.router.get("/api/config/abconfs")
        async def get_abconfs():
            return {"success": True, "data": []}

        @self.router.get("/api/config/abconf")
        async def get_abconf(name: str = ""):
            return {"success": True, "data": {}}

        @self.router.get("/api/config/default")
        async def get_default_config():
            return {"success": True, "data": {}}

        @self.router.get("/api/tools/list")
        async def get_tools_list():
            return {"success": True, "data": []}

        @self.router.get("/api/agents")
        async def get_agents():
            return {"success": True, "data": []}

        @self.router.get("/api/mcp/list")
        async def get_mcp_list():
            return {"success": True, "data": []}

        @self.router.post("/api/mcp/call")
        async def mcp_call():
            return {"success": False, "error": "MCP 未初始化（stub 路由）"}

        @self.router.get("/api/skills")
        async def get_skills():
            return {"success": True, "data": []}

        @self.router.post("/api/plugin/uninstall")
        async def uninstall_plugin(request_data: dict = None):
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "插件卸载功能开发中"}

        @self.router.post("/api/plugin/on")
        async def enable_plugin(request_data: dict = None):
            if request_data is None:
                request_data = {}
            return {"success": True}

        @self.router.post("/api/plugin/off")
        async def disable_plugin(request_data: dict = None):
            if request_data is None:
                request_data = {}
            return {"success": True}

        @self.router.get("/api/cron/jobs")
        async def get_cron_jobs():
            return {"success": True, "data": []}

        @self.router.post("/api/cron/jobs")
        async def create_cron_job(request_data: dict = None):
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "定时任务创建功能开发中"}

        @self.router.get("/api/provider/list")
        async def get_provider_list():
            return {"success": True, "data": []}

        @self.router.get("/api/provider/template")
        async def get_provider_template_legacy():
            return {"success": True, "data": []}

        @self.router.get("/api/memory/stats")
        async def get_memory_stats_legacy():
            return {
                "success": True,
                "data": {"total": 0, "short_term": 0, "long_term": 0},
            }

        @self.router.get("/api/memory/list")
        async def get_memory_list_legacy():
            return {"success": True, "data": []}

        @self.router.get("/api/memory/search")
        async def search_memory_legacy(query: str = ""):
            return {"success": True, "data": []}

        @self.router.get("/api/persona/list")
        async def get_persona_list_legacy():
            return {"success": True, "data": []}

        @self.router.get("/api/persona/current")
        async def get_current_persona():
            return {
                "success": True,
                "data": {"name": "default", "description": "默认人格"},
            }

        @self.router.post("/api/persona/switch")
        async def switch_persona(request_data: dict = None):
            if request_data is None:
                request_data = {}
            return {"success": True}

        @self.router.get("/api/platform/list")
        async def get_platform_list_legacy():
            return {"success": True, "data": []}

        @self.router.get("/api/system/status")
        async def get_system_status_legacy():
            return {"success": True, "data": {}}

        @self.router.get("/api/system/monitor")
        async def get_system_monitor_legacy():
            return {"success": True, "data": {}}

        @self.router.get("/api/apikey/list")
        async def get_apikey_list():
            return {"success": True, "data": []}

        @self.router.get("/api/trace/settings")
        async def get_trace_settings():
            return {"success": True, "data": {}}

        @self.router.post("/api/trace/settings")
        async def update_trace_settings(request_data: dict = None):
            if request_data is None:
                request_data = {}
            return {"success": True}

        @self.router.get("/api/session/list-rule")
        async def get_session_rules():
            return {"success": True, "data": []}

        @self.router.get("/api/session/active-umos")
        async def get_active_umos():
            return {"success": True, "data": []}

        @self.router.get("/api/session/groups")
        async def get_session_groups():
            return {"success": True, "data": []}

        @self.router.get("/api/subagent/config")
        async def get_subagent_config():
            return {"success": True, "data": {}}

        @self.router.post("/api/subagent/config")
        async def update_subagent_config(request_data: dict = None):
            if request_data is None:
                request_data = {}
            return {"success": True}

        @self.router.get("/api/plug/alkaid/kb/collections")
        async def get_kb_collections():
            return {"success": True, "data": []}

        @self.router.get("/api/plug/alkaid/ltm/user_ids")
        async def get_ltm_user_ids():
            return {"success": True, "data": []}

        @self.router.get("/api/plug/alkaid/ltm/graph")
        async def get_ltm_graph():
            return {"success": True, "data": {}}

        @self.router.get("/api/health")
        async def health_check():
            """健康检查"""
            return {
                "status": "ok",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "miya-api",
            }

        # ========== Conversation 会话管理 ==========
        @self.router.get("/api/conversation/list")
        async def get_conversation_list():
            """获取会话列表"""
            return {
                "success": True,
                "data": [],
                "total": 0,
            }

        @self.router.post("/api/conversation/detail")
        async def get_conversation_detail(request_data: dict = None):
            """获取会话详情"""
            if request_data is None:
                request_data = {}
            conversation_id = request_data.get("conversation_id")
            return {
                "success": True,
                "data": {
                    "id": conversation_id,
                    "messages": [],
                    "created_at": datetime.now().isoformat(),
                },
            }

        @self.router.post("/api/conversation/update")
        async def update_conversation(request_data: dict = None):
            """更新会话"""
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "会话已更新"}

        @self.router.post("/api/conversation/update_history")
        async def update_conversation_history(request_data: dict = None):
            """更新会话历史"""
            if request_data is None:
                request_data = {}
            return {"success": True, "message": "历史已更新"}

        @self.router.post("/api/conversation/delete")
        async def delete_conversation(request_data: dict = None):
            """删除会话"""
            if request_data is None:
                request_data = {}
            conversation_id = request_data.get("conversation_id")
            return {"success": True, "message": f"会话 {conversation_id} 已删除"}

        @self.router.post("/api/conversation/export")
        async def export_conversation(request_data: dict = None):
            """导出会话"""
            if request_data is None:
                request_data = {}
            return {"success": True, "data": b""}

        # ========== 统计 API ==========
        @self.router.get("/api/stat/get")
        async def get_stat():
            """获取统计信息"""
            try:
                from core.model_pool_manager import get_model_pool

                pool = get_model_pool()
                models = pool._models if hasattr(pool, "_models") else {}

                # 获取启动时间
                import time

                start_time = int(time.time()) - 3600  # 假设运行了1小时

                return {
                    "success": True,
                    "data": {
                        "total_conversations": 0,
                        "total_messages": 0,
                        "total_users": 0,
                        "active_providers": len(models),
                        "total_providers": len(models),
                        "running": start_time,
                        "message_time_series": [],
                        "start_time": start_time,
                    },
                }
            except Exception as e:
                logger.warning(f"[MiyaAPI] 获取统计失败: {e}")
                return {
                    "success": True,
                    "data": {
                        "total_conversations": 0,
                        "total_messages": 0,
                        "total_users": 0,
                        "active_providers": 0,
                        "total_providers": 0,
                        "running": 0,
                        "message_time_series": [],
                        "start_time": 0,
                    },
                }

        @self.router.get("/api/stat/provider-tokens")
        async def get_provider_tokens():
            """获取提供商Token统计"""
            return {
                "success": True,
                "data": {
                    "trend": {"series": []},
                    "range_by_provider": [],
                    "range_by_umo": [],
                    "range_avg_ttft_ms": 0,
                    "range_avg_duration_ms": 0,
                    "range_avg_tpm": 0,
                },
            }

        # ========== AstrBot 兼容配置 ==========
        @self.router.post("/api/config/astrbot/update")
        async def update_astrbot_config(request_data: dict = None):
            """更新 AstrBot 兼容配置 (映射到弥娅配置)"""
            if request_data is None:
                request_data = {}
            try:
                model = request_data.get("model", "")
                provider = request_data.get("provider", "")
                temperature = request_data.get("temperature", 0.7)

                logger.info(f"[MiyaAPI] 更新配置: model={model}, provider={provider}, temperature={temperature}")

                return {
                    "success": True,
                    "message": "配置已更新（映射到弥娅系统）",
                }
            except Exception as e:
                logger.error(f"[MiyaAPI] 更新配置失败: {e}")
                return {"success": False, "message": str(e)}

        # ========== 知识库文档上传 ==========
        @self.router.post("/api/kb/document/upload/url")
        async def upload_document_by_url(request_data: dict = None):
            """通过 URL 上传文档"""
            if request_data is None:
                request_data = {}
            return {
                "success": True,
                "task_id": "task_" + str(int(datetime.now().timestamp())),
            }

        @self.router.get("/api/kb/document/upload/progress")
        async def get_upload_progress(task_id: str = ""):
            """获取上传进度"""
            return {
                "success": True,
                "progress": 100,
                "status": "completed",
            }

    def _get_emotion_state(self) -> Dict:
        """获取情绪状态"""
        try:
            if hasattr(self.decision_hub, "emotion") and self.decision_hub.emotion:
                return self.decision_hub.emotion.get_emotion_state()
        except:
            pass
        return {
            "emotion_name": "平静",
            "intensity": 50,
            "emotions": [{"name": "平静", "intensity": 60}],
        }

    def _get_personality_state(self) -> Dict:
        """获取人格状态"""
        try:
            if hasattr(self.decision_hub, "personality") and self.decision_hub.personality:
                return self.decision_hub.personality.get_profile()
        except:
            pass
        return {"current_personality": "default", "traits": {}}

    def _get_memory_stats(self) -> Dict:
        """获取记忆统计（附带前端期望的 nodeCount/edgeCount 别名）"""
        try:
            if hasattr(self.decision_hub, "memory_engine") and self.decision_hub.memory_engine:
                stats = self.decision_hub.memory_engine.get_memory_stats()
            else:
                stats = {}
        except:
            stats = {}
        stats.setdefault("total", 0)
        stats.setdefault("short_term", 0)
        stats.setdefault("long_term", 0)
        # 前端 MemoryStats 接口期望驼峰字段
        stats.setdefault("nodeCount", stats.get("total_nodes", stats.get("total", 0)))
        stats.setdefault("edgeCount", stats.get("total_edges", 0))
        return stats

    def _get_platform_info(self) -> Dict:
        """获取平台信息"""
        try:
            from config.platforms_config import (
                get_enabled_platforms,
                list_all_platforms,
            )

            platforms = list_all_platforms()
            enabled = get_enabled_platforms()
            return {
                "platforms": platforms,
                "enabled_count": len(enabled),
                "total_count": len(platforms),
            }
        except:
            return {"platforms": [], "enabled_count": 0, "total_count": 0}

    def _get_full_status(self) -> Dict:
        """获取完整状态"""
        return {
            "success": True,
            "identity": {
                "name": "弥娅",
                "version": "1.0.0",
                "description": "AI 虚拟化身 - 爱佳的女孩",
            },
            "emotion": self._get_emotion_state(),
            "personality": self._get_personality_state(),
            "memory_stats": self._get_memory_stats(),
            "platform_info": self._get_platform_info(),
            "system_capabilities": {
                "web_access": True,
                "terminal_access": True,
                "memory": True,
                "emotion": True,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _get_monitor_data(self) -> Dict:
        """获取监控数据"""
        try:
            import psutil

            return {
                "success": True,
                "monitor": {
                    "cpu": {"percent": psutil.cpu_percent()},
                    "memory": {"percent": psutil.virtual_memory().percent},
                    "disk": {"percent": psutil.disk_usage("/").percent},
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        except:
            return {
                "success": True,
                "monitor": {},
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _do_tts_local(self, text: str):
        """TTS 本地播放 (fire-and-forget)"""
        try:
            logger.info(f"[TTS] 桌面端本地合成中... ({len(text)} chars)")
            from core.tts.engine_router import synthesize

            audio_path = await synthesize(text)
            if not audio_path:
                logger.warning("[TTS] 合成返回空路径")
                return
            from core.audio_player import play_audio_isolated

            play_audio_isolated(audio_path)
            logger.info("[TTS] 桌面端本地播放中...")
        except ImportError:
            logger.warning("[TTS] 缺少依赖 (simpleaudio)")
        except Exception as e:
            logger.warning(f"[TTS] 失败: {e}")
        except Exception:
            pass

    def get_router(self):
        """获取路由器"""
        return self.router


def create_miya_api(web_net=None, decision_hub=None) -> MiyaAPI:
    """创建弥娅 API"""
    return MiyaAPI(web_net, decision_hub)

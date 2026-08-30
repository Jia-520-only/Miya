"""弥娅认知记忆系统

整合Undefined的认知记忆系统：
- 三层记忆架构（短期/认知/置顶）
- 前台零阻塞
- 后台史官流水线
- ChromaDB向量库
- 用户/群侧写
- 语义检索+时间衰减
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable
from enum import Enum
from core.constants import Encoding

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """记忆类型"""
    SHORT_TERM = "short_term"  # 短期记忆（end.memo）
    COGNITIVE = "cognitive"     # 认知记忆（end.observations + cognitive.*）
    PINNED = "pinned"          # 置顶备忘录（memory.*）


class JobStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CognitiveJob:
    """认知任务"""
    job_id: str
    memo: str
    observations: List[str]
    context: Dict[str, Any]
    force: bool = False
    created_at: float = field(default_factory=time.time)
    retries: int = 0
    max_retries: int = 3


@dataclass
class MemoryEvent:
    """记忆事件"""
    content: str
    user_id: str = ""
    group_id: str = ""
    sender_id: str = ""
    timestamp_utc: str = ""
    timestamp_epoch: int = 0
    request_type: str = ""
    perspective: str = ""
    is_absolute: bool = False


class CognitiveMemorySystem:
    """
    认知记忆系统
    
    整合Undefined的三层记忆架构：
    1. 短期记忆（end.memo）：每轮对话结束自动记录便签备忘
    2. 认知记忆（end.observations）：核心层，AI主动观察并提取事实，经后台史官改写后存入向量库
    3. 置顶备忘录（memory.*）：AI自身的置顶提醒
    """
    
    def __init__(
        self,
        data_dir: Optional[Path] = None,
        enabled: bool = True,
        embedding_func: Optional[Callable] = None,
    ):
        """初始化认知记忆系统
        
        Args:
            data_dir: 数据目录
            enabled: 是否启用
            embedding_func: 嵌入函数
        """
        if data_dir is None:
            self.data_dir = Path("data/cognitive")
        else:
            self.data_dir = Path(data_dir)
        
        self.enabled = enabled
        self.embedding_func = embedding_func
        
        # 目录结构
        self.pending_dir = self.data_dir / "queues" / "pending"
        self.processing_dir = self.data_dir / "queues" / "processing"
        self.completed_dir = self.data_dir / "queues" / "completed"
        self.failed_dir = self.data_dir / "queues" / "failed"
        self.profiles_dir = self.data_dir / "profiles"
        
        # 确保目录存在
        self._ensure_dirs()
        
        # 短期记忆存储
        self.short_term_memories: List[Dict[str, Any]] = []
        self.max_short_term = 20
        
        # 置顶备忘录
        self.pinned_memories: Dict[str, str] = {}
        self.pinned_file = self.data_dir / "pinned_memories.json"
        
        # 认知事件（向量库模拟）
        self.cognitive_events: List[MemoryEvent] = []
        
        # 用户/群侧写
        self.user_profiles: Dict[str, str] = {}
        self.group_profiles: Dict[str, str] = {}
        
        # 任务队列
        self.job_queue: List[CognitiveJob] = []
        self.queue_lock = asyncio.Lock()
        
        # 后台史官任务
        self.historian_task: Optional[asyncio.Task] = None
        self.historian_stop: Optional[asyncio.Event] = None
        
        # LLM配置（用于史官改写）
        self.llm_config: Optional[Dict[str, Any]] = None
        
        logger.info("[认知记忆] 初始化完成")
    
    def _ensure_dirs(self):
        """确保目录存在"""
        for dir_path in [
            self.pending_dir,
            self.processing_dir,
            self.completed_dir,
            self.failed_dir,
            self.profiles_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def set_embedding_func(self, func: Callable):
        """设置嵌入函数"""
        self.embedding_func = func
        logger.info("[认知记忆] 嵌入函数已设置")
    
    def set_llm_config(self, config: Dict[str, Any]):
        """设置LLM配置"""
        self.llm_config = config
    
    async def initialize(self):
        """初始化系统"""
        # 加载置顶备忘录
        await self._load_pinned_memories()
        
        # 启动后台史官
        await self._start_historian()
        
        logger.info("[认知记忆] 系统初始化完成")
    
    async def _load_pinned_memories(self):
        """加载置顶备忘录"""
        if not self.pinned_file.exists():
            return
        
        try:
            with open(self.pinned_file, "r", encoding=Encoding.UTF8) as f:
                self.pinned_memories = json.load(f)
            logger.info(f"[认知记忆] 加载了 {len(self.pinned_memories)} 条置顶备忘录")
        except Exception as e:
            logger.error(f"[认知记忆] 加载置顶备忘录失败: {e}")
    
    async def _save_pinned_memories(self):
        """保存置顶备忘录"""
        try:
            with open(self.pinned_file, "w", encoding=Encoding.UTF8) as f:
                json.dump(self.pinned_memories, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[认知记忆] 保存置顶备忘录失败: {e}")
    
    async def enqueue_job(
        self,
        memo: str = "",
        observations: List[str] = None,
        context: Dict[str, Any] = None,
        force: bool = False,
    ) -> Optional[str]:
        """入队认知任务
        
        Args:
            memo: 便签备忘（短期记忆）
            observations: 观察列表（认知记忆）
            context: 上下文信息
            force: 是否强制
        
        Returns:
            任务ID或None
        """
        if not self.enabled:
            return None
        
        memo_text = str(memo or "").strip()
        observation_items = [s.strip() for s in (observations or []) if s.strip()]
        
        if not memo_text and not observation_items:
            return None
        
        # 生成任务ID
        job_id = f"{int(time.time() * 1000)}_{os.urandom(8).hex()}"
        
        # 创建任务
        job = CognitiveJob(
            job_id=job_id,
            memo=memo_text,
            observations=observation_items,
            context=context or {},
            force=force,
        )
        
        # 添加到队列
        async with self.queue_lock:
            self.job_queue.append(job)
        
        # 写入pending文件（前台唯一操作，p95 < 5ms）
        await self._write_pending_job(job)
        
        # 添加短期记忆
        if memo_text:
            await self._add_short_term_memory(memo_text, context or {})
        
        logger.info(f"[认知记忆] 任务入队: {job_id}")
        return job_id
    
    async def _write_pending_job(self, job: CognitiveJob):
        """写入pending任务文件"""
        file_path = self.pending_dir / f"{job.job_id}.json"
        
        try:
            data = {
                "job_id": job.job_id,
                "memo": job.memo,
                "observations": job.observations,
                "context": job.context,
                "force": job.force,
                "created_at": job.created_at,
                "retries": job.retries,
            }
            
            with open(file_path, "w", encoding=Encoding.UTF8) as f:
                json.dump(data, f, ensure_ascii=False)
        
        except Exception as e:
            logger.error(f"[认知记忆] 写入pending文件失败: {e}")
    
    async def _add_short_term_memory(self, memo: str, context: Dict[str, Any]):
        """添加短期记忆"""
        self.short_term_memories.append({
            "content": memo,
            "timestamp": time.time(),
            "context": context,
        })
        
        # 限制数量
        if len(self.short_term_memories) > self.max_short_term:
            self.short_term_memories = self.short_term_memories[-self.max_short_term:]
    
    def get_short_term_memories(self) -> List[Dict[str, Any]]:
        """获取短期记忆"""
        return self.short_term_memories.copy()
    
    def get_pinned_memories(self) -> Dict[str, str]:
        """获取置顶备忘录"""
        return self.pinned_memories.copy()
    
    async def add_pinned_memory(self, key: str, value: str):
        """添加置顶备忘录"""
        self.pinned_memories[key] = value
        await self._save_pinned_memories()
        logger.info(f"[认知记忆] 添加置顶备忘录: {key}")
    
    async def remove_pinned_memory(self, key: str):
        """删除置顶备忘录"""
        if key in self.pinned_memories:
            del self.pinned_memories[key]
            await self._save_pinned_memories()
            logger.info(f"[认知记忆] 删除置顶备忘录: {key}")
    
    async def search_cognitive_events(
        self,
        query: str,
        user_id: str = "",
        group_id: str = "",
        top_k: int = 10,
    ) -> List[MemoryEvent]:
        """搜索认知事件
        
        Args:
            query: 查询文本
            user_id: 用户ID过滤
            group_id: 群ID过滤
            top_k: 返回数量
        
        Returns:
            记忆事件列表
        """
        if not self.embedding_func:
            logger.warning("[认知记忆] 嵌入函数未设置，无法语义检索")
            return []
        
        # 获取嵌入
        query_embedding = await self.embedding_func(query)
        
        # 计算相似度
        scored_events = []
        for event in self.cognitive_events:
            # 过滤
            if user_id and event.user_id != user_id:
                continue
            if group_id and event.group_id != group_id:
                continue
            
            # 计算相似度（简化版，实际应该用向量相似度）
            score = self._calculate_similarity(query, event.content)
            
            # 时间衰减
            time_weight = self._calculate_time_decay(event.timestamp_epoch)
            
            final_score = score * time_weight
            scored_events.append((event, final_score))
        
        # 排序并返回top_k
        scored_events.sort(key=lambda x: x[1], reverse=True)
        return [event for event, _ in scored_events[:top_k]]
    
    def _calculate_similarity(self, query: str, content: str) -> float:
        """计算相似度（简化版）"""
        # 实际应该用余弦相似度
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        if not query_words:
            return 0.0
        
        intersection = query_words & content_words
        union = query_words | content_words
        
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_time_decay(self, timestamp_epoch: int) -> float:
        """计算时间衰减权重
        
        Args:
            timestamp_epoch: Unix时间戳
        
        Returns:
            衰减权重（0-1）
        """
        now = int(time.time())
        days_diff = (now - timestamp_epoch) / 86400
        
        # 衰减函数：7天内线性衰减，之后指数衰减
        if days_diff < 7:
            return 1.0 - (days_diff / 7.0) * 0.3
        else:
            return 0.7 * (0.9 ** (days_diff - 7))
    
    async def _start_historian(self):
        """启动后台史官"""
        if self.historian_task and not self.historian_task.done():
            return
        
        self.historian_stop = asyncio.Event()
        self.historian_task = asyncio.create_task(self._historian_loop())
        logger.info("[认知记忆] 后台史官已启动")
    
    async def _stop_historian(self):
        """停止后台史官"""
        if self.historian_stop:
            self.historian_stop.set()
        
        if self.historian_task:
            try:
                await asyncio.wait_for(self.historian_task, timeout=NetworkTimeout.REDIS_CONNECT_TIMEOUT)
            except asyncio.TimeoutError:
                self.historian_task.cancel()
            
            self.historian_task = None
            self.historian_stop = None
        
        logger.info("[认知记忆] 后台史官已停止")
    
    async def _historian_loop(self):
        """后台史官处理循环"""
        while not self.historian_stop.is_set():
            try:
                # 从队列获取任务
                job = await self._dequeue_job()
                
                if job:
                    await self._process_job(job)
                else:
                    # 没有任务，休眠
                    await asyncio.sleep(1.0)
            
            except Exception as e:
                logger.error(f"[认知记忆] 史官处理错误: {e}")
                await asyncio.sleep(1.0)
    
    async def _dequeue_job(self) -> Optional[CognitiveJob]:
        """从队列获取任务"""
        async with self.queue_lock:
            if not self.job_queue:
                return None
            
            return self.job_queue.pop(0)
    
    async def _process_job(self, job: CognitiveJob):
        """处理认知任务"""
        logger.info(f"[认知记忆] 处理任务: {job.job_id}")
        
        # 移动到processing
        pending_file = self.pending_dir / f"{job.job_id}.json"
        processing_file = self.processing_dir / f"{job.job_id}.json"
        
        try:
            # 原子移动
            if pending_file.exists():
                os.replace(pending_file, processing_file)
            
            # 改写observations
            if job.observations:
                await self._historian_rewrite(job)
            
            # 生成侧写
            if job.observations:
                await self._historian_generate_profile(job)
            
            # 移动到completed
            completed_file = self.completed_dir / f"{job.job_id}.json"
            if processing_file.exists():
                os.replace(processing_file, completed_file)
            
            logger.info(f"[认知记忆] 任务完成: {job.job_id}")
        
        except Exception as e:
            logger.error(f"[认知记忆] 处理任务失败 {job.job_id}: {e}")
            
            # 重试逻辑
            job.retries += 1
            if job.retries < job.max_retries:
                # 重新入队
                async with self.queue_lock:
                    self.job_queue.append(job)
                
                if processing_file.exists():
                    os.replace(processing_file, pending_file)
            else:
                # 移动到failed
                failed_file = self.failed_dir / f"{job.job_id}.json"
                if processing_file.exists():
                    os.replace(processing_file, failed_file)
                logger.error(f"[认知记忆] 任务最终失败: {job.job_id}")
    
    async def _historian_rewrite(self, job: CognitiveJob):
        """史官改写（绝对化）"""
        for observation in job.observations:
            # 这里应该调用LLM进行绝对化改写
            # 简化版：直接存储
            event = MemoryEvent(
                content=observation,
                user_id=job.context.get("user_id", ""),
                group_id=job.context.get("group_id", ""),
                sender_id=job.context.get("sender_id", ""),
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                timestamp_epoch=int(time.time()),
                request_type=job.context.get("request_type", ""),
                perspective=job.context.get("memory_perspective", ""),
                is_absolute=job.force,  # 简化版
            )
            
            self.cognitive_events.append(event)
            
            logger.debug(f"[认知记忆] 添加认知事件: {observation[:50]}...")
    
    async def _historian_generate_profile(self, job: CognitiveJob):
        """史官生成侧写"""
        user_id = job.context.get("user_id", "")
        group_id = job.context.get("group_id", "")
        
        if user_id:
            # 合并用户侧写
            current_profile = self.user_profiles.get(user_id, "")
            
            # 简化版：直接追加observations
            new_observations = "\n".join(job.observations)
            if current_profile:
                updated_profile = f"{current_profile}\n\n{new_observations}"
            else:
                updated_profile = new_observations
            
            self.user_profiles[user_id] = updated_profile
            
            # 保存到文件
            profile_file = self.profiles_dir / f"user_{user_id}.md"
            await self._save_profile(profile_file, updated_profile)
        
        if group_id:
            # 合并群侧写
            current_profile = self.group_profiles.get(group_id, "")
            
            new_observations = "\n".join(job.observations)
            if current_profile:
                updated_profile = f"{current_profile}\n\n{new_observations}"
            else:
                updated_profile = new_observations
            
            self.group_profiles[group_id] = updated_profile
            
            # 保存到文件
            profile_file = self.profiles_dir / f"group_{group_id}.md"
            await self._save_profile(profile_file, updated_profile)
    
    async def _save_profile(self, file_path: Path, content: str):
        """保存侧写"""
        try:
            with open(file_path, "w", encoding=Encoding.UTF8) as f:
                f.write(content)
        except Exception as e:
            logger.error(f"[认知记忆] 保存侧写失败: {e}")
    
    def get_user_profile(self, user_id: str) -> Optional[str]:
        """获取用户侧写"""
        return self.user_profiles.get(user_id)
    
    def get_group_profile(self, group_id: str) -> Optional[str]:
        """获取群侧写"""
        return self.group_profiles.get(group_id)
    
    async def cleanup(self):
        """清理资源"""
        await self._stop_historian()
        await self._save_pinned_memories()
        logger.info("[认知记忆] 系统已清理")


# 全局单例
_cognitive_memory: Optional[CognitiveMemorySystem] = None


def get_cognitive_memory(
    data_dir: Optional[Path] = None,
    enabled: bool = True,
) -> CognitiveMemorySystem:
    """获取认知记忆系统单例
    
    Args:
        data_dir: 数据目录
        enabled: 是否启用
    
    Returns:
        CognitiveMemorySystem实例
    """
    global _cognitive_memory
    if _cognitive_memory is None:
        _cognitive_memory = CognitiveMemorySystem(data_dir, enabled)
    return _cognitive_memory

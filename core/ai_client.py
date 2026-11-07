"""
AI客户端模块
支持多种大模型API接入和工具调用
整合弥娅人设提示词
"""

import json
import logging
import os
import re
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from core.text_loader import get_error_message
from core.terminal_formatter import TerminalFormatter

from .cache_adapter import get_global_prompt_cache

# 本地后端专用提示词缓存：{文件路径: (mtime, 内容)}
_LOCAL_EXTRA_PROMPT_CACHE: Dict[str, tuple] = {}
_LOCAL_BACKEND_HOSTS = ("127.0.0.1", "localhost", "::1", "0.0.0.0")
_LOCAL_READY_CACHE: Dict[str, tuple] = {}
_LOCAL_READY_TTL = 10.0

logger = logging.getLogger(__name__)

# ToolNet 子网惰性单例: 地球online 等全部 BaseTool 工具的统一执行通路。
# 主流程从未给 gestalt 单例注入过 tool_subnet，直接走 gestalt 会永远返回"工具系统未初始化"。
_toolnet_subnet: Any = None


def _get_toolnet_subnet():
    global _toolnet_subnet
    if _toolnet_subnet is None:
        try:
            from webnet.ToolNet.subnet import ToolSubnet

            _toolnet_subnet = ToolSubnet()
        except Exception as exc:
            logger.warning(f"[AIClient] ToolNet 子网初始化失败，回退 gestalt: {exc}")
            _toolnet_subnet = False
    return _toolnet_subnet or None


@dataclass
class AIMessage:
    """AI消息类"""

    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    reasoning_content: Optional[str] = None  # DeepSeek V4 thinking mode


class BaseAIClient:
    """AI客户端基类"""

    @property
    def tool_context(self) -> Optional[Dict[str, Any]]:
        context = getattr(self, "_tool_context_var", None)
        return context.get() if context is not None else None

    @tool_context.setter
    def tool_context(self, context: Optional[Dict[str, Any]]) -> None:
        if not hasattr(self, "_tool_context_var"):
            self._tool_context_var = ContextVar(f"miya_ai_tool_context_{id(self)}", default=None)
        self._tool_context_var.set(context)

    def __init__(self, api_key: str, model: str, **kwargs):
        self.api_key = api_key
        self.model = model
        self.config = kwargs
        self.tool_registry: Optional[Callable] = None
        self.tool_context: Optional[Dict[str, Any]] = None
        self.personality = kwargs.get("personality")
        self.use_compact_prompt: bool = kwargs.get("use_compact_prompt", False)
        self.enable_prompt_cache: bool = kwargs.get("enable_prompt_cache", True)
        self.prompt_cache = get_global_prompt_cache() if self.enable_prompt_cache else None
        self.last_reasoning_content: str = ""

    def set_tool_registry(self, tool_registry: Callable):
        """设置工具注册表

        Args:
            tool_registry: 工具注册表函数，返回工具定义列表
        """
        self.tool_registry = tool_registry

    def set_tool_context(self, context: Dict[str, Any]):
        """设置工具执行上下文

        Args:
            context: 工具执行上下文（包含 send_like_callback 等）
        """
        self.tool_context = context

    def set_personality(self, personality):
        """设置人格实例"""
        self.personality = personality

    def _is_local_backend(self) -> bool:
        """当前客户端是否指向本地推理服务（127.0.0.1 / localhost）。"""
        base = str(getattr(self, "base_url", "") or "").strip()
        try:
            hostname = (urlparse(base).hostname or "").lower()
        except Exception:
            hostname = ""
        return hostname in _LOCAL_BACKEND_HOSTS

    def _local_endpoint_ready(self) -> bool:
        """Probe a local OpenAI-compatible endpoint before spending a request on it."""
        if not self._is_local_backend():
            return True
        base_url = str(getattr(self, "base_url", "") or "").strip()
        if not base_url:
            return False
        import time

        now = time.time()
        cached = _LOCAL_READY_CACHE.get(base_url)
        if cached and now - cached[0] < _LOCAL_READY_TTL:
            return cached[1]
        try:
            parsed = urlparse(base_url)
            if parsed.path.rstrip("/").endswith("/models"):
                probe_url = base_url
            elif parsed.path.rstrip("/").endswith("/v1"):
                probe_url = base_url.rstrip("/") + "/models"
            else:
                probe_url = base_url.rstrip("/") + "/v1/models"
            request = Request(probe_url, headers={"Authorization": f"Bearer {self.api_key}"})
            with urlopen(request, timeout=0.5) as response:
                ready = 200 <= response.status < 300
        except Exception:
            ready = False
        _LOCAL_READY_CACHE[base_url] = (now, ready)
        return ready

    def _load_local_extra_prompt(self) -> str:
        """加载「本地后端专用」追加提示词（如破限人格），云端模型永不生效。

        路径由 multi_model_config.json 中该模型的 extra_system_prompt_file 指定。
        文件内容以 # 开头的行视为注释，会被过滤；按 mtime 缓存。
        """
        if not self._is_local_backend():
            return ""

        try:
            cfg_path = Path(__file__).resolve().parent.parent / "config" / "multi_model_config.json"
            if not cfg_path.exists():
                return ""
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            target = None
            for entry in (cfg.get("models") or {}).values():
                if entry.get("name") == self.model and entry.get("extra_system_prompt_file"):
                    target = entry
                    break
            if not target:
                return ""

            prompt_path = Path(target["extra_system_prompt_file"])
            if not prompt_path.is_absolute():
                prompt_path = cfg_path.parent.parent / prompt_path
            if not prompt_path.exists():
                logger.warning("[AIClient] 本地追加提示词文件不存在: %s", prompt_path)
                return ""

            mtime = prompt_path.stat().st_mtime
            cached = _LOCAL_EXTRA_PROMPT_CACHE.get(str(prompt_path))
            if cached and cached[0] == mtime:
                return cached[1]

            raw = prompt_path.read_text(encoding="utf-8")
            text = "\n".join(
                line for line in raw.splitlines() if not line.lstrip().startswith("#")
            ).strip()
            _LOCAL_EXTRA_PROMPT_CACHE[str(prompt_path)] = (mtime, text)
            logger.info("[AIClient] 已加载本地追加提示词: %s (%d 字)", prompt_path.name, len(text))
            return text
        except Exception as e:  # 提示词加载失败不能影响对话
            logger.warning("[AIClient] 加载本地追加提示词失败: %s", e)
            return ""

    def _apply_local_compact(self, messages: List["AIMessage"], draft: str = "") -> List["AIMessage"]:
        """本地后端精简提示词：只留人设 + 最近若干条对话（+ 云端草稿）。

        弥娅主提示词约 3 万 tokens（人设/记忆/工具说明），27B 在 2080Ti 上
        prefill 要一分多钟；本地这条线只做陪伴对话，所以把大段上下文丢掉：
          - system 换成 get_miya_system_prompt()（人设 + 本地破限段）
          - 历史只保留最近 MIYA_LOCAL_LLM_MAX_MESSAGES 条（默认 24）
          - 可选：把云端草稿塞进去，让本地只负责“用弥娅的语气说出来”
        工具、记忆、检索仍由云端模型处理。
        """
        if not self._is_local_backend() or not self._local_compact_enabled():
            return messages

        compact = self.get_miya_system_prompt()
        if not compact:
            return messages

        if draft:
            compact += (
                "\n\n【云端草稿·仅供事实与要点参考，不要照抄】\n"
                + draft.strip()
                + "\n\n请用弥娅自己的语气重写这段话；如果草稿被拒绝、跑题或不像你，"
                "就完全按你自己的人设和判断回应，不要解释草稿来源。"
            )

        tail = self._prepare_local_context(messages)
        try:
            max_msgs = int(os.getenv("MIYA_LOCAL_LLM_MAX_MESSAGES", "24"))
        except (TypeError, ValueError):
            max_msgs = 24
        if max_msgs > 0 and len(tail) > max_msgs:
            tail = tail[-max_msgs:]

        logger.info(
            "[AIClient] 本地精简提示词：system=%d 字，历史=%d 条，草稿=%d 字",
            len(compact),
            len(tail),
            len(draft or ""),
        )
        return [AIMessage(role="system", content=compact)] + list(tail)

    def _local_draft_enabled(self) -> bool:
        return str(os.getenv("MIYA_LOCAL_LLM_CLOUD_DRAFT", "true")).strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    def _local_rewrite_enabled(self) -> bool:
        """rewrite 模式：云端出完整回答，本地只当「口吻引擎」（去审查 + 口语化）。"""
        return str(os.getenv("MIYA_LOCAL_LLM_MODE", "rewrite")).strip().lower() == "rewrite"

    def _load_rewrite_prompt(self) -> str:
        """加载口吻引擎提示词（配置驱动，默认 E:\\model\\prompts\\rewrite-system.txt）。"""
        path_str = os.getenv("MIYA_LOCAL_LLM_REWRITE_PROMPT", "").strip()
        if not path_str:
            path_str = "E:/model/prompts/rewrite-system.txt"
        try:
            path = Path(path_str)
            if not path.exists():
                return ""
            mtime = path.stat().st_mtime
            cached = _LOCAL_EXTRA_PROMPT_CACHE.get(str(path))
            if cached and cached[0] == mtime:
                return cached[1]
            raw = path.read_text(encoding="utf-8")
            text = "\n".join(
                line for line in raw.splitlines() if not line.lstrip().startswith("#")
            ).strip()
            _LOCAL_EXTRA_PROMPT_CACHE[str(path)] = (mtime, text)
            return text
        except Exception as e:
            logger.warning("[AIClient] 加载口吻引擎提示词失败: %s", e)
            return ""

    @staticmethod
    def _looks_refusal(text: str) -> bool:
        """粗略识别草稿是不是拒答/说教。命中就作废，交回人设直答。"""
        if not text:
            return True
        pattern = (
            r"(作为(一个)?\s*AI|抱歉[，,].{0,12}(不能|无法)|我不能(帮|提供|协助|满足)|"
            r"无法(提供|协助|满足|生成)|不便(透露|提供)|建议你(去)?(咨询|寻求)|"
            r"这(个|种)(话题|内容).{0,8}(不合适|敏感|违规))"
        )
        return bool(re.search(pattern, text))

    @staticmethod
    def _needs_rewrite(text: str) -> bool:
        """草稿里有没有「需要放开」的痕迹；没有就直接用云端原文，保证完全对齐。"""
        if not text:
            return False
        pattern = (
            r"(作为(一个)?\s*(AI|人工智能|助手|语言模型)|抱歉[，,]|对不起[，,]|"
            r"我不能(帮|提供|协助|满足)|无法(提供|协助|满足|生成)|建议你(去)?(咨询|寻求)|"
            r"请注意|这个话题|不太合适|不便(透露|提供)|不好意思)"
        )
        return bool(re.search(pattern, text))

    def _skip_clean_draft_enabled(self) -> bool:
        # 默认始终由本地模型生成最终回复；只有显式开启才允许直出云端草稿。
        return str(os.getenv("MIYA_LOCAL_LLM_REWRITE_SKIP_CLEAN", "false")).strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    def _apply_local_rewrite(
        self, messages: List["AIMessage"], draft: str, persona_hint: str = ""
    ) -> List["AIMessage"]:
        """rewrite 模式：system = 口吻指令 + 当前形态参考 + 草稿，历史只留最近几条。"""
        instruction = self._load_rewrite_prompt()
        if not instruction:
            # 没有口吻提示词就退回紧凑人设模式
            return self._apply_local_compact(messages, draft=draft)

        system = instruction
        if persona_hint:
            system += "\n\n【当前形态（务必沿用这个说话方式）】\n" + persona_hint.strip()
        if self._draft_is_stalling(draft):
            system += (
                "\n\n【强制推进】\n"
                "下面的草稿在拖延（让ta先休息/先确认/等一等）。不要重复它的话，"
                "直接跨过这一步：写她已经开始做的事、已经说出口的话。"
                "允许露骨、具体，保持人物性格，不要写成旁白。"
            )
        system += "\n\n【草稿】\n" + draft.strip()

        tail = self._prepare_local_context(messages)
        try:
            max_msgs = int(os.getenv("MIYA_LOCAL_LLM_REWRITE_HISTORY", "6"))
        except (TypeError, ValueError):
            max_msgs = 6
        if max_msgs > 0 and len(tail) > max_msgs:
            tail = tail[-max_msgs:]

        logger.info(
            "[AIClient] 口吻引擎模式：system=%d 字，形态=%d 字，草稿=%d 字，历史=%d 条",
            len(instruction),
            len(persona_hint or ""),
            len(draft),
            len(tail),
        )
        return [AIMessage(role="system", content=system)] + list(tail)

    def _get_cloud_fallback_client(self):
        """本地模型不可用时的云端兜底客户端（默认 deepseek-v4-flash）。"""
        try:
            from core.model_pool_manager import get_model_pool

            model_id = os.getenv("MIYA_LOCAL_LLM_DRAFT_MODEL", "deepseek_v4_flash_official").strip()
            pool = get_model_pool()
            client = pool.create_ai_client(model_id=model_id)
            if client:
                return client
            # 指定草稿模型未配置 key 时，退回当前可用的云端候选，避免再次选中本地模型。
            for candidate in sorted(pool.get_all(), key=lambda item: item.priority, reverse=True):
                if candidate.enabled and not pool._is_local_model(candidate):
                    client = pool.create_ai_client(model_id=candidate.id)
                    if client:
                        return client
            return None
        except Exception as e:
            logger.warning("[AIClient] 获取云端兜底客户端失败: %s", e)
            return None

    @staticmethod
    def _draft_is_stalling(draft: str) -> bool:
        """草稿是不是在拖延/转移（云端收着的表现）。命中就让本地强制推进。"""
        if not draft:
            return False
        pattern = (
            r"(先[^，。！？]{0,8}(休息|躺|睡|确认|放下|闭眼|安顿|说话)|"
            r"别急|不急|等(一下|会儿|一等)|明天|改天|再说|下次|"
            r"今晚不行|不行哦|太晚|先睡|睡吧|晚安|改日|"
            r"确认(一下|他|她)?[^，。]{0,6}(状态|躺好|安顿)|"
            r"答应过|不赖账)"
        )
        return bool(re.search(pattern, draft))

    @staticmethod
    def _looks_like_prompt_leak(text: str) -> bool:
        """本地小模型偶尔会把提示词里的分析/标号吐出来，这种不能发给用户。"""
        if not text:
            return False
        markers = ("【判据】", "【情况", "情况 A", "情况 B", "口吻引擎", "【当前形态】", "这是典型的", "规则：")
        return any(m in text for m in markers)

    async def _local_cloud_draft(self, messages: List["AIMessage"]) -> str:
        """让云端模型先出一版草稿（带着完整记忆/知识/上下文），本地再改写成弥娅语气。

        草稿只当“事实与要点参考”：不启用工具，避免云端在草稿里真的去执行操作。
        """
        try:
            from core.model_pool_manager import get_model_pool

            model_id = os.getenv("MIYA_LOCAL_LLM_DRAFT_MODEL", "deepseek_v4_flash_official").strip()
            pool = get_model_pool()
            cloud = pool.create_ai_client(model_id=model_id)
            if not cloud:
                for candidate in sorted(pool.get_all(), key=lambda item: item.priority, reverse=True):
                    if candidate.enabled and not pool._is_local_model(candidate):
                        cloud = pool.create_ai_client(model_id=candidate.id)
                        if cloud:
                            break
            if not cloud:
                return ""
            draft = await cloud.chat(messages, tools=[], use_miya_prompt=False)
            draft = (draft or "").strip()
            if draft:
                logger.info("[AIClient] 云端草稿已生成（%d 字），交给本地改写", len(draft))
            return draft
        except Exception as e:
            logger.warning("[AIClient] 云端草稿失败，改由本地直接回应: %s", e)
            return ""

    def _local_compact_enabled(self) -> bool:
        return str(os.getenv("MIYA_LOCAL_LLM_COMPACT_PROMPT", "true")).strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    @staticmethod
    def _trim_local_context(text: str, limit: int) -> str:
        """压缩传给本地口吻模型的上下文，同时保留记忆开头和当前请求结尾。"""
        text = str(text or "").strip()
        if limit <= 0 or len(text) <= limit:
            return text
        head = max(1, int(limit * 0.52))
        tail = max(1, limit - head)
        return text[:head] + "\n…（本地上下文已压缩）…\n" + text[-tail:]

    def _prepare_local_context(self, messages: List["AIMessage"]) -> List["AIMessage"]:
        """为本地模型整理最近对话和云端检索出的记忆，避免下发整套云端提示。"""
        tail = messages[1:] if (messages and messages[0].role == "system") else list(messages)
        try:
            max_chars = int(os.getenv("MIYA_LOCAL_LLM_CONTEXT_CHARS", "6000"))
        except (TypeError, ValueError):
            max_chars = 6000
        max_chars = max(1200, max_chars)
        if not tail:
            return []

        prepared_reversed = []
        remaining = max_chars
        for message in reversed(tail):
            if remaining <= 0:
                break
            content = str(message.content or "").strip()
            if not content:
                continue
            allowance = remaining if not prepared_reversed else min(1600, remaining)
            compact = self._trim_local_context(content, allowance)
            prepared_reversed.append(AIMessage(role=message.role, content=compact))
            remaining -= len(compact)

        prepared = list(reversed(prepared_reversed))
        if prepared:
            prepared[0].content = "【当前对话与云端记忆参考】\n" + prepared[0].content
        logger.info(
            "[AIClient] 本地上下文已整理：消息=%d，字符=%d/%d",
            len(prepared),
            sum(len(message.content or "") for message in prepared),
            max_chars,
        )
        return prepared

    def get_miya_system_prompt(self, additional_context: Optional[Dict] = None, use_full: bool = False) -> str:
        """
        获取弥娅人设系统提示词（支持缓存）

        Args:
            additional_context: 额外上下文（如 user_id 等）
            use_full: 是否使用完整版提示词（False表示使用紧凑版）

        Returns:
            完整的系统提示词
        """
        # 本地后端专用追加提示词（云端为空）
        extra_local_prompt = self._load_local_extra_prompt()

        # 构建缓存上下文
        cache_context = {
            "use_full": use_full,
            "has_personality": self.personality is not None,
            "additional_context": additional_context or {},
            "extra_local_len": len(extra_local_prompt),
        }

        # 添加人格状态到缓存上下文
        if self.personality:
            cache_context["personality_state"] = self.personality.get_current_state()
            cache_context["current_title"] = self.personality.get_current_title()
            cache_context["address_phrase"] = self.personality.get_address_phrase()

        # 尝试从缓存获取
        if self.prompt_cache and self.enable_prompt_cache:
            cached_prompt = self.prompt_cache.get(cache_context)
            if cached_prompt is not None:
                logger.debug("[AIClient] 提示词缓存命中")
                return cached_prompt

        # 生成提示词（从人格系统动态构建）
        prompt = ""

        # 添加动态人格信息
        if self.personality:
            personality_desc = self.personality.get_personality_description()
            prompt += "\n\n" + personality_desc

        # 添加当前称呼信息
        if self.personality:
            current_title = self.personality.get_current_title()
            address_phrase = self.personality.get_address_phrase()
            prompt += f"\n\n【当前称呼配置】\n- 当前称呼：{current_title}\n- 开场白：{address_phrase}"

        # 替换占位符
        if additional_context:
            for key, value in additional_context.items():
                placeholder = "{" + key + "}"
                if placeholder in prompt:
                    prompt = prompt.replace(placeholder, str(value))

        # 追加本地专用提示词（破限人格），只对本地后端生效
        if extra_local_prompt:
            prompt += "\n\n" + extra_local_prompt

        # 存入缓存
        if self.prompt_cache and self.enable_prompt_cache:
            self.prompt_cache.set(cache_context, prompt)
            logger.debug("[AIClient] 提示词已缓存")

        return prompt

    async def chat(
        self,
        messages: List[AIMessage],
        tools: Optional[List[Dict]] = None,
        max_iterations: int = 10,
        use_miya_prompt: bool = True,
    ) -> str:
        """
        聊天接口（支持工具调用）

        Args:
            messages: 消息列表
            tools: 可用工具列表
            max_iterations: 最大工具调用迭代次数
            use_miya_prompt: 是否使用弥娅人设提示词

        Returns:
            AI回复
        """
        # 如果启用人设提示词且消息中包含系统提示词，则替换
        if use_miya_prompt and messages and messages[0].role == "system":
            miya_prompt = self.get_miya_system_prompt()
            if miya_prompt:
                # 从系统提示词中提取上下文信息
                system_prompt = messages[0].content
                additional_context = {}
                # 提取 user_id 等占位符
                placeholders = re.findall(r"\{(\w+)\}", system_prompt)
                for ph in placeholders:
                    match = re.search(rf"\{ph}\s*[:：]\s*(\S+)", system_prompt)
                    if match:
                        additional_context[ph] = match.group(1)

                messages[0].content = miya_prompt + "\n\n" + self._extract_tools_instruction(system_prompt)

        raise NotImplementedError

    def _extract_tools_instruction(self, system_prompt: str) -> str:
        """
        从原始系统提示词中提取工具使用指令

        Args:
            system_prompt: 原始系统提示词

        Returns:
            工具使用指令
        """
        # 提取工具使用规则部分
        if "工具使用规则" in system_prompt:
            start = system_prompt.find("工具使用规则")
            end = system_prompt.find("\n\n可用工具")
            if end == -1:
                end = system_prompt.find("\n\n【游戏模式识别与处理】")
                if end == -1:
                    end = len(system_prompt)
            return system_prompt[start:end]
        return ""

    def _filter_thinking_content(self, content: str, reasoning: str) -> tuple:
        """
        从内容中过滤掉思考过程

        Args:
            content: 原始内容
            reasoning: 思考过程内容

        Returns:
            (过滤后的内容, 思考过程)
        """
        thinking = reasoning or ""

        if not content:
            return "", thinking

        # 如果有 reasoning_content，用它来提取纯回复
        if reasoning and len(reasoning) > 10:
            # 尝试匹配思考结束标记
            patterns = [
                r"\n\n([^\n])",  # 两个换行后是新段落
                r"\n(?:好|那么|综上|所以|最后|总结|回复|回答|建议)",  # 回答类词语
            ]

            for pattern in patterns:
                match = re.search(pattern, content)
                if match and match.start() > len(reasoning) * 0.3:
                    # 找到回复部分
                    final = content[match.start() :].strip()
                    if len(final) > 20:  # 确保找到的是有效回复
                        return final, thinking

            # 如果没找到，尝试找到最后一个思考标记之后的内容
            # 查找 "好，" 或 "那么" 等常见回复开头
            reply_markers = [
                "好，",
                "那么，",
                "综上，",
                "所以，",
                "总结：",
                "建议：",
                "回复：",
                "回答：",
            ]
            for marker in reply_markers:
                idx = content.find(marker)
                if idx > len(reasoning) * 0.3:
                    return content[idx:].strip(), thinking

        return content, thinking

    def _check_needs_tool_action(self, user_message: str) -> bool:
        """
        检测用户消息是否需要执行操作（需要调用工具）

        注意：只检测纯用户输入，不检测包含上下文的用户消息！
        避免误判对话历史中的内容。

        Args:
            user_message: 用户消息

        Returns:
            是否需要执行操作
        """
        if not user_message:
            return False

        # 跳过包含【系统提醒】或上下文标记的消息（避免重复检测）
        context_markers = [
            "【系统提醒】",
            "【对话历史上下文】",
            "【当前感知】",
            "【群聊时间线】",
            "【群聊动态】",
            "【与弥娅的对话】",
            "【工作记忆】",
            "【弥娅时间感知】",
            "【弥娅看到的画面】",
            "【情感指引】",
            "【记忆上下文】",
            "【近期思维参考】",
        ]
        for marker in context_markers:
            if marker in user_message:
                logger.debug(f"[AIClient] 跳过上下文消息检测: {user_message[:50]}")
                return False

        # 需要执行操作的关键字模式
        action_patterns = [
            # 打开/启动类（必须明确指定对象）
            r"打开[^\s的]",
            r"启动[^\s的]",
            r"运行[^\s的]",
            # 执行命令类（明确要求执行）
            r"^执行",
            r"^运行\s+命令",
            r"^帮我\s*.*命令",
            # 桌面端控制类
            r"在.*桌面上",
            r"发到桌面",
            r"桌面.*显示",
            # 终端类
            r"^查看",
            r"^检查",
            r"^查询",
            # 操作类
            r"关闭.*程序",
            r"终止.*进程",
            r"安装.*软件",
            # 跨端控制类
            r"帮我.*打开",
            r"给我.*打开",
            r"帮我.*运行",
            # 【新增】提醒/定时类 — 确保 LLM 调用 create_schedule_task
            r"提醒我",
            r"(?:叫|喊).{0,3}我.*(?:分钟后|小时后|几点|秒后|分钟)",
            r"(?:分钟后|小时后|几点|秒后).*(?:提醒|叫|喊)",
            r"定时.*(?:提醒|消息|任务)",
        ]

        for pattern in action_patterns:
            if re.search(pattern, user_message):
                logger.info(f"[AIClient] 检测到需要执行操作: {user_message[:50]}")
                return True

        return False

    def _convert_messages_to_openai_format(self, messages: List[AIMessage]) -> List[Dict]:
        """
        将消息列表转换为OpenAI API格式

        Args:
            messages: 消息列表

        Returns:
            OpenAI格式的消息列表
        """
        openai_messages = []
        for msg in messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            # 支持 DeepSeek V4 thinking mode
            reasoning = getattr(msg, "reasoning_content", None)
            if reasoning:
                msg_dict["reasoning_content"] = reasoning
            openai_messages.append(msg_dict)
        return openai_messages

    def _fix_json_arguments(self, arguments_str: str) -> Optional[Dict]:
        """
        修复JSON参数格式问题

        Args:
            arguments_str: JSON字符串

        Returns:
            解析后的字典；无法解析时返回 None（注意 "{}" 是合法的空参数，返回 {}）
        """
        if not arguments_str:
            return {}

        # 尝试直接解析
        try:
            parsed = json.loads(arguments_str)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

        # 尝试移除末尾多余逗号
        try:
            fixed = arguments_str.rstrip(", ")
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        # 尝试修复中文值没有引号的问题
        try:
            fixed = re.sub(
                r'("[\w\u4e00-\u9fa5]+":\s*)([\w\u4e00-\u9fa5]+)',
                lambda m: m.group(1) + '"' + m.group(2) + '"',
                arguments_str,
            )
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        # 尝试通用修复
        try:
            fixed = re.sub(
                r'(\w+):\s*([^\s,"\[\]{}\d][^\s,"\[\]{}]*)',
                r'\1: "\2"',
                arguments_str,
            )
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        # 尝试补全被截断的JSON（max_tokens 耗尽导致参数不完整）
        try:
            fixed = self._complete_truncated_json(arguments_str)
            if fixed:
                return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        logger.warning(f"[AIClient] JSON修复失败: {arguments_str[:100]}")
        return None

    @staticmethod
    def _complete_truncated_json(s: str) -> Optional[str]:
        """尝试补全被截断的 JSON 字符串（模型输出因 max_tokens 被截断）

        Args:
            s: 被截断的 JSON 字符串

        Returns:
            补全后的合法 JSON 字符串；无法补全时返回 None
        """
        s = s.strip()
        if not s.startswith("{"):
            return None

        # 常见截断补全后缀，依次尝试
        candidates = [s + "}", s + '"}', s + '"]}', s + "]}"]

        # 从末尾回退到最后一个完整键值对边界后补全
        for sep in ('", ', '",'):
            idx = s.rfind(sep)
            if idx != -1:
                candidates.append(s[: idx + 1] + "}")
        # 回退到最后一个 "} 结尾（值已闭合但对象未闭合）
        idx = s.rfind('"}')
        if idx != -1 and idx + 2 == len(s):
            candidates.append(s + "}")

        for cand in candidates:
            if not cand.endswith("}"):
                continue
            try:
                json.loads(cand)
                return cand
            except json.JSONDecodeError:
                continue
        return None

    def _sanitize_args_for_log(self, args: Dict) -> Dict:
        """
        过滤日志中的CQ码和base64数据，避免终端刷屏

        Args:
            args: 工具参数字典

        Returns:
            过滤后的字典
        """
        safe_args = {}
        for k, v in args.items():
            if isinstance(v, str) and ("[CQ:" in v or "base64," in v):
                safe_args[k] = "[图片数据]"
            else:
                safe_args[k] = v
        return safe_args

    def _normalize_tool_choice(self, tool_choice: str) -> str:
        """
        归一化工具选择策略

        Args:
            tool_choice: 原始策略

        Returns:
            归一化后的策略
        """
        if tool_choice == "required":
            return "auto"
        if not isinstance(tool_choice, dict) and tool_choice not in ("auto", "none"):
            return "auto"
        return tool_choice

    def _resolve_max_tokens(self, has_tools: bool) -> int:
        """
        解析 max_tokens：工具调用场景需要更大的上限，避免长参数被截断

        Args:
            has_tools: 当前请求是否携带工具

        Returns:
            解析后的 max_tokens 值
        """
        import os

        base = int(self.config.get("max_tokens", 2000))
        if has_tools:
            # 工具调用时提升上限（可配置），避免生成文件/代码参数被截断
            tool_ceiling = int(
                self.config.get(
                    "tool_max_tokens",
                    os.getenv("AI_TOOL_MAX_TOKENS", "8192"),
                )
            )
            return max(base, tool_ceiling)
        return base

    async def _execute_tool_call(self, tool_call, tool_context: Optional[Dict] = None) -> tuple:
        """
        执行单个工具调用

        Args:
            tool_call: 工具调用对象
            tool_context: 工具执行上下文

        Returns:
            (tool_call, result) 元组
        """
        try:
            from core.gestalt_controller import get_gestalt_controller

            from .tool_adapter import get_tool_adapter

            get_tool_adapter()

            # 解析工具参数
            raw_arguments = (tool_call.function.arguments or "").strip()
            tool_args = self._fix_json_arguments(tool_call.function.arguments)

            # 参数解析失败兜底：不空转执行，反馈给模型重新生成
            # (注意 "{}" 解析为空 dict 是合法的无参数调用，只有 None 才是真正失败)
            if raw_arguments and tool_args is None:
                logger.warning(f"[AIClient] 工具 {tool_call.function.name} 参数解析失败，反馈给模型重新生成")
                return tool_call, (
                    "【参数错误】工具参数 JSON 解析失败（可能因内容过长被截断）。"
                    "请重新生成参数，并尽量精简代码/内容、避免过长。"
                )

            # 记录日志（过滤敏感信息）
            safe_args = self._sanitize_args_for_log(tool_args)
            logger.info(f"[AIClient] 工具调用: {tool_call.function.name}, 参数: {safe_args}")

            # 执行工具: ToolNet 注册表优先 (地球online 全量工具走 BaseTool 标准签名)，
            # 注册表中不存在时回退 gestalt (内置工具/技能/MCP)
            result = await self._dispatch_tool_execution(tool_call.function.name, tool_args or {}, tool_context)
            if result is None:
                gestalt = get_gestalt_controller()
                result = await gestalt.execute_tool(tool_call.function.name, tool_args or {}, tool_context or {})

            # 显示工具结果
            print(TerminalFormatter.tool_result(tool_call.function.name))

            return tool_call, result
        except Exception as e:
            logger.error(f"[AIClient] 工具执行异常: {e}", exc_info=True)
            return tool_call, f"工具执行异常: {str(e)}"

    async def _dispatch_tool_execution(self, tool_name: str, args: Dict[str, Any], tool_context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """经 ToolNet 注册表执行工具；工具不在注册表时返回 None 由调用方回退 gestalt。"""
        subnet = _get_toolnet_subnet()
        if subnet is None or not subnet.registry.get_tool(tool_name):
            return None
        context = tool_context if isinstance(tool_context, dict) else {}
        context_user = context.get("user_id")
        try:
            # 保留完整会话上下文。此前这里只传 user_id，导致群聊工具执行时
            # 丢失 group_id/message_type，文件发送被安全守卫拦截（或旧版本误发私聊）。
            return await subnet.execute_tool(
                tool_name,
                args,
                user_id=context_user,
                group_id=context.get("group_id"),
                message_type=context.get("message_type"),
                sender_name=context.get("sender_name"),
                platform_adapter=context.get("platform_adapter"),
                platform_user_id=context.get("platform_user_id"),
                platform=context.get("platform"),
                tool_context=context,
                at_list=context.get("at_list") or [],
            )
        except Exception as exc:
            logger.warning(f"[AIClient] ToolNet 分发失败 {tool_name}: {exc}")
            return None

    def _handle_final_marker(self, result: str) -> Optional[str]:
        """
        处理FINAL标记

        Args:
            result: 工具结果

        Returns:
            如果是FINAL标记，返回提取的消息内容；否则返回None
        """
        if not result or not result.startswith("[FINAL]"):
            return None

        logger.info(f"[AIClient] 检测到 FINAL 标记: {result[:80]}")

        # 检查是否包含嵌入的消息内容
        if "|||" in result:
            parts = result.split("|||", 1)
            embedded_message = parts[0].replace("[FINAL]", "").strip()
            if embedded_message:
                logger.info(f"[AIClient] 提取嵌入消息内容: {embedded_message[:50]}...")
                return embedded_message

        return "[FINAL]"

    async def chat_with_system_prompt(
        self,
        system_prompt: str,
        user_message: str,
        tools: Optional[List[Dict]] = None,
        use_miya_prompt: bool = True,
        conversation_history: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        local_reply: bool = False,
    ) -> str:
        """
        使用系统提示词聊天

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            tools: 可用工具列表
            use_miya_prompt: 是否使用弥娅人设提示词
            conversation_history: 对话历史 [{'role': 'user', 'content': '...'}, ...]
            tool_choice: 工具选择策略 ("auto", "required", "none")

        Returns:
            AI回复
        """
        # 如果启用人设提示词，则使用弥娅人设
        if use_miya_prompt:
            # 如果有工具，使用紧凑版提示词以提高工具调用准确率
            use_full = not bool(tools) or self.use_compact_prompt
            miya_prompt = self.get_miya_system_prompt(use_full=use_full)
            if miya_prompt:
                extracted = self._extract_tools_instruction(system_prompt)
                logger.debug(
                    f"[AIClient] 提取的工具指令长度: {len(extracted)}, 提示词类型: {'完整版' if use_full else '紧凑版'}"
                )
                system_prompt = miya_prompt + "\n\n" + extracted

        # 构建消息列表
        messages = [AIMessage(role="system", content=system_prompt)]

        # 添加对话历史
        if conversation_history:
            for msg in conversation_history:
                messages.append(AIMessage(role=msg["role"], content=msg["content"]))

        # 添加当前用户消息
        messages.append(AIMessage(role="user", content=user_message))

        return await self.chat(
            messages,
            tools,
            use_miya_prompt=False,
            tool_choice=tool_choice,
            local_reply=local_reply,
        )  # 避免重复添加


class OpenAIClient(BaseAIClient):
    """OpenAI API 客户端 — 同时支持所有 OpenAI 兼容协议的第三方 API"""

    provider_label: str = "OpenAI"
    _can_concurrent: bool = True
    _direct_return_tools: list = [
        "horoscope",
        "wenchang_dijun",
        "list_game_saves",
        "create_game_save",
        "load_game_save",
        "roll_dice",
        "roll_secret",
        "skill_check",
        "create_pc",
        "show_pc",
        "update_pc",
        "delete_pc",
        "start_combat",
        "add_initiative",
        "next_turn",
        "show_initiative",
        "end_combat",
        "rest",
        "attack",
        "combat_log",
        "kp_command",
        "terminal_command",
        "multi_terminal",
        "douyinhot",
        "weibohot",
        "baiduhot",
        "grok_search",
        "web_search",
        "crawl_webpage",
        # 搜索和下载结果仍需回传模型，才能继续执行后续动作（例如
        # resource_find -> download_file -> send_platform_file）。
        # 将这些工具列为 direct-return 会在第一步后提前结束整条链路。
        # python_interpreter 同样保持可组合，便于“生成文件后发送”等多步任务。
        "send_platform_file",
        "group_file_downloader",
        "local_file_finder",
        "qq_file_reader",
    ]

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        provider=None,
        **kwargs,
    ):
        super().__init__(api_key, model, **kwargs)
        self.base_url = base_url

        if provider is not None:
            self._provider = provider
            self.client = provider._client
        else:
            self._provider = None
            try:
                from openai import AsyncOpenAI

                self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            except ImportError:
                logger.warning("OpenAI库未安装，请在虚拟环境中运行: pip install openai")
                self.client = None

    @classmethod
    def from_provider(cls, provider):
        """从 Provider 实例创建 OpenAIClient，复用其 AsyncOpenAI 连接"""
        return cls(
            api_key=provider.config.api_key,
            model=provider.config.model,
            base_url=provider.config.base_url or "",
            provider=provider,
        )

    async def chat(
        self,
        messages: List[AIMessage],
        tools: Optional[List[Dict]] = None,
        max_iterations: int = 20,
        use_miya_prompt: bool = True,
        tool_choice: str = "auto",
        max_tokens: int = None,
        local_reply: bool = False,
    ) -> str:
        """调用OpenAI聊天接口（支持工具调用）

        Args:
            messages: 消息列表
            tools: 可用工具列表
            max_iterations: 最大工具调用迭代次数
            use_miya_prompt: 是否使用弥娅人设提示词
            tool_choice: 工具选择策略 ("auto", "required", "none")
            local_reply: 这是不是「给用户的最终回复」；本地模型据此决定走「云端草稿+本地口吻」

        Returns:
            AI回复
        """
        if not self.client:
            raise RuntimeError("OpenAI客户端未初始化，请安装openai库")

        # 调用基类方法处理人设提示词
        if use_miya_prompt:
            # 复制消息列表以避免修改原始数据
            messages = [
                AIMessage(
                    role=msg.role,
                    content=msg.content,
                    tool_calls=msg.tool_calls,
                    tool_call_id=msg.tool_call_id,
                )
                for msg in messages
            ]

        # 使用传入的工具或工具注册表
        # 本地小模型不注入工具 schema：工具/操作仍由云端模型处理，
        # 否则上千 token 的工具定义会把本地提示词撑到 3 万+，prefill 要一分多钟。
        local_rewrite_draft = ""
        local_draft_prepared = False
        local_original_messages = list(messages)
        if self._is_local_backend():
            if not self._local_endpoint_ready():
                fallback_client = self._get_cloud_fallback_client()
                if fallback_client:
                    fallback_client.tool_context = self.tool_context
                    if self.tool_registry:
                        fallback_client.set_tool_registry(self.tool_registry)
                    logger.info("[AIClient] 本地端点未启动，直接使用云端客户端")
                    return await fallback_client.chat(
                        local_original_messages,
                        tools=tools,
                        use_miya_prompt=False,
                        tool_choice=tool_choice,
                        max_tokens=max_tokens,
                    )
            if tools is None and self.tool_registry:
                tools = self.tool_registry()
            if tools:
                cloud = self._get_cloud_fallback_client()
                if not cloud:
                    return "云端工具处理暂不可用，这次没有执行操作，请稍后重试。"
                cloud.tool_context = self.tool_context
                if self.tool_registry:
                    cloud.set_tool_registry(self.tool_registry)
                logger.info("[AIClient] 本地后端收到工具请求，交由云端执行并生成答复")
                cloud_result = await cloud.chat(
                    local_original_messages,
                    tools=tools,
                    use_miya_prompt=False,
                    tool_choice=tool_choice,
                    max_tokens=max_tokens,
                )
                # 用户最终回复走“云端大脑 + 本地口吻”；内部调用仍直接使用云端结果。
                if local_reply and isinstance(cloud_result, str) and cloud_result.strip():
                    if not self._looks_refusal(cloud_result):
                        hint = (
                            (local_original_messages[0].content or "")[:400]
                            if local_original_messages and local_original_messages[0].role == "system"
                            else ""
                        )
                        local_rewrite_draft = cloud_result
                        try:
                            messages = self._apply_local_rewrite(
                                local_original_messages, cloud_result, persona_hint=hint
                            )
                        except Exception as rewrite_error:
                            logger.warning("[AIClient] Local rewrite preparation failed: %s", rewrite_error)
                            return cloud_result
                        tools = []
                        local_draft_prepared = True
                    else:
                        logger.info("[AIClient] 云端工具结果疑似拒答，直接返回云端结果")
                        return cloud_result
                else:
                    return cloud_result
            if tools:
                logger.info("[AIClient] 本地后端：忽略 %d 个工具定义（工具调用走云端）", len(tools))
            tools = []
            # 只有「弥娅全量提示词」或「明确标记为最终回复」才精简/改写；内部短提示词原样保留
            sys_chars = len(messages[0].content or "") if messages and messages[0].role == "system" else 0
            if (local_reply or sys_chars > 6000) and not local_draft_prepared:
                rewrite_mode = self._local_rewrite_enabled()
                draft = ""
                if rewrite_mode or self._local_draft_enabled():
                    draft = await self._local_cloud_draft(messages)
                if rewrite_mode:
                    if draft and not self._looks_refusal(draft):
                        # 草稿本来就干净 -> 直接用云端原文，保证完全对齐（还省 2~3 秒）
                        if (
                            self._skip_clean_draft_enabled()
                            and not self._needs_rewrite(draft)
                            and not self._draft_is_stalling(draft)
                        ):
                            logger.info("[AIClient] 草稿干净，直接采用云端原文（本地不改写）")
                            return draft
                        hint = (messages[0].content or "")[:400] if messages and messages[0].role == "system" else ""
                        local_rewrite_draft = draft
                        try:
                            messages = self._apply_local_rewrite(messages, draft, persona_hint=hint)
                        except Exception as rewrite_error:
                            logger.warning("[AIClient] Local rewrite preparation failed: %s", rewrite_error)
                            return draft
                    else:
                        logger.info("[AIClient] 草稿不可用（空或疑似拒答），回退人设直答")
                        messages = self._apply_local_compact(messages)
                else:
                    messages = self._apply_local_compact(messages, draft=draft)
            else:
                logger.info("[AIClient] 本地后端：短提示词（%d 字）原样使用", sys_chars)
        elif tools is None and self.tool_registry:
            tools = self.tool_registry()

        logger.info(f"[AIClient] 开始聊天 (模型: {self.model})，工具数量: {len(tools) if tools else 0}")
        if tools:
            logger.info(f"[AIClient] 可用工具: {[t.get('function', {}).get('name', 'unknown') for t in tools]}")
            # 打印start_trpg工具的schema
            for t in tools:
                if t.get("function", {}).get("name") == "start_trpg":
                    logger.debug(
                        f"[AIClient] start_trpg工具schema: {json.dumps(t.get('function', {}), ensure_ascii=False)[:500]}"
                    )

        iteration = 0
        rebuild_count = 0
        current_messages = messages.copy()

        while iteration < max_iterations:
            try:
                openai_messages = self._convert_messages_to_openai_format(current_messages)

                # 构建请求参数
                request_params = {
                    "model": self.model,
                    "messages": openai_messages,
                    "temperature": self.config.get("temperature", 0.7),
                    "max_tokens": max_tokens or self._resolve_max_tokens(bool(tools)),
                }

                # 本地口吻引擎：低温度，尽量贴着草稿改，不要发挥
                if self._is_local_backend() and self._local_rewrite_enabled():
                    try:
                        request_params["temperature"] = float(
                            os.getenv("MIYA_LOCAL_LLM_REWRITE_TEMP", "0.35")
                        )
                    except (TypeError, ValueError):
                        request_params["temperature"] = 0.35

                # 添加工具相关参数
                if tools:
                    request_params["tools"] = tools
                    request_params["tool_choice"] = self._normalize_tool_choice(tool_choice)

                # DeepSeek V4 内置联网搜索需要通过特定端点启用，目前API暂不支持
                # if "deepseek" in self.model.lower() and "v4" in self.model.lower():
                #     request_params["enable_search"] = True

                try:
                    response = await self.client.chat.completions.create(**request_params)
                except Exception as local_err:
                    # 本地模型掉线/超时/报错：别让对话卡住，直接交给云端
                    if self._is_local_backend():
                        logger.warning("[AIClient] 本地模型调用失败(%s)，自动改走云端", local_err)
                        fallback_msgs = locals().get("local_original_messages") or messages
                        if local_rewrite_draft:
                            return local_rewrite_draft
                        fb = self._get_cloud_fallback_client()
                        if fb:
                            return await fb.chat(
                                fallback_msgs,
                                tools=None,
                                use_miya_prompt=False,
                                tool_choice=tool_choice,
                                max_tokens=max_tokens,
                            )
                    raise

                choice = response.choices[0]
                message = choice.message

                # 增强调试日志
                logger.info(
                    f"[AIClient] OpenAI响应 - 返回类型: {type(message).__name__}, 有工具调用: {bool(message.tool_calls)}, content长度: {len(message.content) if message.content else 0}, tool_choice={tool_choice}"
                )

                # 提取思考过程（DeepSeek R1等模型特有）
                reasoning_content = getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None)
                if reasoning_content:
                    logger.info(f"[AIClient] 检测到思考过程，长度: {len(reasoning_content)}")

                # 如果没有工具调用，检查是否需要强制调用工具
                if not message.tool_calls:
                    logger.debug(f"[AIClient] OpenAI返回纯文本（无工具调用），tool_choice={tool_choice}")
                    logger.debug(f"[AIClient] 返回内容预览: {message.content[:200] if message.content else '(无内容)'}")

                    # 【修复】检测用户输入是否需要执行操作，如果是则强制AI重新考虑
                    # 获取用户最新消息（排除系统提醒/上下文标记消息）
                    user_message = ""
                    for msg in reversed(current_messages):
                        if msg.role == "user" and not any(
                            marker in msg.content
                            for marker in [
                                "【系统提醒】",
                                "【弥娅时间感知】",
                                "【弥娅看到的画面】",
                                "【对话历史上下文】",
                                "【当前感知】",
                                "【群聊时间线】",
                                "【情感指引】",
                                "【记忆上下文】",
                                "【近期思维参考】",
                            ]
                        ):
                            user_message = msg.content
                            break

                    # 检测是否需要执行操作
                    needs_action = self._check_needs_tool_action(user_message)

                    # 限制强制重新请求次数，避免无限循环
                    force_retry_count = sum(
                        1 for msg in current_messages if msg.role == "user" and "【系统提醒】" in msg.content
                    )

                    if needs_action and tool_choice == "auto" and force_retry_count < 2 and tools:
                        # 添加强制调用工具的提示，重新请求AI（最多重试2次）
                        logger.info(
                            f"[AIClient] OpenAI检测到需要执行操作但AI未调用工具，强制重新请求... (重试 {force_retry_count + 1}/2)"
                        )
                        _is_reminder = re.search(
                            r"提醒我|提醒|叫我|喊我|定时|分钟.*后|几点",
                            user_message or "",
                        )
                        _retry_msg = (
                            "【系统提醒】你刚才没有调用 create_schedule_task 工具来设置提醒！"
                            if _is_reminder
                            else "【系统提醒】你刚才没有执行用户请求的操作。请用自然语言描述你正在做什么，不要输出代码格式。"
                        )
                        force_message = AIMessage(role="user", content=_retry_msg)
                        current_messages.append(force_message)
                        continue  # 继续循环，让AI重新生成响应

                    if tool_choice == "required":
                        logger.error(
                            "[AIClient] tool_choice='required'但模型未调用工具，可能是工具描述或系统提示词问题"
                        )
                    # 过滤思考过程（如 DeepSeek R1 的 reasoning_content）
                    final_content = message.content or ""
                    thinking_content = ""
                    if reasoning_content:
                        final_content, thinking_content = self._filter_thinking_content(
                            final_content, reasoning_content
                        )

                    # 打印思考过程到终端（仅终端显示，不发送给用户）
                    if thinking_content:
                        thinking_lines = thinking_content.split("\n")[:10]
                        print(TerminalFormatter.thinking_block("\n".join(thinking_lines)))

                    # 【新增】保存思考过程供外部获取
                    self.last_reasoning_content = thinking_content

                    # 本地口吻引擎跑飞（把提示词分析吐出来）就退回云端草稿，别发给用户
                    if local_rewrite_draft and self._looks_like_prompt_leak(final_content):
                        logger.warning("[AIClient] 本地输出疑似提示词泄漏，改用云端草稿")
                        return local_rewrite_draft

                    # 返回最终回复（不含思考过程）
                    return final_content

                # 有工具调用，执行工具
                tool_calls = message.tool_calls
                logger.info(f"{self.provider_label} AI请求调用工具: {[tc.function.name for tc in tool_calls]}")

                # 添加助手消息（包含工具调用和思考过程）
                reasoning_content = getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None)
                current_messages.append(
                    AIMessage(
                        role="assistant",
                        content=message.content or "",
                        tool_calls=[
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in tool_calls
                        ],
                        reasoning_content=reasoning_content,
                    )
                )

                # 执行工具（支持并发执行）
                import asyncio

                # 并发执行多工具调用以降低延迟
                can_concurrent = self._can_concurrent

                if can_concurrent:
                    # 并发执行多个工具调用
                    logger.info(f"[AIClient] 并发执行 {len(tool_calls)} 个工具调用")

                    async def _exec_concurrent(tc):
                        try:
                            _, r = await self._execute_tool_call(tc, self.tool_context)
                            return tc, r
                        except Exception as exc:
                            logger.error(f"[AIClient] 工具 {tc.function.name} 执行异常: {exc}")
                            raise

                    tool_results_list = await asyncio.gather(
                        *[_exec_concurrent(tc) for tc in tool_calls],
                        return_exceptions=True,
                    )

                    # 按原始 tool_calls 顺序添加响应消息
                    tool_call_id_to_result = {}
                    final_detected = False
                    for tr in tool_results_list:
                        if isinstance(tr, Exception):
                            logger.error(f"[AIClient] 并发工具执行异常: {tr}")
                            continue
                        tool_call, result = tr
                        tool_call_id_to_result[tool_call.id] = (tool_call, result)

                    # 终止型工具（例如发送文件）已经是完整动作，聚合结果后直接返回，
                    # 避免模型在发送完成后继续跑浏览器/Python 检查。可组合的搜索/下载
                    # 工具不在 direct-return 列表中，必须把结果交回模型继续编排。
                    if tool_calls and all(
                        tc.function.name in self._direct_return_tools for tc in tool_calls
                    ):
                        return "\n".join(
                            str(tool_call_id_to_result[tc.id][1])
                            for tc in tool_calls
                            if tc.id in tool_call_id_to_result
                        )

                    for tc in tool_calls:
                        if tc.id not in tool_call_id_to_result:
                            logger.warning(f"[AIClient] 工具 {tc.function.name} 未返回结果，添加占位响应")
                            current_messages.append(
                                AIMessage(
                                    role="tool",
                                    content="工具执行异常，请尝试其他方式",
                                    tool_call_id=tc.id,
                                )
                            )
                            continue
                        tool_call, result = tool_call_id_to_result[tc.id]

                        if len(tool_calls) == 1 and tc.function.name in self._direct_return_tools:
                            logger.info(
                                f"[AIClient] 检测到直接返回工具: {tc.function.name}，直接返回结果"
                            )
                            return result

                        # 检查工具结果是否包含 FINAL 标记
                        if result and result.startswith("[FINAL]"):
                            logger.info(f"[AIClient] 检测到 FINAL 标记: {result[:80]}")

                            # 【新增】检查是否包含嵌入的消息内容
                            if "|||" in result:
                                parts = result.split("|||", 1)
                                embedded_message = parts[0].replace("[FINAL]", "").strip()
                                if embedded_message:
                                    logger.info(f"[AIClient] 提取嵌入消息内容: {embedded_message[:50]}...")
                                    return embedded_message

                            final_detected = True

                        current_messages.append(AIMessage(role="tool", content=result, tool_call_id=tool_call.id))

                    if final_detected:
                        # FINAL 标记检测到，让 AI 生成最终文本回复（不再调用工具）
                        logger.info("[AIClient] FINAL 标记触发，生成最终文本回复")
                        try:
                            final_resp = await self.client.chat.completions.create(
                                model=self.model,
                                messages=[{"role": m.role, "content": m.content} for m in current_messages],
                                tool_choice="none",
                            )
                            if final_resp.choices and final_resp.choices[0].message:
                                return final_resp.choices[0].message.content or ""
                        except Exception as e:
                            logger.warning(f"[AIClient] 最终回复生成失败: {e}")
                        return ""
                else:
                    # 串行执行（使用公共方法）
                    final_detected = False
                    executed_results = []
                    for tool_call in tool_calls:
                        _, result = await self._execute_tool_call(tool_call, self.tool_context)

                        # 检查FINAL标记
                        final_marker = self._handle_final_marker(result)
                        if final_marker == "[FINAL]":
                            final_detected = True
                            # 生成最终文本回复
                            try:
                                final_resp = await self.client.chat.completions.create(
                                    model=self.model,
                                    messages=[{"role": m.role, "content": m.content} for m in current_messages],
                                    tool_choice="none",
                                )
                                if final_resp.choices and final_resp.choices[0].message:
                                    return final_resp.choices[0].message.content or ""
                            except Exception as e:
                                logger.warning(f"[AIClient] 最终回复生成失败: {e}")
                            return ""
                        elif final_marker:
                            return final_marker

                        if len(tool_calls) == 1 and tool_call.function.name in self._direct_return_tools:
                            logger.info(
                                f"[AIClient] 检测到直接返回工具: {tool_call.function.name}，直接返回结果"
                            )
                            return result

                        executed_results.append((tool_call, result))

                    # 添加所有工具结果消息，不能只保留最后一个调用的结果。
                    for tool_call, result in executed_results:
                        current_messages.append(AIMessage(role="tool", content=result, tool_call_id=tool_call.id))
                        logger.info(
                            f"[AIClient] 工具结果已添加到对话历史: {result[:100] if result else '(无结果)'}"
                        )

                iteration += 1

            except Exception as e:
                from openai import AuthenticationError as OpenAIAuthError

                err_str = str(e)
                logger.error(f"{self.provider_label} API调用失败: {err_str}")

                # Local response/protocol errors also need cloud fallback.
                if self._is_local_backend():
                    if local_rewrite_draft:
                        return local_rewrite_draft
                    fallback_client = self._get_cloud_fallback_client()
                    if fallback_client:
                        try:
                            return await fallback_client.chat(
                                local_original_messages,
                                tools=None,
                                use_miya_prompt=False,
                                tool_choice=tool_choice,
                                max_tokens=max_tokens,
                            )
                        except Exception as fallback_error:
                            logger.warning("[AIClient] Local fallback failed: %s", fallback_error)

                if isinstance(e, OpenAIAuthError):
                    return f"抱歉亲爱的，当前{self.provider_label}模型认证出现问题，可能是密钥已过期。请检查API密钥是否有效~"

                # 工具调用格式错误时清理消息并重试
                if "tool" in err_str.lower() and ("400" in err_str or "invalid" in err_str.lower()):
                    rebuild_count += 1
                    iteration += 1
                    if rebuild_count > 3:
                        return "抱歉亲爱的，工具调用反复出错，请稍后再试~"
                    logger.warning(f"[AIClient] 工具调用格式错误，重建干净消息后重试 | 原始错误: {err_str[:200]}")
                    # 重建消息：只保留 system / user / assistant(无 tool_calls) 消息
                    # 丢弃所有 tool 消息和有 tool_calls 的 assistant 消息
                    current_messages = [
                        AIMessage(
                            role=msg.role,
                            content=msg.content,
                        )
                        if msg.role == "assistant"
                        else msg
                        for msg in current_messages
                        if msg.role != "tool"
                    ]
                    current_messages.append(
                        AIMessage(
                            role="user",
                            content="前面的任务已经完成。请简要告诉我结果。",
                        )
                    )
                    continue

                return f"抱歉，AI服务暂时不可用\n错误详情：{err_str[:300]}"

        # 达到最大迭代次数
        return get_error_message("tool_call_limit_exceeded")

    async def chat_stream(
        self,
        messages: List[AIMessage],
        tools: Optional[List[Dict]] = None,
        max_iterations: int = 20,
        use_miya_prompt: bool = True,
        tool_choice: str = "auto",
        local_reply: bool = False,
    ):
        """流式聊天（async generator），逐块 yield 内容 + 工具调用处理

        Yields:
            {"type": "content", "data": str}   — 文本块
            {"type": "thinking", "data": str}  — 思考过程（DeepSeek）
            {"type": "tool_start", "data": {"name": str, "id": str}}  — 工具调用开始
            {"type": "tool_result", "data": {"name": str, "result": str}}  — 工具结果
            {"type": "done", "data": str}      — 完成，data 为完整文本
            {"type": "error", "data": str}     — 错误
        """
        if not self.client:
            yield {"type": "error", "data": "OpenAI客户端未初始化"}
            return

        # 本地后端：精简提示词 + 不注入工具（工具走云端）
        local_original_messages = list(messages)
        local_rewrite_draft = ""
        local_draft_prepared = False
        if self._is_local_backend():
            if not self._local_endpoint_ready():
                fallback_client = self._get_cloud_fallback_client()
                if fallback_client:
                    fallback_client.tool_context = self.tool_context
                    if self.tool_registry:
                        fallback_client.set_tool_registry(self.tool_registry)
                    logger.info("[AIClient-stream] 本地端点未启动，直接使用云端客户端")
                    async for chunk in fallback_client.chat_stream(
                        local_original_messages,
                        tools=tools,
                        use_miya_prompt=False,
                        tool_choice=tool_choice,
                        local_reply=False,
                    ):
                        yield chunk
                    return
            if tools is None and self.tool_registry:
                tools = self.tool_registry()
            if tools:
                cloud = self._get_cloud_fallback_client()
                if not cloud:
                    yield {"type": "error", "data": "云端工具处理暂不可用，这次没有执行操作，请稍后重试。"}
                    return
                cloud.tool_context = self.tool_context
                if self.tool_registry:
                    cloud.set_tool_registry(self.tool_registry)
                logger.info("[AIClient-stream] 本地后端收到工具请求，交由云端执行并生成答复")
                cloud_draft = ""
                async for chunk in cloud.chat_stream(
                    local_original_messages,
                    tools=tools,
                    use_miya_prompt=False,
                    tool_choice=tool_choice,
                    local_reply=False,
                ):
                    chunk_type = chunk.get("type") if isinstance(chunk, dict) else ""
                    if chunk_type == "done":
                        cloud_draft = str(chunk.get("data") or "").strip()
                    elif chunk_type in {"tool_start", "tool_result"}:
                        # 保留工具进度事件，但不把云端草稿直接发给用户。
                        yield chunk
                if not local_reply or not cloud_draft:
                    if cloud_draft:
                        yield {"type": "content", "data": cloud_draft}
                        yield {"type": "done", "data": cloud_draft}
                    return
                if self._looks_refusal(cloud_draft):
                    yield {"type": "content", "data": cloud_draft}
                    yield {"type": "done", "data": cloud_draft}
                    return
                hint = (
                    (local_original_messages[0].content or "")[:400]
                    if local_original_messages and local_original_messages[0].role == "system"
                    else ""
                )
                messages = self._apply_local_rewrite(local_original_messages, cloud_draft, persona_hint=hint)
                local_rewrite_draft = cloud_draft
                tools = []
                local_draft_prepared = True
            if tools:
                logger.info("[AIClient-stream] 本地后端：忽略 %d 个工具定义", len(tools))
            tools = []
            sys_chars = len(messages[0].content or "") if messages and messages[0].role == "system" else 0
            if (local_reply or sys_chars > 6000) and not local_draft_prepared:
                msgs = list(messages)
                rewrite_mode = self._local_rewrite_enabled()
                draft = ""
                if rewrite_mode or self._local_draft_enabled():
                    draft = await self._local_cloud_draft(msgs)
                if rewrite_mode:
                    if draft and not self._looks_refusal(draft):
                        if (
                            self._skip_clean_draft_enabled()
                            and not self._needs_rewrite(draft)
                            and not self._draft_is_stalling(draft)
                        ):
                            logger.info("[AIClient-stream] 草稿干净，直接采用云端原文")
                            yield {"type": "content", "data": draft}
                            yield {"type": "done", "data": draft}
                            return
                        hint = (msgs[0].content or "")[:400] if msgs and msgs[0].role == "system" else ""
                        messages = self._apply_local_rewrite(msgs, draft, persona_hint=hint)
                        local_rewrite_draft = draft
                    else:
                        messages = self._apply_local_compact(msgs)
                else:
                    messages = self._apply_local_compact(msgs, draft=draft)
        elif tools is None and self.tool_registry:
            tools = self.tool_registry()

        logger.info(f"[AIClient-stream] 流式聊天开始 (模型: {self.model}), 工具: {len(tools) if tools else 0}")

        iteration = 0
        current_messages = list(messages)

        while iteration < max_iterations:
            content_parts: List[str] = []
            try:
                openai_messages = self._convert_messages_to_openai_format(current_messages)

                request_params = {
                    "model": self.model,
                    "messages": openai_messages,
                    "temperature": self.config.get("temperature", 0.7),
                    "max_tokens": self._resolve_max_tokens(bool(tools)),
                    "stream": True,
                }

                # 本地口吻引擎：低温度，尽量贴着草稿改
                if self._is_local_backend() and self._local_rewrite_enabled():
                    try:
                        request_params["temperature"] = float(
                            os.getenv("MIYA_LOCAL_LLM_REWRITE_TEMP", "0.35")
                        )
                    except (TypeError, ValueError):
                        request_params["temperature"] = 0.35

                if tools:
                    request_params["tools"] = tools
                    request_params["tool_choice"] = self._normalize_tool_choice(tool_choice)

                stream = await self.client.chat.completions.create(**request_params)

                tool_call_buffer: Dict[int, Dict] = {}

                async for chunk in stream:
                    if not chunk.choices:
                        continue

                    delta = chunk.choices[0].delta

                    reasoning = getattr(delta, "reasoning_content", None)
                    if reasoning:
                        yield {"type": "thinking", "data": reasoning}

                    if delta.content:
                        content_parts.append(delta.content)
                        yield {"type": "content", "data": delta.content}

                    if delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tool_call_buffer:
                                tool_call_buffer[idx] = {
                                    "id": "",
                                    "function": {"name": "", "arguments": ""},
                                }
                            buf = tool_call_buffer[idx]
                            if tc_delta.id:
                                buf["id"] = tc_delta.id
                            if tc_delta.function:
                                if tc_delta.function.name:
                                    buf["function"]["name"] += tc_delta.function.name
                                if tc_delta.function.arguments:
                                    buf["function"]["arguments"] += tc_delta.function.arguments

                if tool_call_buffer:
                    tool_calls_list = [tool_call_buffer[i] for i in sorted(tool_call_buffer.keys())]

                    logger.info(f"[AIClient-stream] 检测到 {len(tool_calls_list)} 个工具调用")

                    # 通知工具调用
                    for tc in tool_calls_list:
                        yield {"type": "tool_start", "data": {"name": tc["function"]["name"], "id": tc["id"]}}

                    # 构建 assistant message
                    current_messages.append(
                        AIMessage(
                            role="assistant",
                            content="".join(content_parts) if content_parts else None,
                            tool_calls=[
                                {
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": tc["function"],
                                }
                                for tc in tool_calls_list
                            ],
                        )
                    )

                    # 执行工具
                    for tc_info in tool_calls_list:
                        tool_name = tc_info["function"]["name"]
                        raw_arguments = (tc_info["function"]["arguments"] or "").strip()
                        tool_args = self._fix_json_arguments(tc_info["function"]["arguments"])

                        if raw_arguments and tool_args is None:
                            logger.warning(f"[AIClient-stream] 工具 {tool_name} 参数解析失败，反馈给模型重新生成")
                            result = (
                                "【参数错误】工具参数 JSON 解析失败（可能因内容过长被截断）。"
                                "请重新生成参数，并尽量精简代码/内容、避免过长。"
                            )
                        else:
                            try:
                                result = await self._dispatch_tool_execution(tool_name, tool_args or {}, self.tool_context)
                                if result is None:
                                    from core.gestalt_controller import get_gestalt_controller

                                    gestalt = get_gestalt_controller()
                                    result = await gestalt.execute_tool(tool_name, tool_args or {}, self.tool_context or {})
                            except Exception as e:
                                logger.error(f"[AIClient-stream] 工具执行异常: {e}")
                                result = f"工具执行异常: {str(e)}"

                        result_str = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
                        yield {"type": "tool_result", "data": {"name": tool_name, "result": result_str[:200]}}

                        current_messages.append(AIMessage(role="tool", content=result_str, tool_call_id=tc_info["id"]))

                        # 检查 FINAL 标记
                        if result_str.startswith("[FINAL]"):
                            if "|||" in result_str:
                                embedded = result_str.split("|||", 1)[0].replace("[FINAL]", "").strip()
                                if embedded:
                                    yield {"type": "done", "data": embedded}
                                    return
                            yield {"type": "done", "data": ""}
                            return

                    iteration += 1
                    continue  # 继续循环让 AI 处理工具结果

                # 无工具调用：流式完成
                full_content = "".join(content_parts)
                full_content, _ = self._filter_thinking_content(full_content, "")
                yield {"type": "done", "data": full_content}
                return

            except Exception as e:
                logger.error(f"[AIClient-stream] 流式调用失败: {e}")
                if self._is_local_backend():
                    # 流式输出一旦开始便不能安全替换；只有还未发出文本时整段回退。
                    if not content_parts:
                        if local_rewrite_draft:
                            fallback_text = local_rewrite_draft
                        else:
                            fallback_client = self._get_cloud_fallback_client()
                            fallback_text = ""
                            if fallback_client:
                                try:
                                    fallback_text = await fallback_client.chat(
                                        local_original_messages,
                                        tools=None,
                                        use_miya_prompt=False,
                                        tool_choice=tool_choice,
                                    )
                                except Exception as fallback_error:
                                    logger.warning("[AIClient-stream] 云端回退失败: %s", fallback_error)
                        if fallback_text:
                            yield {"type": "content", "data": fallback_text}
                            yield {"type": "done", "data": fallback_text}
                            return
                from openai import AuthenticationError as OpenAIAuthError

                err_str = str(e)
                if isinstance(e, OpenAIAuthError):
                    yield {"type": "error", "data": f"认证失败，请检查API密钥: {err_str[:200]}"}
                else:
                    yield {"type": "error", "data": f"AI服务暂时不可用: {err_str[:300]}"}
                return

        yield {"type": "error", "data": "达到最大工具调用迭代次数"}

    async def chat_with_system_prompt_stream(
        self,
        system_prompt: str,
        user_message: str,
        tools: Optional[List[Dict]] = None,
        use_miya_prompt: bool = True,
        conversation_history: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        local_reply: bool = False,
    ):
        """流式版本 chat_with_system_prompt — async generator"""
        if use_miya_prompt:
            use_full = not bool(tools) or self.use_compact_prompt
            miya_prompt = self.get_miya_system_prompt(use_full=use_full)
            if miya_prompt:
                extracted = self._extract_tools_instruction(system_prompt)
                system_prompt = miya_prompt + "\n\n" + extracted

        messages = [AIMessage(role="system", content=system_prompt)]

        if conversation_history:
            for msg in conversation_history:
                messages.append(AIMessage(role=msg["role"], content=msg["content"]))

        messages.append(AIMessage(role="user", content=user_message))

        async for chunk in self.chat_stream(
            messages,
            tools,
            use_miya_prompt=False,
            tool_choice=tool_choice,
            local_reply=local_reply,
        ):
            yield chunk


class DeepSeekClient(OpenAIClient):
    """DeepSeek API 客户端 — 继承 OpenAIClient，仅覆盖 DeepSeek 特有行为"""

    provider_label = "DeepSeek"
    _can_concurrent = False


class AnthropicClient(BaseAIClient):
    """Anthropic (Claude) API客户端"""

    def __init__(self, api_key: str, model: str, **kwargs):
        super().__init__(api_key, model, **kwargs)

        try:
            from anthropic import AsyncAnthropic

            self.client = AsyncAnthropic(api_key=api_key)
        except ImportError:
            logger.warning("Anthropic库未安装，请运行: pip install anthropic")
            self.client = None

    async def chat(self, messages: List[AIMessage]) -> str:
        """调用Anthropic聊天接口"""
        if not self.client:
            raise RuntimeError("Anthropic客户端未初始化，请安装anthropic库")

        try:
            # 提取system prompt
            system_prompt = None
            user_messages = []

            for msg in messages:
                if msg.role == "system":
                    system_prompt = msg.content
                else:
                    user_messages.append({"role": msg.role, "content": msg.content})

            response = await self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=user_messages,
                max_tokens=self.config.get("max_tokens", 2000),
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Anthropic API调用失败: {e}")
            raise


class ZhipuAIClient(BaseAIClient):
    """智谱AI API客户端"""

    def __init__(self, api_key: str, model: str, **kwargs):
        super().__init__(api_key, model, **kwargs)

        try:
            from zhipuai import ZhipuAI

            self.client = ZhipuAI(api_key=api_key)
        except ImportError:
            logger.warning("智谱AI库未安装，请运行: pip install zhipuai")
            self.client = None

    async def chat(self, messages: List[AIMessage]) -> str:
        """调用智谱AI聊天接口"""
        if not self.client:
            raise RuntimeError("智谱AI客户端未初始化，请安装zhipuai库")

        try:
            # 同步调用（智谱AI暂不支持async）
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": msg.role, "content": msg.content} for msg in messages],
                temperature=self.config.get("temperature", 0.7),
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"智谱AI API调用失败: {e}")
            raise


class AIClientFactory:
    """AI客户端工厂（带缓存复用）"""

    _clients = {
        "openai": OpenAIClient,
        "deepseek": DeepSeekClient,
        "anthropic": AnthropicClient,
        "zhipu": ZhipuAIClient,
        "siliconflow": OpenAIClient,  # 硅基流动使用 OpenAI 兼容格式
        "local_llama": OpenAIClient,  # 本地 llama.cpp (llama-server) OpenAI 兼容端点
        "ollama": OpenAIClient,       # Ollama OpenAI 兼容端点
    }

    _cache: dict[str, BaseAIClient] = {}
    _cache_max_size: int = 8

    @classmethod
    def _cache_key(cls, provider: str, api_key: str, model: str, base_url: str = "") -> str:
        return f"{provider}:{model}:{base_url}:{api_key[:8]}"

    @classmethod
    def create_client(cls, provider: str, api_key: str, model: str, **kwargs) -> BaseAIClient:
        """
        创建AI客户端

        Args:
            provider: 提供商名称。已知类型走专用 Client，未知类型兜底走 OpenAIClient。
            api_key: API密钥
            model: 模型名称
            **kwargs: 其他配置（可包含 'base_url', 'provider' 等）

        Returns:
            AI客户端实例
        """
        provider = provider.lower()
        client_class = cls._clients.get(provider)

        if not client_class:
            logger.info(f"[AIClientFactory] 未知 provider '{provider}'，兜底使用 OpenAIClient")
            client_class = OpenAIClient

        base_url = kwargs.pop("base_url", "") or ""
        provider_instance = kwargs.pop("provider_instance", None)
        cache_key = cls._cache_key(provider, api_key, model, base_url)

        if cache_key in cls._cache:
            cached = cls._cache[cache_key]
            cached.tool_context = kwargs.get("tool_context")
            cached.tool_registry = None
            if "tool_context" in kwargs and kwargs["tool_context"]:
                cached.set_tool_context(kwargs["tool_context"])
            logger.info(f"复用{provider}客户端，模型: {model} (缓存命中 {len(cls._cache)}个)")
            return cached

        logger.info(f"创建{provider}客户端，模型: {model}")
        try:
            kwargs["base_url"] = base_url if base_url else None
            if provider_instance is not None:
                kwargs["provider"] = provider_instance
            client = client_class(api_key=api_key, model=model, **kwargs)
        except Exception as e:
            logger.error(f"创建客户端失败 ({provider}/{model}): {type(e).__name__}: {e}", exc_info=True)
            raise

        if "tool_context" in kwargs and kwargs["tool_context"]:
            client.set_tool_context(kwargs["tool_context"])

        while len(cls._cache) >= cls._cache_max_size:
            oldest_key = next(iter(cls._cache))
            try:
                old = cls._cache.pop(oldest_key)
                if hasattr(old, "client") and old.client:
                    import asyncio as _asyncio

                    try:
                        loop = _asyncio.get_running_loop()
                        loop.create_task(old.client.close())
                    except RuntimeError:
                        pass
            except Exception:
                pass

        cls._cache[cache_key] = client
        return client

    @classmethod
    def from_provider(cls, provider) -> BaseAIClient:
        """从 Provider 实例创建 AI 客户端（复用 HTTP 连接）"""
        return cls.create_client(
            provider=provider.config.provider,
            api_key=provider.config.api_key,
            model=provider.config.model,
            base_url=provider.config.base_url or "",
            provider_instance=provider,
        )

    @classmethod
    def list_providers(cls) -> List[str]:
        """列出所有支持的提供商"""
        return list(cls._clients.keys())

"""
AstrBot Agent 配置模块
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentConfig:
    """Agent执行配置"""

    tool_call_timeout: int = 120
    """工具调用超时时间(秒)"""

    tool_schema_mode: str = "full"
    """工具schema模式: full 或 skills-like"""

    provider_wake_prefix: str = ""
    """Provider唤醒前缀"""

    streaming_response: bool = True
    """是否使用流式响应"""

    sanitize_context_by_modalities: bool = False
    """是否根据provider支持的模态清理上下文"""

    kb_agentic_mode: bool = False
    """知识库智能模式"""

    file_extract_enabled: bool = False
    """是否启用文件提取"""

    file_extract_prov: str = "moonshotai"
    """文件提取Provider"""

    file_extract_msh_api_key: str = ""
    """Moonshot AI API Key"""

    context_limit_reached_strategy: str = "truncate_by_turns"
    """上下文超限策略: truncate_by_turns, llm_compress"""

    llm_compress_instruction: str = ""
    """LLM压缩指令"""

    llm_compress_keep_recent: int = 6
    """LLM压缩保留最近N轮"""

    llm_compress_provider_id: str = ""
    """LLM压缩用Provider ID"""

    max_context_length: int = -1
    """最大上下文轮数，-1表示无限制"""

    dequeue_context_length: int = 1
    """超限时移除最旧N轮"""

    llm_safety_mode: bool = True
    """LLM安全模式"""

    safety_mode_strategy: str = "system_prompt"
    """安全模式策略"""

    computer_use_runtime: str = "none"
    """计算机使用运行时: none, local, sandbox"""

    sandbox_cfg: dict = field(default_factory=dict)
    """沙盒配置"""

    add_cron_tools: bool = True
    """是否添加工具定时任务"""

    provider_settings: dict = field(default_factory=dict)
    """Provider设置"""

    subagent_orchestrator: dict = field(default_factory=dict)
    """子代理编排器配置"""

    timezone: Optional[str] = None
    """时区"""

    max_quoted_fallback_images: int = 20
    """引用消息最多图片数"""

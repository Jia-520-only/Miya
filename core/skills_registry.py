"""弥娅Skills注册系统

整合Undefined的Skills架构能力：
- 工具注册表 (ToolRegistry)
- Agent注册表 (AgentRegistry)
- 基础注册表 (BaseRegistry)
- 热重载支持
- 执行统计
- 延迟加载
"""

import asyncio
import importlib.util
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union
from enum import Enum

logger = logging.getLogger(__name__)


class SkillStatus(Enum):
    """技能状态"""
    UNKNOWN = "unknown"
    LOADED = "loaded"
    ERROR = "error"
    RELOADING = "reloading"


@dataclass
class SkillStats:
    """技能执行统计数据
    
    记录单个技能（工具或Agent）的执行次数、成功率、耗时等
    """
    count: int = 0
    success: int = 0
    failure: int = 0
    total_duration: float = 0.0
    last_duration: float = 0.0
    last_error: Optional[str] = None
    last_called_at: Optional[float] = None
    
    def record_success(self, duration: float) -> None:
        """记录成功执行"""
        self.count += 1
        self.success += 1
        self.total_duration += duration
        self.last_duration = duration
        self.last_error = None
        self.last_called_at = time.time()
    
    def record_failure(self, duration: float, error: str) -> None:
        """记录失败执行"""
        self.count += 1
        self.failure += 1
        self.total_duration += duration
        self.last_duration = duration
        self.last_error = error
        self.last_called_at = time.time()
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.count == 0:
            return 0.0
        return self.success / self.count
    
    @property
    def avg_duration(self) -> float:
        """平均耗时"""
        if self.count == 0:
            return 0.0
        return self.total_duration / self.count
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "count": self.count,
            "success": self.success,
            "failure": self.failure,
            "total_duration": self.total_duration,
            "last_duration": self.last_duration,
            "last_error": self.last_error,
            "last_called_at": self.last_called_at,
            "success_rate": self.success_rate,
            "avg_duration": self.avg_duration,
        }


@dataclass
class SkillItem:
    """技能项元数据
    
    封装技能的配置、处理函数和加载状态
    """
    name: str
    config: Dict[str, Any]
    handler_path: Optional[Path] = None
    module_name: Optional[str] = None
    handler: Optional[Callable] = None
    loaded: bool = False
    status: SkillStatus = SkillStatus.UNKNOWN
    
    def get_function_name(self) -> str:
        """获取函数名"""
        return self.config.get("function", {}).get("name", "")
    
    def get_description(self) -> str:
        """获取描述"""
        return self.config.get("function", {}).get("description", "")
    
    def get_parameters(self) -> Dict[str, Any]:
        """获取参数定义"""
        return self.config.get("function", {}).get("parameters", {})


class BaseRegistry:
    """
    基础注册表类，用于发现和加载技能（Tools/Agents）
    
    提供：
    - 统一的加载和验证
    - 延迟加载执行
    - 执行统计
    - 热重载逻辑
    - 文件监视
    """
    
    def __init__(
        self,
        base_dir: Optional[Union[str, Path]] = None,
        kind: str = "skill",
        timeout_seconds: float = 480.0,
        enable_hot_reload: bool = True,
    ) -> None:
        """初始化基础注册表
        
        Args:
            base_dir: 技能目录
            kind: 技能类型（tool/agent）
            timeout_seconds: 执行超时时间
            enable_hot_reload: 是否启用热重载
        """
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path(".")
        
        self.kind = kind
        self.timeout_seconds = timeout_seconds
        self.enable_hot_reload = enable_hot_reload
        
        # 技能项存储
        self._items: Dict[str, SkillItem] = {}
        self._items_schema: List[Dict[str, Any]] = []
        
        # 统计数据
        self._stats: Dict[str, SkillStats] = {}
        
        # 锁
        self._items_lock = asyncio.Lock()
        self._reload_lock = asyncio.Lock()
        
        # 热重载
        self._watch_paths: List[Path] = [self.base_dir]
        self._watch_task: Optional[asyncio.Task[None]] = None
        self._watch_stop: Optional[asyncio.Event] = None
        self._last_snapshot: Dict[str, tuple[int, int]] = {}
        self._watch_filenames: set[str] = {"config.json", "handler.py"}
        
        # 解析技能根目录
        self.skills_root = self._resolve_skills_root(self.base_dir)
    
    def _resolve_skills_root(self, base_dir: Path) -> Path:
        """解析技能定义的根目录"""
        if base_dir.name in {"tools", "agents", "toolsets"} and base_dir.parent.name:
            return base_dir.parent
        return base_dir
    
    def set_watch_paths(self, paths: List[Path]) -> None:
        """设置监视路径"""
        self._watch_paths = paths
    
    def set_watch_filenames(self, filenames: set[str]) -> None:
        """设置监视文件名"""
        self._watch_filenames = filenames
    
    def _log_event(self, event: str, name: str = "", **fields: Any) -> None:
        """记录日志事件"""
        parts = [f"event={event}", f"kind={self.kind}"]
        if name:
            parts.append(f"name={name}")
        for key, value in fields.items():
            parts.append(f"{key}={value}")
        logger.info("[skills] " + " ".join(parts))
    
    def _reset_items(self) -> None:
        """重置技能项"""
        self._items = {}
        self._items_schema = []
    
    async def load_items(self) -> None:
        """从base_dir自动发现并加载技能定义
        
        注意：仅加载config配置文件，不导入handler代码（延迟加载）
        """
        async with self._reload_lock:
            self._reset_items()
            
            if not self.base_dir.exists():
                logger.warning(f"[skills] 目录不存在: {self.base_dir}")
                return
            
            self._discover_items_in_dir(self.base_dir, prefix="")
            
            # 保留统计数据
            active_names = set(self._items.keys())
            self._stats = {
                name: self._stats.get(name, SkillStats()) 
                for name in active_names
            }
            
            item_names = list(self._items.keys())
            logger.info(
                f"[{self.__class__.__name__}] 成功加载 {len(self._items_schema)} 个项目: "
                f"{', '.join(item_names)}"
            )
    
    def _discover_items_in_dir(self, parent_dir: Path, prefix: str = "") -> None:
        """递归发现目录中的技能项"""
        for item in parent_dir.iterdir():
            if item.is_dir() and not item.name.startswith("_"):
                self._register_item_from_dir(item, prefix=prefix)
    
    def _register_item_from_dir(self, item_dir: Path, prefix: str = "") -> None:
        """从特定目录解析并注册一个技能项
        
        查找目录下的config.json和handler.py，构造SkillItem
        
        Args:
            item_dir: 技能所在目录
            prefix: 技能名称前缀
        """
        config_path = item_dir / "config.json"
        handler_path = item_dir / "handler.py"
        
        if not config_path.exists() or not handler_path.exists():
            logger.debug(
                f"[skills] 目录 {item_dir} 缺少 config.json 或 handler.py，跳过"
            )
            return
        
        try:
            config = self._load_config(config_path)
            if not config:
                return
            
            item = self._build_skill_item(item_dir, config, handler_path, prefix)
            self._items[item.name] = item
            self._items_schema.append(item.config)
            self._stats.setdefault(item.name, SkillStats())
            
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    f"[{self.kind}加载] name={item.name} module={item.module_name} "
                    f"path={handler_path}"
                )
                logger.debug(
                    f"[{self.kind}配置] {item.name} config={json.dumps(config, ensure_ascii=False)}"
                )
        
        except Exception as e:
            logger.error(f"[skills] 从 {item_dir} 加载失败: {e}")
    
    def _load_config(self, config_path: Path) -> Optional[Dict[str, Any]]:
        """加载并验证配置文件"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            if not isinstance(config, dict) or "name" not in config.get("function", {}):
                logger.error(
                    f"[skills] 配置无效 {config_path.parent}: 缺少 function.name"
                )
                return None
            
            return dict(config)
        
        except Exception as e:
            logger.error(f"[skills] 加载配置文件失败 {config_path}: {e}")
            return None
    
    def _build_skill_item(
        self,
        item_dir: Path,
        config: Dict[str, Any],
        handler_path: Path,
        prefix: str,
    ) -> SkillItem:
        """构建技能项
        
        Args:
            item_dir: 技能目录
            config: 配置字典
            handler_path: 处理器路径
            prefix: 名称前缀
        
        Returns:
            SkillItem实例
        """
        # 计算模块名
        rel_path = item_dir.relative_to(self.skills_root)
        module_parts = list(rel_path.parts)
        if module_parts[-1] == "handler.py":
            module_parts[-1] = "handler"
        module_name = ".".join(module_parts)
        
        # 构造技能名
        skill_name = config.get("function", {}).get("name", "")
        if prefix:
            skill_name = f"{prefix}.{skill_name}"
        
        return SkillItem(
            name=skill_name,
            config=config,
            handler_path=handler_path,
            module_name=module_name,
            loaded=False,
            status=SkillStatus.LOADED,
        )
    
    async def _load_handler(self, item: SkillItem) -> Optional[Callable]:
        """延迟加载处理器
        
        Args:
            item: 技能项
        
        Returns:
            处理器函数或None
        """
        if item.loaded and item.handler:
            return item.handler
        
        try:
            # 添加skills_root到sys.path
            sys.path.insert(0, str(self.skills_root))
            
            # 动态导入模块
            spec = importlib.util.spec_from_file_location(
                item.module_name,
                item.handler_path,
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # 获取handler函数
                handler = getattr(module, "handler", None)
                if handler:
                    item.handler = handler
                    item.loaded = True
                    item.status = SkillStatus.LOADED
                    logger.debug(f"[skills] 成功加载handler: {item.name}")
                    return handler
            
            logger.error(f"[skills] 未找到handler函数: {item.name}")
            return None
        
        except Exception as e:
            logger.error(f"[skills] 加载handler失败 {item.name}: {e}")
            item.status = SkillStatus.ERROR
            return None
        
        finally:
            # 从sys.path移除
            if str(self.skills_root) in sys.path:
                sys.path.remove(str(self.skills_root))
    
    async def execute(
        self,
        name: str,
        args: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Any:
        """执行技能
        
        Args:
            name: 技能名称
            args: 调用参数
            context: 执行上下文
        
        Returns:
            执行结果
        
        Raises:
            KeyError: 技能不存在
            TimeoutError: 执行超时
        """
        item = self._items.get(name)
        if not item:
            raise KeyError(f"[skills] 技能不存在: {name}")
        
        # 延迟加载handler
        if not item.loaded:
            await self._load_handler(item)
        
        if not item.handler:
            raise RuntimeError(f"[skills] 技能handler未加载: {name}")
        
        start_time = time.time()
        
        try:
            # 超时保护
            result = await asyncio.wait_for(
                item.handler(args, context),
                timeout=self.timeout_seconds,
            )
            
            duration = time.time() - start_time
            self._stats[name].record_success(duration)
            
            return result
        
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            self._stats[name].record_failure(duration, "timeout")
            raise TimeoutError(f"[skills] 执行超时: {name}")
        
        except Exception as e:
            duration = time.time() - start_time
            self._stats[name].record_failure(duration, str(e))
            logger.error(f"[skills] 执行失败 {name}: {e}")
            raise
    
    def get_schema(self) -> List[Dict[str, Any]]:
        """获取所有技能的架构定义"""
        return self._items_schema.copy()
    
    def get_items(self) -> Dict[str, SkillItem]:
        """获取所有技能项"""
        return self._items.copy()
    
    def get_stats(self, name: Optional[str] = None) -> Union[Dict[str, SkillStats], SkillStats]:
        """获取统计数据
        
        Args:
            name: 技能名称，如果为None则返回所有
        
        Returns:
            单个技能的统计数据或所有统计数据
        """
        if name:
            return self._stats.get(name, SkillStats())
        return self._stats.copy()
    
    async def reload(self) -> None:
        """热重载所有技能"""
        logger.info(f"[skills] 开始热重载 {self.kind}...")
        
        # 停止文件监视
        await self._stop_file_watcher()
        
        # 重新加载
        await self.load_items()
        
        # 重新启动文件监视
        if self.enable_hot_reload:
            await self._start_file_watcher()
        
        logger.info(f"[skills] 热重载完成")
    
    async def _start_file_watcher(self) -> None:
        """启动文件监视器"""
        if self._watch_task and not self._watch_task.done():
            return
        
        self._watch_stop = asyncio.Event()
        self._watch_task = asyncio.create_task(self._file_watcher_loop())
        logger.info(f"[skills] 文件监视器已启动")
    
    async def _stop_file_watcher(self) -> None:
        """停止文件监视器"""
        if self._watch_stop:
            self._watch_stop.set()
        
        if self._watch_task:
            try:
                await asyncio.wait_for(self._watch_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._watch_task.cancel()
            
            self._watch_task = None
            self._watch_stop = None
        
        logger.info(f"[skills] 文件监视器已停止")
    
    async def _file_watcher_loop(self) -> None:
        """文件监视循环"""
        while not self._watch_stop.is_set():
            try:
                await asyncio.sleep(1.0)
                
                # 检测变更
                changed = await self._check_file_changes()
                
                if changed:
                    logger.info(f"[skills] 检测到文件变更，开始热重载...")
                    await self.load_items()
            
            except Exception as e:
                logger.error(f"[skills] 文件监视器错误: {e}")
    
    async def _check_file_changes(self) -> bool:
        """检查文件变更
        
        Returns:
            是否有变更
        """
        snapshot: Dict[str, tuple[int, int]] = {}
        changed = False
        
        for watch_path in self._watch_paths:
            if not watch_path.exists():
                continue
            
            for file_path in watch_path.rglob("*.py"):
                if file_path.suffix != ".py":
                    continue
                
                # 检查是否在监视文件名列表中
                if file_path.name not in self._watch_filenames:
                    continue
                
                try:
                    stat = file_path.stat()
                    key = str(file_path)
                    current = (stat.st_size, stat.st_mtime)
                    
                    if key in self._last_snapshot:
                        if self._last_snapshot[key] != current:
                            logger.debug(f"[skills] 文件变更: {key}")
                            changed = True
                    
                    snapshot[key] = current
                
                except OSError:
                    continue
        
        self._last_snapshot = snapshot
        return changed
    
    async def cleanup(self) -> None:
        """清理资源"""
        await self._stop_file_watcher()
        self._reset_items()


class ToolRegistry(BaseRegistry):
    """工具注册表
    
    继承BaseRegistry，专门用于管理工具
    """
    
    def __init__(
        self,
        tools_dir: Optional[Union[str, Path]] = None,
        enable_hot_reload: bool = True,
    ):
        """初始化工具注册表
        
        Args:
            tools_dir: 工具目录
            enable_hot_reload: 是否启用热重载
        """
        if tools_dir is None:
            tools_path = Path(__file__).parent / "skills" / "tools"
        else:
            tools_path = Path(tools_dir)
        
        super().__init__(
            tools_path,
            kind="tool",
            enable_hot_reload=enable_hot_reload,
        )
        
        self.toolsets_dir = self.base_dir.parent / "toolsets"
        
        if self.enable_hot_reload:
            asyncio.create_task(self._start_file_watcher())
    
    async def load_tools(self) -> None:
        """从tools目录发现并加载工具，同时也加载toolsets"""
        async with self._reload_lock:
            self._reset_items()
            
            # 1) tools目录
            if self.base_dir.exists():
                self._discover_items_in_dir(self.base_dir, prefix="")
            else:
                logger.warning(f"[tools] 目录不存在: {self.base_dir}")
            
            # 2) toolsets目录
            await self._load_toolsets_recursive()
            
            # 保留统计数据
            active_names = set(self._items.keys())
            self._stats = {
                name: self._stats.get(name, SkillStats())
                for name in active_names
            }
            
            self._log_tools_summary()
    
    async def _load_toolsets_recursive(self) -> None:
        """从toolsets目录发现并加载工具集"""
        if not self.toolsets_dir.exists():
            logger.debug(f"[tools] Toolsets目录不存在: {self.toolsets_dir}")
            return
        
        for category_dir in self.toolsets_dir.iterdir():
            if not category_dir.is_dir() or category_dir.name.startswith("_"):
                continue
            
            prefix = category_dir.name
            self._discover_items_in_dir(category_dir, prefix=prefix)
    
    def _log_tools_summary(self) -> None:
        """记录工具加载完成统计"""
        tool_names = list(self._items.keys())
        
        # 分类工具
        basic_tools = [name for name in tool_names if "." not in name]
        toolset_tools = [name for name in tool_names if "." in name]
        
        # 按类别分组工具集工具
        toolset_by_category: Dict[str, List[str]] = {}
        for name in toolset_tools:
            category = name.split(".")[0]
            toolset_by_category.setdefault(category, []).append(name)
        
        # 输出统计
        logger.info("=" * 60)
        logger.info("[ToolRegistry] 工具加载完成统计")
        logger.info(f"  - 基础工具 ({len(basic_tools)} 个): {', '.join(basic_tools) or '无'}")
        
        if toolset_by_category:
            logger.info(f"  - 工具集工具 ({len(toolset_tools)} 个):")
            for category, tools in sorted(toolset_by_category.items()):
                logger.info(f"    [{category}] ({len(tools)} 个): {', '.join(tools)}")
        
        logger.info(f"  - 总计: {len(tool_names)} 个工具")
        logger.info("=" * 60)


class AgentRegistry(BaseRegistry):
    """Agent注册表
    
    继承BaseRegistry，专门用于管理Agent
    """
    
    def __init__(
        self,
        agents_dir: Optional[Union[str, Path]] = None,
        enable_hot_reload: bool = True,
    ):
        """初始化Agent注册表
        
        Args:
            agents_dir: Agent目录
            enable_hot_reload: 是否启用热重载
        """
        if agents_dir is None:
            agents_path = Path(__file__).parent / "skills" / "agents"
        else:
            agents_path = Path(agents_dir)
        
        super().__init__(
            agents_path,
            kind="agent",
            enable_hot_reload=enable_hot_reload,
        )
        
        self.set_watch_filenames({"config.json", "handler.py", "intro.md"})
        
        if self.enable_hot_reload:
            asyncio.create_task(self._start_file_watcher())
    
    async def load_agents(self) -> None:
        """执行完整的Agent加载流程"""
        await self.load_items()
        await self._apply_agent_intros()
        self._log_agents_summary()
    
    async def _apply_agent_intros(self) -> None:
        """为每个已加载的Agent注入自述简介"""
        for name, item in self._items.items():
            agent_dir = self.base_dir / name
            if not agent_dir.exists():
                continue
            
            description = await self._load_agent_description(
                agent_dir,
                fallback=item.get_description(),
            )
            
            if description:
                item.config.setdefault("function", {})
                item.config["function"]["description"] = description
                logger.debug(f"[Agent简介] {name} intro_len={len(description)}")
    
    async def _load_agent_description(
        self,
        agent_dir: Path,
        fallback: str,
    ) -> str:
        """加载Agent描述
        
        Args:
            agent_dir: Agent目录
            fallback: 后备描述
        
        Returns:
            Agent描述文本
        """
        # 优先从intro.md读取
        intro_path = agent_dir / "intro.md"
        if intro_path.exists():
            try:
                with open(intro_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"[Agent] 读取intro.md失败 {agent_dir}: {e}")
        
        # 回退到配置中的描述
        return fallback
    
    def _log_agents_summary(self) -> None:
        """记录Agent加载完成统计"""
        agent_names = list(self._items.keys())
        if agent_names:
            logger.info("=" * 60)
            logger.info("[AgentRegistry] Agent加载完成统计")
            logger.info(f"  - 已加载Agents ({len(agent_names)} 个):")
            for name in sorted(agent_names):
                logger.info(f"    * {name}")
            logger.info("=" * 60)
    
    def get_agents_schema(self) -> List[Dict[str, Any]]:
        """获取所有Agent的架构定义列表"""
        return self.get_schema()
    
    async def execute_agent(
        self,
        agent_name: str,
        args: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """调用并执行特定的Agent
        
        Args:
            agent_name: Agent名称
            args: 调用参数
            context: 执行上下文
        
        Returns:
            Agent执行结果文本
        """
        return await self.execute(agent_name, args, context)


# 全局单例
_tool_registry: Optional[ToolRegistry] = None
_agent_registry: Optional[AgentRegistry] = None


def get_tool_registry(
    tools_dir: Optional[Union[str, Path]] = None,
) -> ToolRegistry:
    """获取工具注册表单例
    
    Args:
        tools_dir: 工具目录
    
    Returns:
        ToolRegistry实例
    """
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry(tools_dir)
    return _tool_registry


def get_agent_registry(
    agents_dir: Optional[Union[str, Path]] = None,
) -> AgentRegistry:
    """获取Agent注册表单例
    
    Args:
        agents_dir: Agent目录
    
    Returns:
        AgentRegistry实例
    """
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry(agents_dir)
    return _agent_registry

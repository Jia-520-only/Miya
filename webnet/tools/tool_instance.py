"""
通用工具架构
为所有工具提供稳定、独立、可维修、故障隔离的能力
"""

from typing import Dict, Any, Optional, Set, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging


logger = logging.getLogger(__name__)


class ToolHealthState(Enum):
    """工具健康状态"""
    HEALTHY = "healthy"         # 健康，正常运行
    DEGRADED = "degraded"       # 降级，有少量错误
    UNSTABLE = "unstable"       # 不稳定，频繁错误
    BROKEN = "broken"          # 损坏，已禁用


@dataclass
class ToolMetrics:
    """工具指标统计"""
    total_calls: int = 0                    # 总调用次数
    successful_calls: int = 0              # 成功次数
    failed_calls: int = 0                  # 失败次数
    last_success_time: Optional[datetime] = None  # 最后成功时间
    last_failure_time: Optional[datetime] = None  # 最后失败时间
    last_error_message: Optional[str] = None     # 最后错误信息

    # 滑动窗口统计（用于熔断）
    failure_count_in_window: int = 0       # 窗口内失败次数
    window_start_time: Optional[datetime] = None  # 窗口开始时间

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls

    @property
    def failure_rate(self) -> float:
        """失败率"""
        return 1.0 - self.success_rate


class ToolCircuitBreaker:
    """
    工具熔断器

    职责：
    1. 监控工具调用失败率
    2. 自动熔断故障工具
    3. 半开状态探测恢复
    4. 支持动态配置
    """

    # 熔断配置
    FAILURE_THRESHOLD = 3           # 失败次数阈值
    FAILURE_RATE_THRESHOLD = 0.5   # 失败率阈值
    RECOVERY_TIMEOUT = 60          # 恢复超时（秒）
    WINDOW_SIZE = 60               # 统计窗口（秒）

    class CircuitState(Enum):
        """熔断器状态"""
        CLOSED = "closed"         # 关闭（正常）
        OPEN = "open"             # 打开（熔断）
        HALF_OPEN = "half_open"   # 半开（探测）

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        self.state = self.CircuitState.CLOSED
        self.metrics = ToolMetrics()
        self.last_state_change = datetime.now()

    def should_allow_call(self) -> bool:
        """检查是否允许调用"""
        # 如果熔断器打开，检查是否可以进入半开状态
        if self.state == self.CircuitState.OPEN:
            time_since_change = (datetime.now() - self.last_state_change).total_seconds()
            if time_since_change >= self.RECOVERY_TIMEOUT:
                self._transition_to(self.CircuitState.HALF_OPEN)
                logger.info(f"[CircuitBreaker] {self.tool_name} 进入半开状态，尝试恢复")
                return True
            return False

        return True

    def record_success(self):
        """记录成功调用"""
        self.metrics.total_calls += 1
        self.metrics.successful_calls += 1
        self.metrics.last_success_time = datetime.now()

        # 半开状态下的成功调用
        if self.state == self.CircuitState.HALF_OPEN:
            self._transition_to(self.CircuitState.CLOSED)
            logger.info(f"[CircuitBreaker] {self.tool_name} 恢复正常，熔断器关闭")

    def record_failure(self, error: str):
        """记录失败调用"""
        self.metrics.total_calls += 1
        self.metrics.failed_calls += 1
        self.metrics.last_failure_time = datetime.now()
        self.metrics.last_error_message = error

        # 更新滑动窗口
        self._update_failure_window()

        # 检查是否需要熔断
        self._check_and_trip()

    def _update_failure_window(self):
        """更新失败滑动窗口"""
        now = datetime.now()

        # 初始化窗口
        if self.metrics.window_start_time is None:
            self.metrics.window_start_time = now
            self.metrics.failure_count_in_window = 1
            return

        # 检查窗口是否过期
        window_elapsed = (now - self.metrics.window_start_time).total_seconds()
        if window_elapsed >= self.WINDOW_SIZE:
            # 重置窗口
            self.metrics.window_start_time = now
            self.metrics.failure_count_in_window = 1
        else:
            # 累加失败次数
            self.metrics.failure_count_in_window += 1

    def _check_and_trip(self):
        """检查并触发熔断"""
        if self.state == self.CircuitState.OPEN:
            return

        # 检查失败次数阈值
        if self.metrics.failure_count_in_window >= self.FAILURE_THRESHOLD:
            self._transition_to(self.CircuitState.OPEN)
            logger.warning(
                f"[CircuitBreaker] {self.tool_name} 熔断器打开，"
                f"失败次数: {self.metrics.failure_count_in_window}"
            )
            return

        # 检查失败率阈值
        if self.metrics.total_calls >= 5 and self.metrics.failure_rate >= self.FAILURE_RATE_THRESHOLD:
            self._transition_to(self.CircuitState.OPEN)
            logger.warning(
                f"[CircuitBreaker] {self.tool_name} 熔断器打开，"
                f"失败率: {self.metrics.failure_rate:.2%}"
            )

    def _transition_to(self, new_state: CircuitState):
        """转换熔断器状态"""
        old_state = self.state
        self.state = new_state
        self.last_state_change = datetime.now()
        logger.debug(f"[CircuitBreaker] {self.tool_name} 状态转换: {old_state.value} -> {new_state.value}")

    def get_health_state(self) -> ToolHealthState:
        """获取健康状态"""
        if self.state == self.CircuitState.OPEN:
            return ToolHealthState.BROKEN

        if self.metrics.total_calls == 0:
            return ToolHealthState.HEALTHY

        # 根据失败率判断健康状态
        if self.metrics.failure_rate < 0.1:
            return ToolHealthState.HEALTHY
        elif self.metrics.failure_rate < 0.3:
            return ToolHealthState.DEGRADED
        elif self.metrics.failure_rate < 0.5:
            return ToolHealthState.UNSTABLE
        else:
            return ToolHealthState.BROKEN

    def reset(self):
        """重置熔断器"""
        self.state = self.CircuitState.CLOSED
        self.metrics = ToolMetrics()
        self.last_state_change = datetime.now()
        logger.info(f"[CircuitBreaker] {self.tool_name} 熔断器已重置")


class ToolInstance:
    """
    工具实例

    职责：
    1. 封装工具的所有状态和行为
    2. 提供实例级别的错误隔离
    3. 支持工具降级和恢复
    4. 提供工具健康监控
    """

    def __init__(self, tool_name: str, tool_class, tool_config: Dict[str, Any]):
        self.tool_name = tool_name
        self.tool_class = tool_class
        self.tool_config = tool_config

        # 工具实例（延迟加载）
        self._tool_instance: Optional[Any] = None

        # 熔断器
        self.circuit_breaker = ToolCircuitBreaker(tool_name)

        # 实例级别配置
        self.enabled: bool = True
        self.fallback_message: Optional[str] = None
        self.priority: int = 0  # 优先级，用于负载均衡

        # 创建时间
        self.created_at = datetime.now()
        self.last_used_at: Optional[datetime] = None

    @property
    def tool(self) -> Any:
        """获取工具实例（延迟加载）"""
        if self._tool_instance is None:
            try:
                self._tool_instance = self.tool_class()
                logger.debug(f"[ToolInstance] {self.tool_name} 工具实例已创建")
            except Exception as e:
                logger.error(f"[ToolInstance] {self.tool_name} 工具实例创建失败: {e}")
                raise
        return self._tool_instance

    @property
    def is_healthy(self) -> bool:
        """检查工具是否健康"""
        return self.circuit_breaker.get_health_state() != ToolHealthState.BROKEN

    @property
    def health_state(self) -> ToolHealthState:
        """获取健康状态"""
        return self.circuit_breaker.get_health_state()

    def should_execute(self) -> bool:
        """检查是否应该执行工具"""
        if not self.enabled:
            logger.debug(f"[ToolInstance] {self.tool_name} 已禁用")
            return False

        if not self.circuit_breaker.should_allow_call():
            logger.debug(f"[ToolInstance] {self.tool_name} 熔断器打开，拒绝调用")
            return False

        return True

    def record_success(self):
        """记录成功"""
        self.circuit_breaker.record_success()
        self.last_used_at = datetime.now()

    def record_failure(self, error: str):
        """记录失败"""
        self.circuit_breaker.record_failure(error)

    def get_metrics(self) -> ToolMetrics:
        """获取工具指标"""
        return self.circuit_breaker.metrics

    def reset(self):
        """重置工具状态"""
        self.circuit_breaker.reset()
        self.enabled = True
        logger.info(f"[ToolInstance] {self.tool_name} 已重置")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'tool_name': self.tool_name,
            'enabled': self.enabled,
            'health_state': self.health_state.value,
            'circuit_state': self.circuit_breaker.state.value,
            'metrics': {
                'total_calls': self.circuit_breaker.metrics.total_calls,
                'successful_calls': self.circuit_breaker.metrics.successful_calls,
                'failed_calls': self.circuit_breaker.metrics.failed_calls,
                'success_rate': f"{self.circuit_breaker.metrics.success_rate:.2%}",
                'last_success_time': self.circuit_breaker.metrics.last_success_time.isoformat() if self.circuit_breaker.metrics.last_success_time else None,
                'last_failure_time': self.circuit_breaker.metrics.last_failure_time.isoformat() if self.circuit_breaker.metrics.last_failure_time else None,
                'last_error_message': self.circuit_breaker.metrics.last_error_message,
            },
            'created_at': self.created_at.isoformat(),
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
        }

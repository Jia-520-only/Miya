"""
Miya 数据库连接池 - 性能优化模块
================================

该模块提供数据库连接池功能,减少连接建立/关闭开销。
支持多种数据库类型(MySQL、PostgreSQL、SQLite等)。

设计目标:
- 减少数据库连接开销 15-25%
- 支持连接复用和自动回收
- 连接健康检查和重连机制
- 线程安全的并发访问
"""

import asyncio
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


@dataclass
class PoolConfig:
    """连接池配置"""

    min_connections: int = 2
    max_connections: int = 10
    connection_timeout: float = 5.0
    idle_timeout: float = 300.0  # 5分钟
    max_lifetime: float = 3600.0  # 1小时
    health_check_interval: float = 60.0
    enable_health_check: bool = True


@dataclass
class ConnectionWrapper:
    """连接包装器"""

    connection: Any
    created_at: float
    last_used_at: float
    is_busy: bool = False
    health_status: str = "healthy"


class ConnectionPool:
    """通用数据库连接池"""

    def __init__(self, connection_factory: Type[Any], config: Optional[PoolConfig] = None, **connection_params):
        self.connection_factory = connection_factory
        self.config = config or PoolConfig()
        self.connection_params = connection_params

        # 连接池
        self._connections: List[ConnectionWrapper] = []
        self._available_connections: Queue = Queue()
        self._busy_connections: Dict[int, ConnectionWrapper] = {}

        # 统计信息
        self.stats = {
            "created": 0,
            "reused": 0,
            "closed": 0,
            "health_checks": 0,
            "failed_checks": 0,
            "max_concurrent": 0,
        }

        # 锁
        self._lock = threading.RLock()
        self._shutdown = False

        logger.info(f"[连接池] 初始化完成, min={self.config.min_connections}, max={self.config.max_connections}")

    async def initialize(self):
        """初始化连接池(创建最小连接数)"""
        logger.info(f"[连接池] 开始初始化, 创建{self.config.min_connections}个连接")

        for _ in range(self.config.min_connections):
            try:
                wrapper = await self._create_connection()
                if wrapper:
                    self._available_connections.put(wrapper)
            except Exception as e:
                logger.error(f"[连接池] 初始化连接失败: {e}")

        logger.info(f"[连接池] 初始化完成, 可用连接数={self._available_connections.qsize()}")

    async def _create_connection(self) -> Optional[ConnectionWrapper]:
        """创建新连接"""
        if self._shutdown:
            return None

        try:
            # 调用连接工厂创建连接
            if asyncio.iscoroutinefunction(self.connection_factory):
                connection = await self.connection_factory(**self.connection_params)
            else:
                connection = self.connection_factory(**self.connection_params)

            wrapper = ConnectionWrapper(
                connection=connection,
                created_at=time.time(),
                last_used_at=time.time(),
                is_busy=False,
                health_status="healthy",
            )

            with self._lock:
                self.stats["created"] += 1
                self._connections.append(wrapper)

            logger.debug("[连接池] 创建新连接")
            return wrapper

        except Exception as e:
            logger.error(f"[连接池] 创建连接失败: {e}")
            return None

    async def get_connection(self, timeout: Optional[float] = None) -> Optional[Any]:
        """获取连接(带超时)"""
        if self._shutdown:
            raise RuntimeError("连接池已关闭")

        timeout = timeout or self.config.connection_timeout
        start_time = time.time()

        try:
            # 尝试从可用队列获取连接
            wrapper = self._available_connections.get(timeout=timeout)

            # 检查连接是否健康
            if self.config.enable_health_check and not await self._check_health(wrapper):
                logger.warning("[连接池] 连接不健康, 重新创建")
                await self._close_connection(wrapper)
                wrapper = await self._create_connection()
                if not wrapper:
                    return None

            # 标记为忙碌
            with self._lock:
                wrapper.is_busy = True
                wrapper.last_used_at = time.time()
                self._busy_connections[id(wrapper.connection)] = wrapper
                self.stats["reused"] += 1
                self.stats["max_concurrent"] = max(self.stats["max_concurrent"], len(self._busy_connections))

            logger.debug("[连接池] 获取连接成功")
            return wrapper.connection

        except Empty:
            # 队列为空,尝试创建新连接
            logger.debug("[连接池] 无可用连接, 尝试创建新连接")

            with self._lock:
                if len(self._connections) < self.config.max_connections:
                    wrapper = await self._create_connection()
                    if wrapper:
                        wrapper.is_busy = True
                        wrapper.last_used_at = time.time()
                        self._busy_connections[id(wrapper.connection)] = wrapper
                        return wrapper.connection

            # 等待其他连接释放
            elapsed = time.time() - start_time
            remaining_timeout = timeout - elapsed
            if remaining_timeout > 0:
                wrapper = self._available_connections.get(timeout=remaining_timeout)
                wrapper.is_busy = True
                wrapper.last_used_at = time.time()
                self._busy_connections[id(wrapper.connection)] = wrapper
                return wrapper.connection

            logger.error(f"[连接池] 获取连接超时: {timeout}s")
            return None

    async def return_connection(self, connection: Any):
        """归还连接"""
        connection_id = id(connection)

        with self._lock:
            if connection_id not in self._busy_connections:
                logger.warning("[连接池] 归还了不存在的连接")
                return

            wrapper = self._busy_connections.pop(connection_id)
            wrapper.is_busy = False
            wrapper.last_used_at = time.time()

        # 检查是否需要关闭连接(超时或超寿命)
        now = time.time()
        if now - wrapper.created_at > self.config.max_lifetime or now - wrapper.last_used_at > self.config.idle_timeout:
            await self._close_connection(wrapper)
            logger.debug("[连接池] 连接已超时,关闭并重新创建")

            # 如果低于最小连接数,创建新连接
            if self._available_connections.qsize() < self.config.min_connections:
                new_wrapper = await self._create_connection()
                if new_wrapper:
                    self._available_connections.put(new_wrapper)
        else:
            self._available_connections.put(wrapper)

        logger.debug("[连接池] 连接已归还")

    async def _check_health(self, wrapper: ConnectionWrapper) -> bool:
        """检查连接健康状态"""
        try:
            # 简单的健康检查(根据具体数据库类型实现)
            conn = wrapper.connection

            # 检查是否有ping方法
            if hasattr(conn, "ping"):
                if asyncio.iscoroutinefunction(conn.ping):
                    await conn.ping()
                else:
                    conn.ping()

            # 检查是否有execute方法(SQLite/PostgreSQL)
            elif hasattr(conn, "execute"):
                if asyncio.iscoroutinefunction(conn.execute):
                    await conn.execute("SELECT 1")
                else:
                    conn.execute("SELECT 1")

            with self._lock:
                self.stats["health_checks"] += 1
            return True

        except Exception as e:
            logger.warning(f"[连接池] 健康检查失败: {e}")
            with self._lock:
                self.stats["failed_checks"] += 1
            return False

    async def _close_connection(self, wrapper: ConnectionWrapper):
        """关闭连接"""
        try:
            conn = wrapper.connection

            if asyncio.iscoroutinefunction(conn.close):
                await conn.close()
            else:
                conn.close()

            with self._lock:
                self.stats["closed"] += 1
                if wrapper in self._connections:
                    self._connections.remove(wrapper)

            logger.debug("[连接池] 连接已关闭")

        except Exception as e:
            logger.error(f"[连接池] 关闭连接失败: {e}")

    async def health_check_task(self):
        """定期健康检查任务"""
        logger.info("[连接池] 健康检查任务启动")

        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.health_check_interval)

                with self._lock:
                    wrappers = list(self._connections)

                for wrapper in wrappers:
                    if not wrapper.is_busy:
                        is_healthy = await self._check_health(wrapper)
                        wrapper.health_status = "healthy" if is_healthy else "unhealthy"

                        if not is_healthy:
                            logger.warning("[连接池] 发现不健康连接,关闭并重新创建")
                            await self._close_connection(wrapper)

                            # 创建新连接
                            new_wrapper = await self._create_connection()
                            if new_wrapper:
                                self._available_connections.put(new_wrapper)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[连接池] 健康检查任务错误: {e}")

        logger.info("[连接池] 健康检查任务停止")

    async def shutdown(self):
        """关闭连接池"""
        logger.info("[连接池] 开始关闭连接池")
        self._shutdown = True

        # 关闭所有连接
        with self._lock:
            wrappers = list(self._connections)

        for wrapper in wrappers:
            await self._close_connection(wrapper)

        self._connections.clear()
        self._busy_connections.clear()

        # 清空队列
        while not self._available_connections.empty():
            try:
                self._available_connections.get_nowait()
            except Empty:
                break

        logger.info("[连接池] 连接池已关闭")

    @contextmanager
    def get_connection_context(self):
        """获取连接的上下文管理器(同步)"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            connection = loop.run_until_complete(self.get_connection())
            try:
                yield connection
            finally:
                loop.run_until_complete(self.return_connection(connection))
        finally:
            loop.close()

    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        with self._lock:
            return {
                **self.stats,
                "total_connections": len(self._connections),
                "available_connections": self._available_connections.qsize(),
                "busy_connections": len(self._busy_connections),
            }

    def clear_stats(self):
        """清空统计信息"""
        with self._lock:
            self.stats = {
                "created": 0,
                "reused": 0,
                "closed": 0,
                "health_checks": 0,
                "failed_checks": 0,
                "max_concurrent": 0,
            }


# SQLite连接池
class SQLiteConnectionPool(ConnectionPool):
    """SQLite连接池"""

    def __init__(self, db_path: str, config: Optional[PoolConfig] = None):
        import sqlite3

        def create_connection(db_path: str):
            return sqlite3.connect(db_path, check_same_thread=False)

        super().__init__(connection_factory=lambda: create_connection(db_path), config=config)


# MySQL连接池(使用aiomysql)
class MySQLConnectionPool(ConnectionPool):
    """MySQL连接池"""

    def __init__(
        self, host: str, port: int, user: str, password: str, database: str, config: Optional[PoolConfig] = None
    ):
        import aiomysql

        async def create_connection(**kwargs):
            return await aiomysql.connect(**kwargs)

        super().__init__(
            connection_factory=create_connection,
            config=config,
            host=host,
            port=port,
            user=user,
            password=password,
            db=database,
        )


# PostgreSQL连接池(使用asyncpg)
class PostgreSQLConnectionPool(ConnectionPool):
    """PostgreSQL连接池"""

    def __init__(
        self, host: str, port: int, user: str, password: str, database: str, config: Optional[PoolConfig] = None
    ):
        import asyncpg

        async def create_connection(**kwargs):
            return await asyncpg.connect(**kwargs)

        super().__init__(
            connection_factory=create_connection,
            config=config,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )


# 全局连接池管理器
_global_pools: Dict[str, ConnectionPool] = {}


def register_pool(name: str, pool: ConnectionPool):
    """注册连接池"""
    _global_pools[name] = pool
    logger.info(f"[连接池] 注册连接池: {name}")


def get_pool(name: str) -> Optional[ConnectionPool]:
    """获取连接池"""
    return _global_pools.get(name)


async def shutdown_all_pools():
    """关闭所有连接池"""
    logger.info(f"[连接池] 关闭所有连接池, 数量={len(_global_pools)}")

    for name, pool in _global_pools.items():
        try:
            await pool.shutdown()
        except Exception as e:
            logger.error(f"[连接池] 关闭连接池失败: {name}, 错误: {e}")

    _global_pools.clear()


# 示例使用
if __name__ == "__main__":

    async def test_sqlite_pool():

        # 创建SQLite连接池
        pool = SQLiteConnectionPool("test.db", PoolConfig(min_connections=2, max_connections=5))

        # 初始化
        await pool.initialize()

        # 获取连接
        conn = await pool.get_connection()
        print(f"获取连接: {conn}")

        # 执行查询
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        print(f"查询结果: {result}")

        # 归还连接
        await pool.return_connection(conn)

        # 打印统计
        stats = pool.get_stats()
        print(f"统计: {stats}")

        # 关闭
        await pool.shutdown()

    asyncio.run(test_sqlite_pool())

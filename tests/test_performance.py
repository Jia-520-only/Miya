"""
弥娅系统性能压力测试
测试系统在高负载情况下的性能表现
"""
import asyncio
import time
import statistics
import unittest
import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent_manager import AgentManager, TaskStep
from memory.memory_system import MemorySystem


class PerformanceTestResult:
    """性能测试结果"""
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.execution_times: List[float] = []
        self.success_count = 0
        self.failure_count = 0
        self.errors: List[str] = []

    def add_result(self, execution_time: float, success: bool, error: str = None):
        """添加测试结果"""
        self.execution_times.append(execution_time)
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
            if error:
                self.errors.append(error)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.execution_times:
            return {
                "test_name": self.test_name,
                "total_runs": 0,
                "success_rate": 0,
                "avg_time": 0,
                "min_time": 0,
                "max_time": 0,
                "median_time": 0,
                "p95_time": 0
            }
        
        return {
            "test_name": self.test_name,
            "total_runs": len(self.execution_times),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_count / len(self.execution_times) * 100,
            "avg_time": statistics.mean(self.execution_times),
            "min_time": min(self.execution_times),
            "max_time": max(self.execution_times),
            "median_time": statistics.median(self.execution_times),
            "p95_time": self._percentile(95),
            "errors": self.errors[:5]  # 只保留前5个错误
        }

    def _percentile(self, p: float) -> float:
        """计算百分位数"""
        sorted_times = sorted(self.execution_times)
        k = (len(sorted_times) - 1) * (p / 100)
        f = int(k)
        c = k - f
        
        if f == len(sorted_times) - 1:
            return sorted_times[-1]
        
        return sorted_times[f] + c * (sorted_times[f + 1] - sorted_times[f])


class PerformanceTests(unittest.TestCase):
    """性能压力测试"""

    def setUp(self):
        """测试前准备"""
        self.agent_manager = AgentManager(config={"max_steps": 100})
        self.memory_system = MemorySystem()
        self.results: Dict[str, PerformanceTestResult] = {}

    def tearDown(self):
        """测试后清理"""
        self._print_performance_summary()

    def _print_performance_summary(self):
        """打印性能测试摘要"""
        print("\n" + "=" * 80)
        print("性能测试摘要")
        print("=" * 80)
        
        for test_name, result in self.results.items():
            stats = result.get_stats()
            print(f"\n【{test_name}】")
            print(f"  总运行次数: {stats['total_runs']}")
            print(f"  成功/失败: {stats['success_count']}/{stats['failure_count']}")
            print(f"  成功率: {stats['success_rate']:.2f}%")
            print(f"  平均耗时: {stats['avg_time']:.4f}s")
            print(f"  最小/最大: {stats['min_time']:.4f}s / {stats['max_time']:.4f}s")
            print(f"  中位数: {stats['median_time']:.4f}s")
            print(f"  P95: {stats['p95_time']:.4f}s")
            
            if stats['errors']:
                print(f"  错误示例: {stats['errors']}")
        
        print("\n" + "=" * 80)

    async def _task_creation_stress_test(self, num_tasks: int = 1000):
        """任务创建压力测试"""
        result = PerformanceTestResult("任务创建压力测试")
        
        for i in range(num_tasks):
            start_time = time.time()
            try:
                await self.agent_manager.create_task(
                    task_id=f"stress_task_{i}",
                    purpose=f"Stress test task {i}"
                )
                execution_time = time.time() - start_time
                result.add_result(execution_time, True)
            except Exception as e:
                execution_time = time.time() - start_time
                result.add_result(execution_time, False, str(e))
        
        self.results[result.test_name] = result
        return result

    def test_task_creation_performance(self):
        """测试任务创建性能"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(self._task_creation_stress_test(100))
        stats = result.get_stats()
        
        # 断言性能指标
        self.assertGreater(stats['success_rate'], 99, "任务创建成功率应该大于99%")
        self.assertLess(stats['avg_time'], 0.01, "平均任务创建时间应该小于10ms")
        
        loop.close()

    async def _step_addition_stress_test(self, num_steps: int = 500):
        """步骤添加压力测试"""
        result = PerformanceTestResult("步骤添加压力测试")
        
        # 创建测试任务
        await self.agent_manager.create_task("step_stress_task", "stress test")
        
        for i in range(num_steps):
            start_time = time.time()
            try:
                step = TaskStep(
                    step_id=f"step_{i}",
                    task_id="step_stress_task",
                    purpose="test",
                    content=f"Step content {i}",
                    output=f"Output {i}"
                )
                await self.agent_manager.add_task_step("step_stress_task", step)
                execution_time = time.time() - start_time
                result.add_result(execution_time, True)
            except Exception as e:
                execution_time = time.time() - start_time
                result.add_result(execution_time, False, str(e))
        
        self.results[result.test_name] = result
        return result

    def test_step_addition_performance(self):
        """测试步骤添加性能"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(self._step_addition_stress_test(200))
        stats = result.get_stats()
        
        self.assertGreater(stats['success_rate'], 98, "步骤添加成功率应该大于98%")
        self.assertLess(stats['avg_time'], 0.05, "平均步骤添加时间应该小于50ms")
        
        loop.close()

    async def _memory_query_stress_test(self, num_queries: int = 1000):
        """记忆查询压力测试"""
        result = PerformanceTestResult("记忆查询压力测试")
        
        # 预填充一些记忆
        for i in range(100):
            self.memory_system.add_memory(
                content=f"Test memory content {i}",
                importance=0.5
            )
        
        for i in range(num_queries):
            start_time = time.time()
            try:
                self.memory_system.query_memory(query=f"test {i}", limit=10)
                execution_time = time.time() - start_time
                result.add_result(execution_time, True)
            except Exception as e:
                execution_time = time.time() - start_time
                result.add_result(execution_time, False, str(e))
        
        self.results[result.test_name] = result
        return result

    def test_memory_query_performance(self):
        """测试记忆查询性能"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(self._memory_query_stress_test(500))
        stats = result.get_stats()
        
        self.assertGreater(stats['success_rate'], 99, "记忆查询成功率应该大于99%")
        self.assertLess(stats['p95_time'], 0.1, "P95查询时间应该小于100ms")
        
        loop.close()

    async def _concurrent_task_test(self, num_concurrent: int = 50):
        """并发任务测试"""
        result = PerformanceTestResult("并发任务测试")
        
        async def create_and_process_task(task_id: str):
            start_time = time.time()
            try:
                await self.agent_manager.create_task(task_id, f"Concurrent task {task_id}")
                
                # 添加一些步骤
                for i in range(5):
                    step = TaskStep(
                        step_id=f"{task_id}_step_{i}",
                        task_id=task_id,
                        purpose="test",
                        content=f"Step {i}",
                        output=f"Output {i}"
                    )
                    await self.agent_manager.add_task_step(task_id, step)
                
                execution_time = time.time() - start_time
                return execution_time, True, None
            except Exception as e:
                execution_time = time.time() - start_time
                return execution_time, False, str(e)
        
        # 并发执行多个任务
        tasks = [create_and_process_task(f"concurrent_{i}") for i in range(num_concurrent)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for r in results:
            if isinstance(r, Exception):
                result.add_result(0, False, str(r))
            else:
                execution_time, success, error = r
                result.add_result(execution_time, success, error)
        
        self.results[result.test_name] = result
        return result

    def test_concurrent_performance(self):
        """测试并发性能"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(self._concurrent_task_test(30))
        stats = result.get_stats()
        
        self.assertGreater(stats['success_rate'], 95, "并发任务成功率应该大于95%")
        self.assertLess(stats['p95_time'], 1.0, "P95任务完成时间应该小于1秒")
        
        loop.close()

    async def _memory_compression_test(self, num_memories: int = 1000):
        """记忆压缩性能测试"""
        result = PerformanceTestResult("记忆压缩性能测试")
        
        # 创建测试任务
        await self.agent_manager.create_task("compression_test", "test")
        
        for i in range(num_memories):
            start_time = time.time()
            try:
                step = TaskStep(
                    step_id=f"step_{i}",
                    task_id="compression_test",
                    purpose="test",
                    content=f"Memory content {i} " * 10,  # 较长的内容
                    output=f"Output {i}"
                )
                await self.agent_manager.add_task_step("compression_test", step)
                execution_time = time.time() - start_time
                result.add_result(execution_time, True)
            except Exception as e:
                execution_time = time.time() - start_time
                result.add_result(execution_time, False, str(e))
        
        self.results[result.test_name] = result
        return result

    def test_compression_performance(self):
        """测试记忆压缩性能"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 设置较小的压缩阈值
        self.agent_manager.compression_threshold = 50
        self.agent_manager.keep_last_steps = 10
        
        result = loop.run_until_complete(self._memory_compression_test(200))
        stats = result.get_stats()
        
        self.assertGreater(stats['success_rate'], 98, "记忆压缩成功率应该大于98%")
        
        # 验证压缩效果
        steps_count = len(self.agent_manager.task_steps.get("compression_test", []))
        self.assertLessEqual(
            steps_count,
            self.agent_manager.keep_last_steps * 2,  # 允许一定的余量
            "压缩后步骤数量应该显著减少"
        )
        
        loop.close()

    async def _session_memory_stress_test(self, num_sessions: int = 100):
        """会话记忆压力测试"""
        result = PerformanceTestResult("会话记忆压力测试")
        
        for i in range(num_sessions):
            start_time = time.time()
            try:
                session_id = f"session_{i}"
                await self.agent_manager.create_task(
                    task_id=f"task_{i}",
                    purpose=f"Task {i}",
                    session_id=session_id
                )
                
                # 添加一些会话记忆
                self.agent_manager.update_session_memory(
                    session_id,
                    {"key_fact": f"Fact {i}"}
                )
                
                execution_time = time.time() - start_time
                result.add_result(execution_time, True)
            except Exception as e:
                execution_time = time.time() - start_time
                result.add_result(execution_time, False, str(e))
        
        self.results[result.test_name] = result
        return result

    def test_session_memory_performance(self):
        """测试会话记忆性能"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(self._session_memory_stress_test(50))
        stats = result.get_stats()
        
        self.assertGreater(stats['success_rate'], 99, "会话记忆操作成功率应该大于99%")
        self.assertLess(stats['avg_time'], 0.02, "平均会话操作时间应该小于20ms")
        
        loop.close()

    def test_statistics_retrieval_performance(self):
        """测试统计信息获取性能"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 创建一些任务
        loop.run_until_complete(
            asyncio.gather(*[
                self.agent_manager.create_task(f"stat_task_{i}", f"Task {i}")
                for i in range(100)
            ])
        )
        
        result = PerformanceTestResult("统计信息获取性能测试")
        
        for i in range(1000):
            start_time = time.time()
            try:
                stats = self.agent_manager.get_statistics()
                execution_time = time.time() - start_time
                
                # 验证统计信息结构
                self.assertIn("total_tasks", stats)
                self.assertIn("active_tasks", stats)
                
                result.add_result(execution_time, True)
            except Exception as e:
                execution_time = time.time() - start_time
                result.add_result(execution_time, False, str(e))
        
        self.results[result.test_name] = result
        stats = result.get_stats()
        
        self.assertGreater(stats['success_rate'], 99, "统计获取成功率应该大于99%")
        self.assertLess(stats['p95_time'], 0.01, "P95统计获取时间应该小于10ms")
        
        loop.close()

    async def _large_data_handling_test(self, data_size: int = 100000):
        """大数据处理测试"""
        result = PerformanceTestResult("大数据处理性能测试")
        
        # 创建大数据
        large_data = "x" * data_size
        
        for i in range(50):
            start_time = time.time()
            try:
                step = TaskStep(
                    step_id=f"large_step_{i}",
                    task_id="large_data_test",
                    purpose="test",
                    content=large_data,
                    output=large_data
                )
                await self.agent_manager.add_task_step("large_data_test", step)
                execution_time = time.time() - start_time
                result.add_result(execution_time, True)
            except Exception as e:
                execution_time = time.time() - start_time
                result.add_result(execution_time, False, str(e))
        
        self.results[result.test_name] = result
        return result

    def test_large_data_performance(self):
        """测试大数据处理性能"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self.agent_manager.create_task("large_data_test", "test"))
        result = loop.run_until_complete(self._large_data_handling_test(50000))
        stats = result.get_stats()
        
        self.assertGreater(stats['success_rate'], 95, "大数据处理成功率应该大于95%")
        
        loop.close()


def run_performance_tests():
    """运行所有性能测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试方法
    suite.addTests(loader.loadTestsFromTestCase(PerformanceTests))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    result = run_performance_tests()
    sys.exit(0 if result.wasSuccessful() else 1)

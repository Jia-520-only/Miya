"""
自动化测试框架
运行所有测试套件并生成报告
"""
from typing import Dict, List
from dataclasses import dataclass
import time


@dataclass
class TestResult:
    """测试结果"""
    suite_name: str
    passed: int
    failed: int
    duration: float
    details: List[Dict]


class TestSuite:
    """测试套件基类"""

    async def run(self) -> TestResult:
        """运行测试"""
        raise NotImplementedError


class AutomatedTestFramework:
    """自动化测试框架"""

    def __init__(self):
        self.test_suites = {}

    def register_suite(self, name: str, suite: TestSuite):
        """注册测试套件"""
        self.test_suites[name] = suite

    async def run_all_tests(self) -> Dict:
        """运行所有测试"""
        results = {}
        total_passed = 0
        total_failed = 0
        total_duration = 0.0

        for name, suite in self.test_suites.items():
            print(f"运行测试套件：{name}...")
            start_time = time.time()

            result = await suite.run()

            duration = time.time() - start_time
            results[name] = {
                'passed': result.passed,
                'failed': result.failed,
                'duration': duration,
                'details': result.details
            }

            total_passed += result.passed
            total_failed += result.failed
            total_duration += duration

            print(f"  通过：{result.passed}，失败：{result.failed}")

        # 生成报告
        report = self._generate_report(results, total_passed, total_failed, total_duration)

        return {
            'results': results,
            'summary': {
                'total_passed': total_passed,
                'total_failed': total_failed,
                'total_tests': total_passed + total_failed,
                'success_rate': round(total_passed / (total_passed + total_failed), 3)
                    if (total_passed + total_failed) > 0 else 0,
                'total_duration': total_duration
            },
            'report': report
        }

    def _generate_report(self, results: Dict, passed: int, failed: int, duration: float) -> str:
        """生成测试报告"""
        lines = [
            "=" * 60,
            "        自动化测试报告",
            "=" * 60,
            "",
            f"执行时间：{duration:.2f}秒",
            f"测试总数：{passed + failed}",
            f"通过：{passed}",
            f"失败：{failed}",
            f"成功率：{passed / (passed + failed):.2%}" if (passed + failed) > 0 else "无测试",
            "",
            "=" * 60,
            "        详细结果",
            "=" * 60,
            ""
        ]

        for name, result in results.items():
            lines.extend([
                f"【{name}】",
                f"  通过：{result['passed']}",
                f"  失败：{result['failed']}",
                f"  耗时：{result['duration']:.2f}秒",
                ""
            ])

        lines.append("=" * 60)

        return "\n".join(lines)

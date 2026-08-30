"""
人格微调A/B测试
进行人格参数的A/B测试
"""
from typing import Dict, List, Optional
from datetime import datetime
import uuid


class ABTest:
    """A/B测试"""

    def __init__(self):
        self.tests = {}  # test_id -> test_data
        self.test_results = {}

    def create_test(self, name: str, control_params: Dict,
                    variant_params: Dict, config: Dict = None) -> str:
        """
        创建A/B测试

        Returns:
            测试ID
        """
        test_id = str(uuid.uuid4())
        test = {
            'test_id': test_id,
            'name': name,
            'control': control_params,  # 对照组参数
            'variant': variant_params,   # 变体参数
            'config': config or {},
            'status': 'pending',
            'created_at': datetime.now(),
            'started_at': None,
            'ended_at': None
        }

        self.tests[test_id] = test
        return test_id

    def start_test(self, test_id: str) -> bool:
        """启动测试"""
        if test_id not in self.tests:
            return False

        test = self.tests[test_id]
        test['status'] = 'running'
        test['started_at'] = datetime.now()
        return True

    def end_test(self, test_id: str) -> bool:
        """结束测试"""
        if test_id not in self.tests:
            return False

        test = self.tests[test_id]
        test['status'] = 'ended'
        test['ended_at'] = datetime.now()
        return True

    def record_result(self, test_id: str, group: str,
                      user_id: str, metrics: Dict) -> bool:
        """
        记录测试结果

        Args:
            test_id: 测试ID
            group: 'control' 或 'variant'
            user_id: 用户ID
            metrics: 指标字典
        """
        if test_id not in self.tests:
            return False

        if group not in ['control', 'variant']:
            return False

        if test_id not in self.test_results:
            self.test_results[test_id] = {'control': [], 'variant': []}

        result = {
            'user_id': user_id,
            'metrics': metrics,
            'timestamp': datetime.now()
        }

        self.test_results[test_id][group].append(result)
        return True

    def analyze_test(self, test_id: str) -> Dict:
        """分析测试结果"""
        if test_id not in self.tests or test_id not in self.test_results:
            return {'error': 'Test not found or no results'}

        control_results = self.test_results[test_id]['control']
        variant_results = self.test_results[test_id]['variant']

        # 计算各指标的平均值
        control_metrics = self._calculate_average_metrics(control_results)
        variant_metrics = self._calculate_average_metrics(variant_results)

        # 计算提升
        improvements = {}
        for key in control_metrics:
            if key in variant_metrics:
                if control_metrics[key] > 0:
                    improvement = (variant_metrics[key] - control_metrics[key]) / control_metrics[key] * 100
                    improvements[key] = round(improvement, 2)

        # 确定赢家
        winner = 'control'
        if any(imp > 0 for imp in improvements.values()):
            winner = 'variant' if sum(imp for imp in improvements.values() if imp > 0) > sum(abs(imp) for imp in improvements.values() if imp < 0) else 'control'

        return {
            'test_id': test_id,
            'control_count': len(control_results),
            'variant_count': len(variant_results),
            'control_metrics': control_metrics,
            'variant_metrics': variant_metrics,
            'improvements': improvements,
            'winner': winner
        }

    def _calculate_average_metrics(self, results: List[Dict]) -> Dict:
        """计算平均指标"""
        if not results:
            return {}

        metrics_sums = {}
        for result in results:
            for key, value in result['metrics'].items():
                if isinstance(value, (int, float)):
                    metrics_sums[key] = metrics_sums.get(key, 0) + value

        averages = {
            key: value / len(results)
            for key, value in metrics_sums.items()
        }

        return averages

    def get_test(self, test_id: str) -> Optional[Dict]:
        """获取测试信息"""
        test = self.tests.get(test_id)
        if not test:
            return None

        test_copy = test.copy()
        # 添加结果统计
        if test_id in self.test_results:
            test_copy['result_counts'] = {
                'control': len(self.test_results[test_id]['control']),
                'variant': len(self.test_results[test_id]['variant'])
            }

        return test_copy

    def get_all_tests(self, status: str = None) -> List[Dict]:
        """获取所有测试"""
        tests = list(self.tests.values())

        if status:
            tests = [t for t in tests if t['status'] == status]

        return tests

    def get_test_stats(self) -> Dict:
        """获取测试统计"""
        total = len(self.tests)
        running = len(self.get_all_tests('running'))
        ended = len(self.get_all_tests('ended'))

        return {
            'total_tests': total,
            'running': running,
            'ended': ended,
            'with_results': len(self.test_results)
        }

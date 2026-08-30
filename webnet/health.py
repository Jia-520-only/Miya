"""
健康子网
处理健康相关事务
"""
from typing import Dict, List


class HealthNet:
    """健康子网"""

    def __init__(self):
        self.net_id = 'health_net'
        self.capabilities = [
            'health_tracking',
            'exercise_reminder',
            'diet_suggestion'
        ]

        # 健康数据
        self.health_records = []
        self.vital_signs = {}
        self.health_goals = {}

    def record_vital(self, vital_type: str, value: float, timestamp: str = None) -> bool:
        """记录生命体征"""
        if not timestamp:
            from datetime import datetime
            timestamp = datetime.now().isoformat()

        record = {
            'type': vital_type,
            'value': value,
            'timestamp': timestamp
        }
        self.health_records.append(record)

        # 更新最新值
        self.vital_signs[vital_type] = {
            'value': value,
            'timestamp': timestamp
        }

        return True

    def get_vital(self, vital_type: str) -> Dict:
        """获取生命体征"""
        return self.vital_signs.get(vital_type, {})

    def get_health_records(self, vital_type: str = None, limit: int = 10) -> List[Dict]:
        """获取健康记录"""
        records = self.health_records

        if vital_type:
            records = [r for r in records if r.get('type') == vital_type]

        # 返回最近的记录
        return records[-limit:] if records else []

    def set_health_goal(self, goal_type: str, target: float) -> None:
        """设置健康目标"""
        self.health_goals[goal_type] = target

    def get_health_goal(self, goal_type: str) -> float:
        """获取健康目标"""
        return self.health_goals.get(goal_type)

    def check_goal_progress(self, goal_type: str) -> Dict:
        """检查目标进度"""
        target = self.health_goals.get(goal_type)
        if not target:
            return {'error': 'Goal not found'}

        current = self.vital_signs.get(goal_type, {}).get('value', 0)
        progress = (current / target) * 100 if target > 0 else 0

        return {
            'goal_type': goal_type,
            'target': target,
            'current': current,
            'progress': round(progress, 2)
        }

    def analyze_health(self) -> Dict:
        """健康分析"""
        if not self.vital_signs:
            return {'status': 'no_data'}

        analysis = {
            'vitals': {},
            'overall_score': 0.0,
            'recommendations': []
        }

        # 分析各项生命体征
        for vital_type, data in self.vital_signs.items():
            value = data['value']
            # 简化评分
            score = max(0.0, min(1.0, value / 100))
            analysis['vitals'][vital_type] = {
                'value': value,
                'score': score
            }

        # 计算总体评分
        scores = [v['score'] for v in analysis['vitals'].values()]
        analysis['overall_score'] = sum(scores) / len(scores) if scores else 0.0

        return analysis

    def process_request(self, request: Dict) -> Dict:
        """处理健康请求"""
        req_type = request.get('type')

        if req_type == 'record_vital':
            success = self.record_vital(
                request.get('vital_type'),
                request.get('value'),
                request.get('timestamp')
            )
            return {'success': success}
        elif req_type == 'get_vital':
            vital = self.get_vital(request.get('vital_type'))
            return {'vital': vital}
        elif req_type == 'analyze':
            analysis = self.analyze_health()
            return analysis
        else:
            return {'error': 'Unknown request type'}

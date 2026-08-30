"""
离线实验沙盒
进行离线实验和测试
"""
from typing import Dict, List, Optional
from datetime import datetime
import uuid


class Experiment:
    """实验类"""

    def __init__(self, experiment_id: str, name: str, config: Dict):
        self.experiment_id = experiment_id
        self.name = name
        self.config = config
        self.status = 'pending'
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.results = {}


class Sandbox:
    """实验沙盒"""

    def __init__(self):
        self.experiments = {}  # experiment_id -> Experiment
        self.active_sandboxes = {}  # sandbox_id -> data

    def create_experiment(self, name: str, config: Dict) -> str:
        """
        创建实验

        Returns:
            实验ID
        """
        experiment_id = str(uuid.uuid4())
        experiment = Experiment(experiment_id, name, config)
        self.experiments[experiment_id] = experiment
        return experiment_id

    def start_experiment(self, experiment_id: str) -> bool:
        """启动实验"""
        if experiment_id not in self.experiments:
            return False

        experiment = self.experiments[experiment_id]
        experiment.status = 'running'
        experiment.started_at = datetime.now()
        return True

    def complete_experiment(self, experiment_id: str, results: Dict) -> bool:
        """完成实验"""
        if experiment_id not in self.experiments:
            return False

        experiment = self.experiments[experiment_id]
        experiment.status = 'completed'
        experiment.completed_at = datetime.now()
        experiment.results = results
        return True

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """获取实验"""
        return self.experiments.get(experiment_id)

    def get_experiments(self, status: str = None) -> List[Experiment]:
        """获取实验列表"""
        experiments = list(self.experiments.values())

        if status:
            experiments = [e for e in experiments if e.status == status]

        return experiments

    def run_simulation(self, simulation_id: str, parameters: Dict,
                      steps: int = 100) -> Dict:
        """
        运行模拟

        Args:
            simulation_id: 模拟ID
            parameters: 模拟参数
            steps: 模拟步数

        Returns:
            模拟结果
        """
        results = {
            'simulation_id': simulation_id,
            'steps': steps,
            'parameters': parameters,
            'data': [],
            'started_at': datetime.now().isoformat()
        }

        # 简化的模拟实现
        for step in range(steps):
            step_data = {
                'step': step,
                'value': self._simulate_step(step, parameters)
            }
            results['data'].append(step_data)

        results['completed_at'] = datetime.now().isoformat()
        return results

    def _simulate_step(self, step: int, parameters: Dict) -> float:
        """模拟单步"""
        # 简化实现：生成伪随机数据
        import random
        base_value = parameters.get('base', 0.5)
        noise = random.uniform(-0.1, 0.1)
        return max(0.0, min(1.0, base_value + noise))

    def create_sandbox(self, sandbox_id: str, initial_state: Dict = None) -> bool:
        """创建沙盒"""
        if sandbox_id in self.active_sandboxes:
            return False

        self.active_sandboxes[sandbox_id] = {
            'state': initial_state or {},
            'created_at': datetime.now()
        }
        return True

    def update_sandbox_state(self, sandbox_id: str, updates: Dict) -> bool:
        """更新沙盒状态"""
        if sandbox_id not in self.active_sandboxes:
            return False

        self.active_sandboxes[sandbox_id]['state'].update(updates)
        return True

    def get_sandbox_state(self, sandbox_id: str) -> Optional[Dict]:
        """获取沙盒状态"""
        sandbox = self.active_sandboxes.get(sandbox_id)
        if sandbox:
            return sandbox['state'].copy()
        return None

    def cleanup_sandbox(self, sandbox_id: str) -> bool:
        """清理沙盒"""
        if sandbox_id in self.active_sandboxes:
            del self.active_sandboxes[sandbox_id]
            return True
        return False

    def get_sandbox_stats(self) -> Dict:
        """获取沙盒统计"""
        total_experiments = len(self.experiments)
        active = len(self.get_experiments('running'))
        completed = len(self.get_experiments('completed'))

        return {
            'total_experiments': total_experiments,
            'active_sandboxes': len(self.active_sandboxes),
            'running_experiments': active,
            'completed_experiments': completed
        }

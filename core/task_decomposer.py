"""
任务自动分解器
参考 MegaAgent，将大型任务分解为子任务
"""
from typing import Dict, List
import uuid


class TaskDecomposer:
    """任务分解器"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def decompose(self, task: Dict) -> List[Dict]:
        """分解任务为子任务"""
        # 简化实现：基于任务类型分解
        task_type = task.get('type', 'general')

        if task_type == 'trpg_scene_generation':
            return self._decompose_trpg_scene(task)
        elif task_type == 'story_creation':
            return self._decompose_story(task)
        else:
            return self._decompose_general(task)

    def _decompose_trpg_scene(self, task: Dict) -> List[Dict]:
        """分解TRPG场景生成任务"""
        params = task.get('params', {})

        return [
            {
                'id': str(uuid.uuid4()),
                'description': '生成故事大纲',
                'required_capabilities': ['story_outline', 'plot_design'],
                'dependencies': []
            },
            {
                'id': str(uuid.uuid4()),
                'description': '设计环境描述',
                'required_capabilities': ['environment_desc', 'atmosphere'],
                'dependencies': []
            },
            {
                'id': str(uuid.uuid4()),
                'description': '创建敌人配置',
                'required_capabilities': ['enemy_stats', 'boss_design'],
                'dependencies': []
            },
            {
                'id': str(uuid.uuid4()),
                'description': '生成物品掉落',
                'required_capabilities': ['item_generation', 'treasure'],
                'dependencies': []
            }
        ]

    def _decompose_story(self, task: Dict) -> List[Dict]:
        """分解故事创作任务"""
        return [
            {
                'id': str(uuid.uuid4()),
                'description': '设计角色',
                'required_capabilities': ['character_design'],
                'dependencies': []
            },
            {
                'id': str(uuid.uuid4()),
                'description': '构建世界观',
                'required_capabilities': ['world_building'],
                'dependencies': []
            },
            {
                'id': str(uuid.uuid4()),
                'description': '撰写剧情',
                'required_capabilities': ['storytelling', 'narrative'],
                'dependencies': []
            }
        ]

    def _decompose_general(self, task: Dict) -> List[Dict]:
        """分解通用任务"""
        return [{
            'id': str(uuid.uuid4()),
            'description': task.get('description', '执行任务'),
            'required_capabilities': task.get('capabilities', []),
            'dependencies': []
        }]

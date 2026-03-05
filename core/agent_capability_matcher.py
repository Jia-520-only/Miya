"""
Agent能力匹配系统
基于能力匹配Agent与任务
"""
from typing import Dict, List


class AgentCapabilityMatcher:
    """Agent能力匹配器"""

    def __init__(self):
        self.capability_index = {}

    def register_capability(self, agent_id: str, capability: str,
                           proficiency: float = 0.8):
        """注册Agent能力"""
        if capability not in self.capability_index:
            self.capability_index[capability] = []

        self.capability_index[capability].append({
            'agent_id': agent_id,
            'proficiency': proficiency
        })

    def match_agents(self, task_capabilities: List[str],
                    min_proficiency: float = 0.6) -> List[str]:
        """匹配具备所需能力的Agent"""
        candidates = []

        for cap in task_capabilities:
            if cap in self.capability_index:
                agents = self.capability_index[cap]
                qualified = [a['agent_id'] for a in agents
                           if a['proficiency'] >= min_proficiency]
                candidates.extend(qualified)

        # 去重并排序
        return sorted(set(candidates), key=candidates.count, reverse=True)

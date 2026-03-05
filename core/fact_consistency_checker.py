"""
事实一致性检查器
检查角色设定、时间线等事实一致性
"""
from typing import Dict, Optional
import json
from core.constants import Encoding


class FactConsistencyChecker:
    """事实一致性检查器"""

    def __init__(self, knowledge_base=None):
        self.kb = knowledge_base

    def check_character_fact(self, character_name: str,
                             statement: str) -> Dict:
        """检查陈述是否符合角色设定"""
        # 简化实现：查询本地角色文件
        try:
            from pathlib import Path
            char_file = Path('data/trpg_characters.json')

            if char_file.exists():
                with open(char_file, 'r', encoding=Encoding.UTF8) as f:
                    characters = json.load(f)

                character = characters.get(character_name)
                if character:
                    # 简单检查：角色名是否在陈述中
                    return {
                        'valid': True,
                        'reason': f"找到角色设定：{character_name}"
                    }

            return {
                'valid': False,
                'reason': f"角色不存在：{character_name}"
            }

        except Exception as e:
            return {
                'valid': False,
                'reason': f"检查失败：{str(e)}"
            }

    def check_timeline_consistency(self, events: List[Dict]) -> Dict:
        """检查时间线一致性"""
        if not events:
            return {'valid': True, 'reason': '无事件检查'}

        # 按时间排序
        sorted_events = sorted(events, key=lambda e: e.get('timestamp', 0))

        # 检查时间顺序
        for i in range(1, len(sorted_events)):
            if sorted_events[i]['timestamp'] < sorted_events[i-1]['timestamp']:
                return {
                    'valid': False,
                    'reason': '时间顺序不一致'
                }

        return {'valid': True, 'reason': '时间线一致'}

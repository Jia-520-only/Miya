"""
社交节点
处理社交相关事务
"""
from typing import Dict, List
from datetime import datetime


class SocialNet:
    """社交子网"""

    def __init__(self):
        self.net_id = 'social_net'
        self.capabilities = [
            'contact_management',
            'message_handling',
            'social_analysis'
        ]

        # 社交数据
        self.contacts = {}
        self.messages = []
        self.interactions = {}

    def add_contact(self, contact_id: str, name: str,
                    info: Dict = None) -> bool:
        """添加联系人"""
        if not info:
            info = {}

        self.contacts[contact_id] = {
            'name': name,
            'info': info,
            'added_at': datetime.now().isoformat()
        }
        return True

    def get_contact(self, contact_id: str) -> Dict:
        """获取联系人"""
        return self.contacts.get(contact_id, {})

    def get_all_contacts(self) -> List[Dict]:
        """获取所有联系人"""
        return [
            {'id': cid, **contact}
            for cid, contact in self.contacts.items()
        ]

    def add_message(self, from_id: str, to_id: str, content: str,
                    timestamp: str = None) -> bool:
        """添加消息"""
        if not timestamp:
            timestamp = datetime.now().isoformat()

        message = {
            'id': len(self.messages),
            'from': from_id,
            'to': to_id,
            'content': content,
            'timestamp': timestamp
        }

        self.messages.append(message)
        return True

    def get_messages(self, contact_id: str = None, limit: int = 20) -> List[Dict]:
        """获取消息"""
        messages = self.messages

        if contact_id:
            messages = [
                m for m in messages
                if m.get('from') == contact_id or m.get('to') == contact_id
            ]

        return messages[-limit:] if messages else []

    def record_interaction(self, contact_id: str, interaction_type: str,
                           metadata: Dict = None) -> None:
        """记录互动"""
        if contact_id not in self.interactions:
            self.interactions[contact_id] = []

        self.interactions[contact_id].append({
            'type': interaction_type,
            'metadata': metadata or {},
            'timestamp': datetime.now().isoformat()
        })

    def get_interaction_stats(self, contact_id: str = None) -> Dict:
        """获取互动统计"""
        if contact_id:
            interactions = self.interactions.get(contact_id, [])
            return {
                'contact_id': contact_id,
                'total': len(interactions),
                'types': self._count_interaction_types(interactions)
            }
        else:
            # 所有联系人的统计
            all_stats = {}
            for cid, interactions in self.interactions.items():
                all_stats[cid] = {
                    'total': len(interactions),
                    'types': self._count_interaction_types(interactions)
                }
            return all_stats

    def _count_interaction_types(self, interactions: List[Dict]) -> Dict:
        """统计互动类型"""
        type_counts = {}
        for interaction in interactions:
            i_type = interaction.get('type', 'unknown')
            type_counts[i_type] = type_counts.get(i_type, 0) + 1
        return type_counts

    def analyze_relationship(self, contact_id: str) -> Dict:
        """分析关系"""
        if contact_id not in self.contacts:
            return {'error': 'Contact not found'}

        contact = self.contacts[contact_id]
        interactions = self.interactions.get(contact_id, [])
        messages = self.get_messages(contact_id)

        # 计算亲密度
        intimacy_score = min(1.0, len(interactions) / 50)

        return {
            'contact': contact,
            'intimacy_score': round(intimacy_score, 2),
            'interaction_count': len(interactions),
            'message_count': len(messages),
            'last_interaction': interactions[-1]['timestamp'] if interactions else None
        }

    def process_request(self, request: Dict) -> Dict:
        """处理社交请求"""
        req_type = request.get('type')

        if req_type == 'add_contact':
            success = self.add_contact(
                request.get('contact_id'),
                request.get('name'),
                request.get('info')
            )
            return {'success': success}
        elif req_type == 'get_contact':
            contact = self.get_contact(request.get('contact_id'))
            return {'contact': contact}
        elif req_type == 'add_message':
            success = self.add_message(
                request.get('from_id'),
                request.get('to_id'),
                request.get('content')
            )
            return {'success': success}
        elif req_type == 'get_messages':
            messages = self.get_messages(request.get('contact_id'))
            return {'messages': messages}
        else:
            return {'error': 'Unknown request type'}

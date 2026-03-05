"""
用户共演接口
实现用户与AI的共演交互
"""
from typing import Dict, List, Optional
from datetime import datetime


class UserCoPlay:
    """用户共演系统"""

    def __init__(self):
        self.sessions = {}  # session_id -> session_data
        self.interaction_history = []

    def create_session(self, user_id: str, personality_config: Dict = None) -> str:
        """
        创建共演会话

        Returns:
            会话ID
        """
        session_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}_{user_id}"

        session = {
            'session_id': session_id,
            'user_id': user_id,
            'personality_config': personality_config or {},
            'created_at': datetime.now(),
            'status': 'active',
            'interactions': [],
            'feedback': []
        }

        self.sessions[session_id] = session
        return session_id

    def record_interaction(self, session_id: str, user_input: str,
                          ai_response: str, metadata: Dict = None) -> bool:
        """记录交互"""
        if session_id not in self.sessions:
            return False

        interaction = {
            'user_input': user_input,
            'ai_response': ai_response,
            'metadata': metadata or {},
            'timestamp': datetime.now()
        }

        self.sessions[session_id]['interactions'].append(interaction)
        return True

    def record_feedback(self, session_id: str, feedback_type: str,
                       score: float, comment: str = '') -> bool:
        """
        记录用户反馈

        Args:
            session_id: 会话ID
            feedback_type: 反馈类型
            score: 评分 (0-1)
            comment: 评论
        """
        if session_id not in self.sessions:
            return False

        feedback = {
            'type': feedback_type,
            'score': max(0.0, min(1.0, score)),
            'comment': comment,
            'timestamp': datetime.now()
        }

        self.sessions[session_id]['feedback'].append(feedback)
        return True

    def get_session(self, session_id: str) -> Optional[Dict]:
        """获取会话信息"""
        session = self.sessions.get(session_id)
        if not session:
            return None

        return {
            'session_id': session['session_id'],
            'user_id': session['user_id'],
            'status': session['status'],
            'interaction_count': len(session['interactions']),
            'feedback_count': len(session['feedback']),
            'created_at': session['created_at'].isoformat()
        }

    def get_user_sessions(self, user_id: str) -> List[Dict]:
        """获取用户的所有会话"""
        user_sessions = [
            session for session in self.sessions.values()
            if session['user_id'] == user_id
        ]

        return [
            {
                'session_id': s['session_id'],
                'status': s['status'],
                'interaction_count': len(s['interactions']),
                'created_at': s['created_at'].isoformat()
            }
            for s in user_sessions
        ]

    def analyze_session(self, session_id: str) -> Dict:
        """分析会话"""
        session = self.sessions.get(session_id)
        if not session:
            return {'error': 'Session not found'}

        interactions = session['interactions']
        feedback = session['feedback']

        # 计算平均反馈分数
        avg_score = 0.0
        if feedback:
            avg_score = sum(f['score'] for f in feedback) / len(feedback)

        # 统计交互类型
        interaction_types = {}
        for interaction in interactions:
            itype = interaction.get('metadata', {}).get('type', 'general')
            interaction_types[itype] = interaction_types.get(itype, 0) + 1

        return {
            'session_id': session_id,
            'user_id': session['user_id'],
            'interaction_count': len(interactions),
            'feedback_count': len(feedback),
            'avg_feedback_score': round(avg_score, 3),
            'interaction_types': interaction_types,
            'session_duration': self._calculate_duration(session)
        }

    def _calculate_duration(self, session: Dict) -> float:
        """计算会话持续时间（秒）"""
        if not session['interactions']:
            return 0.0

        first = session['interactions'][0]['timestamp']
        last = session['interactions'][-1]['timestamp']
        return (last - first).total_seconds()

    def get_user_feedback_summary(self, user_id: str) -> Dict:
        """获取用户反馈摘要"""
        user_sessions = [
            session for session in self.sessions.values()
            if session['user_id'] == user_id
        ]

        all_feedback = []
        for session in user_sessions:
            all_feedback.extend(session['feedback'])

        if not all_feedback:
            return {'status': 'no_feedback'}

        # 计算统计
        avg_score = sum(f['score'] for f in all_feedback) / len(all_feedback)

        # 按类型统计
        type_counts = {}
        type_scores = {}
        for feedback in all_feedback:
            ftype = feedback['type']
            type_counts[ftype] = type_counts.get(ftype, 0) + 1
            type_scores[ftype] = type_scores.get(ftype, 0) + feedback['score']

        type_avgs = {
            ftype: type_scores[ftype] / count
            for ftype, count in type_counts.items()
        }

        return {
            'user_id': user_id,
            'total_feedback': len(all_feedback),
            'avg_score': round(avg_score, 3),
            'feedback_by_type': {
                ftype: {
                    'count': type_counts[ftype],
                    'avg_score': round(type_avgs[ftype], 3)
                }
                for ftype in type_counts
            }
        }

    def close_session(self, session_id: str) -> bool:
        """关闭会话"""
        if session_id not in self.sessions:
            return False

        self.sessions[session_id]['status'] = 'closed'
        return True

    def get_co_play_stats(self) -> Dict:
        """获取共演统计"""
        total_sessions = len(self.sessions)
        active = len([s for s in self.sessions.values() if s['status'] == 'active'])

        total_interactions = sum(len(s['interactions']) for s in self.sessions.values())
        total_feedback = sum(len(s['feedback']) for s in self.sessions.values())

        return {
            'total_sessions': total_sessions,
            'active_sessions': active,
            'total_interactions': total_interactions,
            'total_feedback': total_feedback
        }

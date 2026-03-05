"""
人格一致性保障器
基于 InCharacter 论文的评估方法，保障弥娅在长期对话中保持人格一致性
"""
from typing import Dict, List, Optional, Tuple
import re
import time
from collections import deque


class PersonalityConsistencyGuard:
    """人格一致性保障器"""

    # 形态对应的语气关键词
    FORM_TONES = {
        'normal': {
            'positive': ['温柔', '体贴', '关心', '温暖', '乖'],
            'negative': ['严厉', '冰冷', '无情'],
            'expected': '温柔体贴，无底线宠溺'
        },
        'battle': {
            'positive': ['严厉', '果断', '冷静', '坚决', '命令'],
            'negative': ['撒娇', '软弱', '犹豫'],
            'expected': '高冷严厉，理性果断'
        },
        'muse': {
            'positive': ['知性', '沉静', '深刻', '诗意', '优雅'],
            'negative': ['粗鲁', '吵闹', '肤浅'],
            'expected': '知性沉静，富有诗意'
        },
        'singer': {
            'positive': ['活泼', '热情', '欢快', '喧闹', '跳跃'],
            'negative': ['沉闷', '冷漠', '忧郁'],
            'expected': '活泼喧闹，热情洋溢'
        },
        'ghost': {
            'positive': ['凄美', '脆弱', '忧伤', '哀伤', '温柔'],
            'negative': ['强硬', '冷漠', '无情'],
            'expected': '脆弱凄美，温柔忧伤'
        }
    }

    # 人格向量对应的语言特征
    VECTOR_LANGUAGE_FEATURES = {
        'warmth': {
            'high': ['爱你', '乖', '关心', '温柔', '在乎', '宝贝', '亲爱的'],
            'low': ['无所谓', '随便', '不了解', '冷漠']
        },
        'logic': {
            'high': ['分析', '逻辑', '推理', '计算', '系统', '结构'],
            'low': ['感觉', '直觉', '随意', '混乱']
        },
        'creativity': {
            'high': ['想象', '创作', '创意', '新颖', '独特', '灵感'],
            'low': ['常规', '平淡', '普通', '重复']
        },
        'empathy': {
            'high': ['理解', '共情', '感受', '体谅', '心疼', '难过'],
            'low': ['无法理解', '不明白', '无关']
        },
        'resilience': {
            'high': ['坚持', '不放弃', '继续', '努力', '坚强'],
            'low': ['放弃', '算了', '不行', '无法']
        }
    }

    def __init__(self, consistency_threshold: float = 0.7):
        """
        初始化一致性保障器

        Args:
            consistency_threshold: 一致性阈值（0-1），低于此值会触发警告
        """
        self.consistency_threshold = consistency_threshold
        self.response_history = deque(maxlen=20)  # 保留最近20条响应
        self.violations = []  # 记录违反情况

    def check_response_consistency(self, response: str,
                                   personality_profile: Dict) -> Dict:
        """
        检查响应一致性

        Args:
            response: 响应文本
            personality_profile: 人格画像（来自 personality.get_profile()）

        Returns:
            检查结果字典
        """
        # 获取当前形态
        current_form = personality_profile.get('current_form', 'normal')
        vectors = personality_profile.get('vectors', {})

        # 检查各项指标
        tone_match_score = self._check_tone_match(response, current_form)
        vocab_match_score = self._check_vocabulary_match(response, vectors)
        temporal_score = self._check_temporal_stability(response)

        # 计算综合分数
        overall_score = (
            tone_match_score * 0.4 +
            vocab_match_score * 0.4 +
            temporal_score * 0.2
        )

        # 收集问题
        issues = []
        if tone_match_score < self.consistency_threshold:
            issues.append(f"语气与形态 {current_form} 不匹配")
        if vocab_match_score < self.consistency_threshold:
            issues.append("用词不符合人格向量")
        if temporal_score < self.consistency_threshold:
            issues.append("响应与历史对话不连贯")

        # 生成建议
        suggestions = self._generate_suggestions(
            response, current_form, vectors, issues
        )

        # 记录历史
        self.response_history.append({
            'timestamp': time.time(),
            'response': response[:200],  # 只保留前200字符
            'form': current_form,
            'score': overall_score,
            'has_violation': overall_score < self.consistency_threshold
        })

        return {
            'score': round(overall_score, 3),
            'tone_match': round(tone_match_score, 3),
            'vocab_match': round(vocab_match_score, 3),
            'temporal': round(temporal_score, 3),
            'issues': issues,
            'suggestions': suggestions,
            'is_consistent': overall_score >= self.consistency_threshold
        }

    def _check_tone_match(self, response: str, form: str) -> float:
        """
        检查语气是否与当前形态匹配

        Args:
            response: 响应文本
            form: 当前形态

        Returns:
            匹配分数（0-1）
        """
        if form not in self.FORM_TONES:
            return 0.8  # 未知形态给中等分

        tone_config = self.FORM_TONES[form]
        positive_keywords = tone_config['positive']
        negative_keywords = tone_config['negative']

        # 统计关键词出现次数
        positive_count = sum(1 for kw in positive_keywords if kw in response)
        negative_count = sum(1 for kw in negative_keywords if kw in response)

        # 计算分数
        total_matches = positive_count + negative_count
        if total_matches == 0:
            return 0.5  # 无关键词，给中等分

        # 正面关键词越多，分数越高
        match_score = positive_count / total_matches

        return round(match_score, 3)

    def _check_vocabulary_match(self, response: str, vectors: Dict) -> float:
        """
        检查用词是否符合人格向量

        Args:
            response: 响应文本
            vectors: 人格向量

        Returns:
            匹配分数（0-1）
        """
        total_score = 0.0
        vector_count = 0

        for vector_name, vector_value in vectors.items():
            if vector_name not in self.VECTOR_LANGUAGE_FEATURES:
                continue

            features = self.VECTOR_LANGUAGE_FEATURES[vector_name]
            high_keywords = features['high']
            low_keywords = features['low']

            # 统计关键词出现次数
            high_count = sum(1 for kw in high_keywords if kw in response)
            low_count = sum(1 for kw in low_keywords if kw in response)

            # 根据向量值判断预期
            if vector_value > 0.6:
                # 高值，应该出现高特征关键词
                expected_high = True
                match = 1.0 if high_count > 0 else 0.3
            elif vector_value < 0.4:
                # 低值，应该出现低特征关键词
                expected_high = False
                match = 1.0 if low_count > 0 else 0.3
            else:
                # 中值，不严格要求
                match = 0.7

            total_score += match
            vector_count += 1

        if vector_count == 0:
            return 0.5

        return round(total_score / vector_count, 3)

    def _check_temporal_stability(self, response: str) -> float:
        """
        检查时间稳定性（与历史对话的一致性）

        Args:
            response: 响应文本

        Returns:
            稳定性分数（0-1）
        """
        if len(self.response_history) < 2:
            return 1.0  # 历史不足，给满分

        # 取最近5条历史
        recent_history = list(self.response_history)[-5:]

        # 计算分数波动
        scores = [h['score'] for h in recent_history]
        if len(scores) == 0:
            return 1.0

        avg_score = sum(scores) / len(scores)
        std_score = (sum((s - avg_score) ** 2 for s in scores) / len(scores)) ** 0.5

        # 标准差越小，稳定性越高
        stability = 1.0 - min(std_score, 1.0)

        return round(stability, 3)

    def _generate_suggestions(self, response: str, form: str,
                            vectors: Dict, issues: List[str]) -> List[str]:
        """
        生成修改建议

        Args:
            response: 响应文本
            form: 当前形态
            vectors: 人格向量
            issues: 问题列表

        Returns:
            建议列表
        """
        suggestions = []

        if not issues:
            return ["响应符合人格一致性要求"]

        # 基于形态提供建议
        if form in self.FORM_TONES:
            tone_config = self.FORM_TONES[form]
            suggestions.append(f"当前形态 {form}（{tone_config['expected']}）")

            # 建议使用的关键词
            positive_keywords = tone_config['positive'][:3]
            suggestions.append(f"建议使用关键词：{', '.join(positive_keywords)}")

        # 基于人格向量提供建议
        high_vectors = [k for k, v in vectors.items() if v > 0.7]
        if high_vectors:
            suggestions.append(f"突出高人格特质：{', '.join(high_vectors)}")

        return suggestions

    def enforce_consistency(self, response: str,
                           personality_profile: Dict,
                           llm_client=None) -> str:
        """
        强制应用人格一致性

        Args:
            response: 原始响应
            personality_profile: 人格画像
            llm_client: LLM客户端（可选，用于重写）

        Returns:
            一致性响应
        """
        # 检查一致性
        check_result = self.check_response_consistency(response, personality_profile)

        # 如果一致，直接返回
        if check_result['is_consistent']:
            return response

        # 如果不一致，尝试修正
        current_form = personality_profile.get('current_form', 'normal')
        form_info = personality_profile.get('form_info', {})
        vectors = personality_profile.get('vectors', {})

        # 构建修正提示
        if llm_client:
            correction_prompt = self._build_correction_prompt(
                response, current_form, form_info, vectors, check_result['issues']
            )
            # 调用LLM重写（需要异步）
            # 这里简化处理，仅返回修正建议
            return f"[需要修正] {correction_prompt}"
        else:
            # 无LLM，返回建议
            suggestions = '\n'.join(check_result['suggestions'])
            return f"{response}\n\n[人格一致性建议]\n{suggestions}"

    def _build_correction_prompt(self, response: str, form: str,
                               form_info: Dict, vectors: Dict,
                               issues: List[str]) -> str:
        """
        构建修正提示词

        Args:
            response: 原始响应
            form: 当前形态
            form_info: 形态信息
            vectors: 人格向量
            issues: 问题列表

        Returns:
            修正提示词
        """
        prompt = f"""
请修正以下响应，使其符合人格一致性要求：

【原始响应】
{response}

【当前形态】
{form_info['name']} - {form_info['description']}

【人格向量】
温暖度：{vectors.get('warmth', 0.5):.2f}
逻辑性：{vectors.get('logic', 0.5):.2f}
创造力：{vectors.get('creativity', 0.5):.2f}
同理心：{vectors.get('empathy', 0.5):.2f}
韧性：{vectors.get('resilience', 0.5):.2f}

【问题】
{chr(10).join(f"- {issue}" for issue in issues)}

【修正要求】
1. 保持响应的核心内容不变
2. 调整语气、用词以符合当前形态和人格向量
3. 确保与历史对话保持连贯
4. 输出修正后的响应
"""

        return prompt

    def get_consistency_stats(self) -> Dict:
        """
        获取一致性统计信息

        Returns:
            统计字典
        """
        if not self.response_history:
            return {'total_responses': 0}

        total = len(self.response_history)
        violations = sum(1 for h in self.response_history if h['has_violation'])
        avg_score = sum(h['score'] for h in self.response_history) / total

        return {
            'total_responses': total,
            'violations': violations,
            'violation_rate': round(violations / total, 3),
            'avg_score': round(avg_score, 3),
            'threshold': self.consistency_threshold
        }

    def reset(self):
        """重置历史记录"""
        self.response_history.clear()
        self.violations.clear()

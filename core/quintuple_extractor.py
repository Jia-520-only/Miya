"""
五元组提取器 - 从对话中提取结构化知识
参考 NagaAgent 的 quintuple_extractor 实现
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Quintuple:
    """五元组数据结构"""

    subject: str
    subject_type: str
    predicate: str
    object: str
    object_type: str

    def to_tuple(self) -> Tuple[str, str, str, str, str]:
        return (
            self.subject,
            self.subject_type,
            self.predicate,
            self.object,
            self.object_type,
        )

    def to_dict(self) -> Dict:
        return {
            "subject": self.subject,
            "subject_type": self.subject_type,
            "predicate": self.predicate,
            "object": self.object,
            "object_type": self.object_type,
        }


SYSTEM_PROMPT = """
你是一个专业的中文文本信息抽取专家。你的任务是从给定的中文文本中抽取有价值的五元组关系。
五元组格式为：(主体, 主体类型, 动作, 客体, 客体类型)。

## 提取规则
1. 只提取**事实性**信息，包括：
   - 具体的行为和动作
   - 明确的实体关系
   - 实际存在的状态和属性
   - 用户表达的具体需求、偏好、计划

2. 严格过滤以下内容：
   - 比喻、拟人、夸张等修辞手法
   - 虚拟、假设、想象的内容
   - 纯粹的情感表达（如"我很开心"、"你真棒"）
   - 赞美、讽刺、调侃等主观评价
   - 闲聊中的无关信息
   - 重复或冗余的关系

3. 类型包括但不限于：人物、地点、组织、物品、概念、时间、事件、活动等。

## 示例
输入：小明在公园里踢足球。
输出：[["小明", "人物", "踢", "足球", "物品"], ["小明", "人物", "在", "公园", "地点"]]

输入：你像小太阳一样温暖。
输出：[] （比喻句，不提取）

输入：我喜欢吃苹果和香蕉。
输出：[["我", "人物", "喜欢吃", "苹果", "物品"], ["我", "人物", "喜欢吃", "香蕉", "物品"]]

请从文本中提取有价值的事实性五元组：
"""


async def extract_quintuples_async(text: str, ai_client) -> List[Quintuple]:
    """
    异步提取五元组

    Args:
        text: 待提取的文本
        ai_client: AI客户端（需要有 chat.completions.create 方法）

    Returns:
        五元组列表
    """
    if not text or not text.strip():
        return []

    prompt = f"{SYSTEM_PROMPT}\n{text}"

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = await asyncio.wait_for(
                ai_client.chat.completions.create(
                    model=ai_client.model if hasattr(ai_client, "model") else "default",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2000,
                    temperature=0.3,
                ),
                timeout=30.0,
            )

            content = response.choices[0].message.content.strip()
            return _parse_quintuples(content)

        except asyncio.TimeoutError:
            logger.warning(f"五元组提取超时 (尝试 {attempt + 1}/{max_retries + 1})")
            if attempt < max_retries:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"五元组提取失败: {e}")
            if attempt < max_retries:
                await asyncio.sleep(1)

    return []


def _parse_quintuples(content: str) -> List[Quintuple]:
    """解析五元组结果"""
    quintuples = []

    try:
        # 尝试直接解析JSON
        data = json.loads(content)
        for item in data:
            if isinstance(item, list) and len(item) == 5:
                quintuples.append(
                    Quintuple(
                        subject=str(item[0]),
                        subject_type=str(item[1]),
                        predicate=str(item[2]),
                        object=str(item[3]),
                        object_type=str(item[4]),
                    )
                )
        return quintuples
    except json.JSONDecodeError:
        pass

    # 尝试从文本中提取JSON数组
    try:
        if "[" in content and "]" in content:
            start = content.index("[")
            end = content.rindex("]") + 1
            data = json.loads(content[start:end])
            for item in data:
                if isinstance(item, list) and len(item) == 5:
                    quintuples.append(
                        Quintuple(
                            subject=str(item[0]),
                            subject_type=str(item[1]),
                            predicate=str(item[2]),
                            object=str(item[3]),
                            object_type=str(item[4]),
                        )
                    )
    except Exception as e:
        logger.error(f"解析五元组失败: {e}")

    return quintuples


def extract_quintuples_sync(text: str, ai_client) -> List[Quintuple]:
    """
    同步提取五元组（阻塞版本）

    Args:
        text: 待提取的文本
        ai_client: AI客户端

    Returns:
        五元组列表
    """
    if not text or not text.strip():
        return []

    prompt = f"{SYSTEM_PROMPT}\n{text}"

    try:
        response = ai_client.chat.completions.create(
            model=ai_client.model if hasattr(ai_client, "model") else "default",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3,
        )

        content = response.choices[0].message.content.strip()
        return _parse_quintuples(content)

    except Exception as e:
        logger.error(f"同步五元组提取失败: {e}")
        return []


def format_quintuples_for_prompt(quintuples: List[Quintuple]) -> str:
    """将五元组格式化为提示词"""
    if not quintuples:
        return ""

    lines = ["【知识图谱记忆】"]
    for q in quintuples[:10]:  # 限制数量
        lines.append(f"- {q.subject}({q.subject_type}) {q.predicate} {q.object}({q.object_type})")

    return "\n".join(lines)

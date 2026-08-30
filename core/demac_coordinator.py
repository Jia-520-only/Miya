"""
DeMAC去中心化协调器
基于DeMAC论文，实现去中心化的多Agent协调，消除Zeno效应
"""
import asyncio
import json
import logging
import time
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ConsensusPhase(Enum):
    """共识阶段"""
    INIT = "init"
    PROPOSE = "propose"
    VOTE = "vote"
    COMMIT = "commit"
    ABORT = "abort"


@dataclass
class Proposal:
    """提案"""
    proposal_id: str
    proposer: str
    action: str
    parameters: Dict[str, Any]
    votes: Dict[str, int] = field(default_factory=dict)
    phase: ConsensusPhase = ConsensusPhase.INIT
    timestamp: float = field(default_factory=time.time)
    deadline: float = 0.0


class DeMACCoordinator:
    """DeMAC协调器"""

    def __init__(
        self,
        agent_id: str,
        quorum_ratio: float = 0.6,
        timeout: float = 10.0
    ):
        self.agent_id = agent_id
        self.quorum_ratio = quorum_ratio  # 法定人数比例
        self.timeout = timeout  # 超时时间（秒）

        # 提案存储
        self.proposals: Dict[str, Proposal] = {}

        # 已知Agent
        self.known_agents: Set[str] = set()

        # 动作队列
        self.action_queue: List[Tuple[str, Dict[str, Any]]] = []

        # 网络模拟（实际应通过A2A通信）
        self.network_delay_range = (0.1, 0.5)  # 秒
        self.network_failure_rate = 0.01  # 1%失败率

        # Zeno效应防护
        self.zeno_threshold = 3  # 连续异常决策阈值

        # 统计信息
        self.stats = {
            'total_proposals': 0,
            'successful_consensus': 0,
            'failed_consensus': 0,
            'zeno_detected': 0
        }

    async def propose_action(
        self,
        action: str,
        parameters: Optional[Dict[str, Any]] = None,
        broadcast: bool = True
    ) -> Optional[Proposal]:
        """
        发起动作提案

        Args:
            action: 动作名称
            parameters: 动作参数
            broadcast: 是否广播

        Returns:
            提案对象
        """
        proposal_id = self._generate_proposal_id()

        proposal = Proposal(
            proposal_id=proposal_id,
            proposer=self.agent_id,
            action=action,
            parameters=parameters or {},
            phase=ConsensusPhase.PROPOSE,
            deadline=time.time() + self.timeout
        )

        self.proposals[proposal_id] = proposal
        self.stats['total_proposals'] += 1

        logger.info(f"[DeMAC] 提案: {action}, ID: {proposal_id}")

        if broadcast:
            await self._broadcast_proposal(proposal)

        return proposal

    async def vote_proposal(
        self,
        proposal_id: str,
        vote: int  # 0=反对, 1=赞成
    ) -> bool:
        """
        对提案投票

        Args:
            proposal_id: 提案ID
            vote: 投票（0或1）

        Returns:
            是否成功
        """
        if proposal_id not in self.proposals:
            logger.warning(f"[DeMAC] 提案不存在: {proposal_id}")
            return False

        proposal = self.proposals[proposal_id]

        # 检查阶段
        if proposal.phase != ConsensusPhase.VOTE:
            logger.warning(f"[DeMAC] 提案非投票阶段: {proposal.phase}")
            return False

        # 记录投票
        proposal.votes[self.agent_id] = vote

        logger.debug(
            f"[DeMAC] 投票: {self.agent_id} -> {proposal_id}, "
            f"投票: {vote}"
        )

        # 检查是否达到法定人数
        if self._check_quorum(proposal):
            await self._finalize_proposal(proposal)

        return True

    async def execute_consensus(self, proposal_id: str) -> bool:
        """
        执行共识

        Args:
            proposal_id: 提案ID

        Returns:
            是否成功
        """
        if proposal_id not in self.proposals:
            return False

        proposal = self.proposals[proposal_id]

        # 检查是否已达成共识
        if proposal.phase != ConsensusPhase.COMMIT:
            logger.warning(f"[DeMAC] 提案未达成共识: {proposal.phase}")
            return False

        # 检测Zeno效应
        if self._detect_zeno_effect(proposal):
            logger.warning(f"[DeMAC] 检测到Zeno效应: {proposal_id}")
            self.stats['zeno_detected'] += 1

            # 中止提案
            proposal.phase = ConsensusPhase.ABORT
            return False

        # 执行动作
        try:
            success = await self._execute_action(proposal.action, proposal.parameters)

            if success:
                self.stats['successful_consensus'] += 1
                logger.info(f"[DeMAC] 执行成功: {proposal.action}")
            else:
                self.stats['failed_consensus'] += 1
                logger.error(f"[DeMAC] 执行失败: {proposal.action}")

            return success

        except Exception as e:
            logger.error(f"[DeMAC] 执行异常: {e}")
            return False

    def _check_quorum(self, proposal: Proposal) -> bool:
        """
        检查是否达到法定人数

        Args:
            proposal: 提案

        Returns:
            是否达到法定人数
        """
        total_agents = len(self.known_agents)
        if total_agents == 0:
            return False

        total_votes = len(proposal.votes)
        positive_votes = sum(proposal.votes.values())

        # 法定人数检查
        quorum_needed = max(1, int(total_agents * self.quorum_ratio))

        return total_votes >= quorum_needed and positive_votes > total_votes // 2

    async def _finalize_proposal(self, proposal: Proposal):
        """
        确定提案

        Args:
            proposal: 提案
        """
        total_votes = len(proposal.votes)
        positive_votes = sum(proposal.votes.values())

        if positive_votes > total_votes // 2:
            proposal.phase = ConsensusPhase.COMMIT
            logger.info(f"[DeMAC] 共识达成: {proposal.proposal_id}")
        else:
            proposal.phase = ConsensusPhase.ABORT
            logger.warning(f"[DeMAC] 共识失败: {proposal.proposal_id}")

    def _detect_zeno_effect(self, proposal: Proposal) -> bool:
        """
        检测Zeno效应

        Zeno效应：Agent被持续引导做出异常决策

        Args:
            proposal: 提案

        Returns:
            是否检测到Zeno效应
        """
        # 检查最近提案的模式
        recent_proposals = [
            p for p in self.proposals.values()
            if p.phase == ConsensusPhase.COMMIT and
               p.timestamp > time.time() - 300  # 5分钟内
        ]

        if len(recent_proposals) < self.zeno_threshold:
            return False

        # 统计提案者分布
        proposer_counts = {}
        for p in recent_proposals:
            proposer_counts[p.proposer] = proposer_counts.get(p.proposer, 0) + 1

        # 检查是否有Agent主导提案
        max_proposals = max(proposer_counts.values()) if proposer_counts else 0
        total_recent = len(recent_proposals)

        # 如果某个Agent超过50%提案，可能存在Zeno效应
        if max_proposals > total_recent * 0.5:
            return True

        return False

    async def _broadcast_proposal(self, proposal: Proposal):
        """
        广播提案（模拟）

        实际实现应通过A2A通信广播
        """
        # 模拟网络延迟
        delay = random.uniform(*self.network_delay_range)
        await asyncio.sleep(delay)

        # 模拟网络失败
        if random.random() < self.network_failure_rate:
            logger.warning(f"[DeMAC] 网络广播失败: {proposal.proposal_id}")
            return

        # 更新投票阶段
        proposal.phase = ConsensusPhase.VOTE

        logger.debug(f"[DeMAC] 广播提案: {proposal.proposal_id}")

    async def _execute_action(
        self,
        action: str,
        parameters: Dict[str, Any]
    ) -> bool:
        """
        执行动作（模拟）

        实际实现应根据action类型执行具体逻辑

        Args:
            action: 动作名称
            parameters: 动作参数

        Returns:
            是否成功
        """
        # 简化实现：模拟执行
        logger.info(f"[DeMAC] 执行动作: {action}, 参数: {parameters}")

        # 模拟执行时间
        await asyncio.sleep(0.1)

        return True

    def _generate_proposal_id(self) -> str:
        """生成提案ID"""
        import uuid
        return f"prop_{self.agent_id}_{uuid.uuid4().hex[:12]}_{int(time.time())}"

    def add_agent(self, agent_id: str):
        """
        添加Agent到已知列表

        Args:
            agent_id: Agent ID
        """
        self.known_agents.add(agent_id)
        logger.debug(f"[DeMAC] 添加Agent: {agent_id}")

    def remove_agent(self, agent_id: str):
        """
        移除Agent

        Args:
            agent_id: Agent ID
        """
        if agent_id in self.known_agents:
            self.known_agents.remove(agent_id)
            logger.debug(f"[DeMAC] 移除Agent: {agent_id}")

    def get_proposal_status(self, proposal_id: str) -> Optional[Proposal]:
        """
        获取提案状态

        Args:
            proposal_id: 提案ID

        Returns:
            提案对象
        """
        return self.proposals.get(proposal_id)

    def cleanup_expired_proposals(self):
        """清理过期提案"""
        current_time = time.time()
        to_remove = []

        for proposal_id, proposal in self.proposals.items():
            if current_time > proposal.deadline:
                to_remove.append(proposal_id)

        for proposal_id in to_remove:
            del self.proposals[proposal_id]
            logger.debug(f"[DeMAC] 清理过期提案: {proposal_id}")

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        active_proposals = [
            p for p in self.proposals.values()
            if p.phase not in [ConsensusPhase.COMMIT, ConsensusPhase.ABORT]
        ]

        return {
            'agent_id': self.agent_id,
            'known_agents': len(self.known_agents),
            'total_proposals': self.stats['total_proposals'],
            'active_proposals': len(active_proposals),
            'successful_consensus': self.stats['successful_consensus'],
            'failed_consensus': self.stats['failed_consensus'],
            'zeno_detected': self.stats['zeno_detected'],
            'consensus_rate': (
                self.stats['successful_consensus'] /
                max(self.stats['total_proposals'], 1)
            ) if self.stats['total_proposals'] > 0 else 0.0
        }

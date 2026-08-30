"""
审计日志 - 记录权限检查和变更操作

功能：
- 记录权限检查日志
- 记录权限授予/撤销日志
- 记录用户操作日志
- 支持日志查询和导出
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    审计日志管理器

    记录所有权限相关的操作，便于安全审计和问题排查
    """

    def __init__(self, log_dir: str = "data/auth"):
        """
        初始化审计日志管理器

        Args:
            log_dir: 日志存储目录
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.audit_file = self.log_dir / "audit.log"
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.max_backup_count = 5

    def log(
        self,
        action: str,
        user_id: str,
        target: str,
        result: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        platform: Optional[str] = None
    ) -> None:
        """
        记录审计日志

        Args:
            action: 操作类型
                - permission_check: 权限检查
                - permission_grant: 授予权限
                - permission_revoke: 撤销权限
                - user_login: 用户登录
                - user_logout: 用户登出
                - tool_execute: 工具执行
                - api_access: API访问
            user_id: 用户ID
            target: 目标（如权限节点、资源等）
            result: 操作结果（success/fail/deny）
            details: 详细信息
            ip_address: IP地址
            platform: 平台
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user_id": user_id,
            "target": target,
            "result": result,
            "details": details or {},
            "ip_address": ip_address,
            "platform": platform
        }

        # 写入日志文件
        try:
            with open(self.audit_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

            # 检查文件大小，必要时轮转
            self._rotate_if_needed()

        except Exception as e:
            logger.error(f"[Audit] 写入审计日志失败: {e}")

    def log_permission_check(
        self,
        user_id: str,
        permission: str,
        result: bool,
        required: bool = False,
        platform: Optional[str] = None
    ) -> None:
        """
        记录权限检查

        Args:
            user_id: 用户ID
            permission: 权限节点
            result: 检查结果
            required: 是否为必需权限
            platform: 平台
        """
        self.log(
            action="permission_check",
            user_id=user_id,
            target=permission,
            result="success" if result else "deny",
            details={"required": required},
            platform=platform
        )

    def log_permission_change(
        self,
        admin_id: str,
        user_id: str,
        permission: str,
        action: str,  # grant/revoke
        success: bool = True
    ) -> None:
        """
        记录权限变更

        Args:
            admin_id: 管理员ID
            user_id: 目标用户ID
            permission: 权限节点
            action: 操作类型
            success: 是否成功
        """
        self.log(
            action=f"permission_{action}",
            user_id=admin_id,
            target=user_id,
            result="success" if success else "fail",
            details={"permission": permission}
        )

    def log_tool_execution(
        self,
        user_id: str,
        tool_name: str,
        result: str,
        platform: Optional[str] = None
    ) -> None:
        """
        记录工具执行

        Args:
            user_id: 用户ID
            tool_name: 工具名称
            result: 执行结果
            platform: 平台
        """
        self.log(
            action="tool_execute",
            user_id=user_id,
            target=tool_name,
            result=result,
            platform=platform
        )

    def log_api_access(
        self,
        user_id: str,
        endpoint: str,
        method: str,
        result: str,
        ip_address: Optional[str] = None
    ) -> None:
        """
        记录API访问

        Args:
            user_id: 用户ID
            endpoint: API端点
            method: HTTP方法
            result: 访问结果
            ip_address: IP地址
        """
        self.log(
            action="api_access",
            user_id=user_id,
            target=f"{method} {endpoint}",
            result=result,
            ip_address=ip_address
        )

    def query(
        self,
        action: Optional[str] = None,
        user_id: Optional[str] = None,
        result: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        查询审计日志

        Args:
            action: 操作类型
            user_id: 用户ID
            result: 操作结果
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制

        Returns:
            日志条目列表
        """
        if not self.audit_file.exists():
            return []

        logs = []
        try:
            with open(self.audit_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())

                        # 过滤条件
                        if action and entry.get('action') != action:
                            continue
                        if user_id and entry.get('user_id') != user_id:
                            continue
                        if result and entry.get('result') != result:
                            continue

                        # 时间过滤
                        entry_time = datetime.fromisoformat(entry.get('timestamp', ''))
                        if start_time and entry_time < start_time:
                            continue
                        if end_time and entry_time > end_time:
                            continue

                        logs.append(entry)

                        if len(logs) >= limit:
                            break
                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            logger.error(f"[Audit] 查询审计日志失败: {e}")

        return logs

    def get_user_activity(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """
        获取用户活动统计

        Args:
            user_id: 用户ID
            days: 查询天数

        Returns:
            活动统计
        """
        start_time = datetime.now() - timedelta(days=days)
        logs = self.query(user_id=user_id, start_time=start_time, limit=1000)

        # 统计
        action_counts = defaultdict(int)
        result_counts = defaultdict(int)

        for log in logs:
            action_counts[log.get('action', 'unknown')] += 1
            result_counts[log.get('result', 'unknown')] += 1

        return {
            "user_id": user_id,
            "period_days": days,
            "total_actions": len(logs),
            "action_breakdown": dict(action_counts),
            "result_breakdown": dict(result_counts),
            "recent_logs": logs[-10:] if logs else []
        }

    def _rotate_if_needed(self):
        """日志文件轮转"""
        if not self.audit_file.exists():
            return

        file_size = self.audit_file.stat().st_size
        if file_size < self.max_file_size:
            return

        # 轮转日志文件
        for i in range(self.max_backup_count - 1, 0, -1):
            old_file = self.audit_file.with_suffix(f'.log.{i}')
            new_file = self.audit_file.with_suffix(f'.log.{i + 1}')
            if old_file.exists():
                old_file.rename(new_file)

        # 当前日志文件重命名为 .log.1
        self.audit_file.rename(self.audit_file.with_suffix('.log.1'))

    def export(self, output_file: str, format: str = "json") -> bool:
        """
        导出审计日志

        Args:
            output_file: 输出文件路径
            format: 导出格式 (json/csv)

        Returns:
            是否成功
        """
        try:
            logs = self.query(limit=10000)

            if format == "json":
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(logs, f, ensure_ascii=False, indent=2)
            elif format == "csv":
                import csv
                if logs:
                    with open(output_file, 'w', encoding='utf-8', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=logs[0].keys())
                        writer.writeheader()
                        writer.writerows(logs)

            logger.info(f"[Audit] 审计日志已导出到 {output_file}")
            return True

        except Exception as e:
            logger.error(f"[Audit] 导出审计日志失败: {e}")
            return False


# 全局审计日志实例
_audit_logger = None


def get_audit_logger() -> AuditLogger:
    """获取全局审计日志实例"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger

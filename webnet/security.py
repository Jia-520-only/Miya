"""
安全审计节点
处理安全审计和检查
"""
from typing import Dict, List
from datetime import datetime


class SecurityNet:
    """安全子网"""

    def __init__(self):
        self.net_id = 'security_net'
        self.capabilities = [
            'audit_logging',
            'threat_detection',
            'access_control'
        ]

        # 安全数据
        self.audit_logs = []
        self.threats = []
        self.security_policies = {}

    def log_audit(self, event: str, source: str,
                  details: Dict = None) -> bool:
        """记录审计日志"""
        log = {
            'id': len(self.audit_logs),
            'event': event,
            'source': source,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        }

        self.audit_logs.append(log)
        return True

    def get_audit_logs(self, event: str = None, source: str = None,
                       limit: int = 50) -> List[Dict]:
        """获取审计日志"""
        logs = self.audit_logs

        if event:
            logs = [l for l in logs if l.get('event') == event]

        if source:
            logs = [l for l in logs if l.get('source') == source]

        return logs[-limit:] if logs else []

    def report_threat(self, threat_type: str, severity: str,
                      details: Dict = None) -> bool:
        """报告威胁"""
        threat = {
            'id': len(self.threats),
            'type': threat_type,
            'severity': severity,
            'details': details or {},
            'reported_at': datetime.now().isoformat(),
            'status': 'open'
        }

        self.threats.append(threat)

        # 同时记录审计日志
        self.log_audit(
            'threat_reported',
            details.get('source', 'unknown'),
            {'threat_id': threat['id'], 'type': threat_type}
        )

        return True

    def get_threats(self, severity: str = None,
                    status: str = None) -> List[Dict]:
        """获取威胁列表"""
        threats = self.threats

        if severity:
            threats = [t for t in threats if t.get('severity') == severity]

        if status:
            threats = [t for t in threats if t.get('status') == status]

        return threats

    def resolve_threat(self, threat_id: int, resolution: str) -> bool:
        """解决威胁"""
        for threat in self.threats:
            if threat['id'] == threat_id and threat.get('status') == 'open':
                threat['status'] = 'resolved'
                threat['resolution'] = resolution
                threat['resolved_at'] = datetime.now().isoformat()
                return True
        return False

    def set_policy(self, policy_name: str, rules: Dict) -> None:
        """设置安全策略"""
        self.security_policies[policy_name] = rules

    def get_policy(self, policy_name: str) -> Dict:
        """获取安全策略"""
        return self.security_policies.get(policy_name, {})

    def check_access(self, source: str, resource: str,
                    action: str) -> Dict:
        """检查访问权限"""
        # 简化实现：检查策略
        allowed = True
        reason = ''

        for policy_name, rules in self.security_policies.items():
            if 'access_rules' in rules:
                for rule in rules['access_rules']:
                    if (rule.get('source') == source and
                        rule.get('resource') == resource and
                        rule.get('action') == action):
                        allowed = rule.get('allow', True)
                        reason = rule.get('reason', '')
                        break

        return {
            'allowed': allowed,
            'reason': reason,
            'source': source,
            'resource': resource,
            'action': action
        }

    def get_security_summary(self) -> Dict:
        """获取安全摘要"""
        open_threats = [t for t in self.threats if t.get('status') == 'open']
        high_severity = [t for t in open_threats if t.get('severity') == 'high']

        return {
            'total_audit_logs': len(self.audit_logs),
            'total_threats': len(self.threats),
            'open_threats': len(open_threats),
            'high_severity_threats': len(high_severity),
            'active_policies': len(self.security_policies)
        }

    def process_request(self, request: Dict) -> Dict:
        """处理安全请求"""
        req_type = request.get('type')

        if req_type == 'log_audit':
            success = self.log_audit(
                request.get('event'),
                request.get('source'),
                request.get('details')
            )
            return {'success': success}
        elif req_type == 'report_threat':
            success = self.report_threat(
                request.get('threat_type'),
                request.get('severity'),
                request.get('details')
            )
            return {'success': success}
        elif req_type == 'get_threats':
            threats = self.get_threats(
                request.get('severity'),
                request.get('status')
            )
            return {'threats': threats}
        elif req_type == 'check_access':
            access = self.check_access(
                request.get('source'),
                request.get('resource'),
                request.get('action')
            )
            return access
        else:
            return {'error': 'Unknown request type'}

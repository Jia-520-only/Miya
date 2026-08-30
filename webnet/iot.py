"""
IoT控制节点
处理IoT设备控制
"""
from typing import Dict, List


class IoTNet:
    """IoT子网"""

    def __init__(self):
        self.net_id = 'iot_net'
        self.capabilities = [
            'device_control',
            'device_monitoring',
            'automation'
        ]

        # IoT数据
        self.devices = {}
        self.device_status = {}
        self.automations = []

    def register_device(self, device_id: str, device_type: str,
                        info: Dict = None) -> bool:
        """注册设备"""
        if not info:
            info = {}

        self.devices[device_id] = {
            'type': device_type,
            'info': info,
            'registered_at': self._get_timestamp()
        }

        # 初始化设备状态
        self.device_status[device_id] = {
            'online': False,
            'status': 'idle',
            'attributes': {}
        }

        return True

    def get_device(self, device_id: str) -> Dict:
        """获取设备信息"""
        device = self.devices.get(device_id, {})
        status = self.device_status.get(device_id, {})
        return {**device, 'status': status}

    def get_all_devices(self, device_type: str = None) -> List[Dict]:
        """获取所有设备"""
        devices = []
        for device_id, device_info in self.devices.items():
            if device_type is None or device_info.get('type') == device_type:
                devices.append({
                    'id': device_id,
                    **device_info,
                    'status': self.device_status.get(device_id, {})
                })
        return devices

    def control_device(self, device_id: str, command: str,
                       parameters: Dict = None) -> bool:
        """控制设备"""
        if device_id not in self.devices:
            return False

        # 更新设备状态
        self.device_status[device_id]['status'] = command
        if parameters:
            self.device_status[device_id]['attributes'].update(parameters)

        return True

    def update_device_status(self, device_id: str, status: Dict) -> bool:
        """更新设备状态"""
        if device_id not in self.device_status:
            return False

        self.device_status[device_id].update(status)
        return True

    def add_automation(self, trigger: Dict, action: Dict) -> bool:
        """添加自动化"""
        automation = {
            'id': len(self.automations),
            'trigger': trigger,
            'action': action,
            'enabled': True,
            'created_at': self._get_timestamp()
        }

        self.automations.append(automation)
        return True

    def trigger_automations(self, event: Dict) -> List[Dict]:
        """触发自动化"""
        triggered = []

        for automation in self.automations:
            if not automation.get('enabled', False):
                continue

            if self._match_trigger(event, automation['trigger']):
                triggered.append(automation['action'])

        return triggered

    def _match_trigger(self, event: Dict, trigger: Dict) -> bool:
        """匹配触发条件"""
        # 简化实现：精确匹配
        for key, value in trigger.items():
            if event.get(key) != value:
                return False
        return True

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()

    def process_request(self, request: Dict) -> Dict:
        """处理IoT请求"""
        req_type = request.get('type')

        if req_type == 'register_device':
            success = self.register_device(
                request.get('device_id'),
                request.get('device_type'),
                request.get('info')
            )
            return {'success': success}
        elif req_type == 'control_device':
            success = self.control_device(
                request.get('device_id'),
                request.get('command'),
                request.get('parameters')
            )
            return {'success': success}
        elif req_type == 'get_devices':
            devices = self.get_all_devices(request.get('device_type'))
            return {'devices': devices}
        elif req_type == 'get_device':
            device = self.get_device(request.get('device_id'))
            return {'device': device}
        else:
            return {'error': 'Unknown request type'}

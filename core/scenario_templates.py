"""
预设场景模板 - 弥娅V4.0

常用终端场景和自动化模板
"""

import json
from typing import Dict, List, Optional
from .terminal_types import TerminalType

class ScenarioTemplate:
    """场景模板"""
    
    def __init__(
        self,
        name: str,
        description: str,
        category: str,
        terminals: List[Dict],
        setup_commands: Dict[str, List[str]],
        cleanup_commands: Dict[str, List[str]] = None
    ):
        self.name = name
        self.description = description
        self.category = category
        self.terminals = terminals
        self.setup_commands = setup_commands
        self.cleanup_commands = cleanup_commands or {}
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "terminals": self.terminals,
            "setup_commands": self.setup_commands,
            "cleanup_commands": self.cleanup_commands
        }

class ScenarioLibrary:
    """场景模板库"""
    
    def __init__(self):
        self.scenarios: Dict[str, ScenarioTemplate] = {}
        self._load_builtin_scenarios()
    
    def _load_builtin_scenarios(self):
        """加载内置场景"""
        
        # Python开发场景
        self.scenarios['python_dev'] = ScenarioTemplate(
            name="Python开发环境",
            description="配置Python开发所需的多终端环境",
            category="开发",
            terminals=[
                {"name": "主终端", "type": "cmd"},
                {"name": "虚拟环境", "type": "cmd"},
                {"name": "测试终端", "type": "cmd"}
            ],
            setup_commands={
                "主终端": ["python -m venv venv", "echo '主终端准备就绪'"],
                "虚拟环境": ["call venv\\Scripts\\activate.bat", "echo '虚拟环境已激活'"],
                "测试终端": ["pip install pytest", "echo '测试环境准备就绪'"]
            },
            cleanup_commands={
                "主终端": ["deactivate"],
                "测试终端": ["echo '清理完成'"]
            }
        )
        
        # Web开发场景
        self.scenarios['web_dev'] = ScenarioTemplate(
            name="Web开发环境",
            description="配置前后端分离的Web开发环境",
            category="开发",
            terminals=[
                {"name": "后端开发", "type": "cmd"},
                {"name": "前端开发", "type": "cmd"},
                {"name": "服务器", "type": "cmd"}
            ],
            setup_commands={
                "后端开发": ["cd backend", "npm install", "echo '后端环境就绪'"],
                "前端开发": ["cd frontend", "npm install", "echo '前端环境就绪'"],
                "服务器": ["npm run dev", "echo '开发服务器启动'"]
            }
        )
        
        # 服务器运维场景
        self.scenarios['server_ops'] = ScenarioTemplate(
            name="服务器运维",
            description="多服务器并行监控和运维",
            category="运维",
            terminals=[
                {"name": "Web服务器", "type": "ssh"},
                {"name": "数据库服务器", "type": "ssh"},
                {"name": "缓存服务器", "type": "ssh"}
            ],
            setup_commands={
                "Web服务器": ["htop", "df -h"],
                "数据库服务器": ["systemctl status mysql", "mysql -e 'SHOW PROCESSLIST;'"],
                "缓存服务器": ["redis-cli info", "netstat -an | grep 6379"]
            }
        )
        
        # Kali渗透场景
        self.scenarios['kali_pentest'] = ScenarioTemplate(
            name="Kali渗透测试",
            description="自动化渗透测试流程",
            category="安全",
            terminals=[
                {"name": "Kali攻击机", "type": "bash"},
                {"name": "目标机", "type": "ssh"}
            ],
            setup_commands={
                "Kali攻击机": ["nmap -sV localhost", "echo '端口扫描完成'"],
                "目标机": ["ls -la", "echo '目标机准备就绪'"]
            }
        )
        
        # 系统监控场景
        self.scenarios['system_monitor'] = ScenarioTemplate(
            name="系统监控",
            description="实时监控系统性能",
            category="监控",
            terminals=[
                {"name": "CPU监控", "type": "cmd"},
                {"name": "内存监控", "type": "cmd"},
                {"name": "磁盘监控", "type": "cmd"},
                {"name": "网络监控", "type": "cmd"}
            ],
            setup_commands={
                "CPU监控": ["typeperf -sc Processor", "echo 'CPU监控启动'"],
                "内存监控": ["wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /Value"],
                "磁盘监控": ["wmic logicaldisk get size,freespace,caption"],
                "网络监控": ["netstat -an", "echo '网络监控启动'"]
            }
        )
        
        # 日志分析场景
        self.scenarios['log_analysis'] = ScenarioTemplate(
            name="日志分析",
            description="多日志并行分析",
            category="分析",
            terminals=[
                {"name": "应用日志", "type": "cmd"},
                {"name": "系统日志", "type": "cmd"},
                {"name": "错误日志", "type": "cmd"}
            ],
            setup_commands={
                "应用日志": ["tail -f app.log"],
                "系统日志": ["tail -f /var/log/syslog"],
                "错误日志": ["grep -i error *.log"]
            }
        )
    
    def get_scenario(self, scenario_id: str) -> Optional[ScenarioTemplate]:
        """获取场景模板
        
        Args:
            scenario_id: 场景ID
            
        Returns:
            场景模板或None
        """
        return self.scenarios.get(scenario_id)
    
    def list_scenarios(self, category: str = None) -> List[Dict]:
        """列出场景
        
        Args:
            category: 类别过滤
            
        Returns:
            场景列表
        """
        
        scenarios = []
        for scenario_id, scenario in self.scenarios.items():
            if category and scenario.category != category:
                continue
            
            scenarios.append({
                "id": scenario_id,
                "name": scenario.name,
                "description": scenario.description,
                "category": scenario.category,
                "terminals_count": len(scenario.terminals)
            })
        
        return scenarios
    
    def apply_scenario(
        self,
        scenario_id: str,
        terminal_manager
    ) -> Dict:
        """应用场景
        
        Args:
            scenario_id: 场景ID
            terminal_manager: 终端管理器
            
        Returns:
            应用结果
        """
        
        scenario = self.get_scenario(scenario_id)
        
        if not scenario:
            return {
                "success": False,
                "error": f"场景不存在: {scenario_id}"
            }
        
        results = {
            "scenario_name": scenario.name,
            "terminals_created": [],
            "setup_results": {}
        }
        
        # 创建终端
        for term_config in scenario.terminals:
            try:
                session_id = await terminal_manager.create_terminal(
                    name=term_config['name'],
                    terminal_type=TerminalType.from_string(term_config.get('type', 'cmd'))
                )
                results['terminals_created'].append(session_id)
            except Exception as e:
                results['setup_errors'] = results.get('setup_errors', [])
                results['setup_errors'].append({
                    "terminal": term_config['name'],
                    "error": str(e)
                })
        
        # 执行设置命令
        for session_id, session_data in terminal_manager.sessions.items():
            session_name = session_data.name
            
            if session_name in scenario.setup_commands:
                commands = scenario.setup_commands[session_name]
                
                setup_results = []
                for cmd in commands:
                    result = await terminal_manager.execute_command(
                        session_id, cmd
                    )
                    setup_results.append({
                        "command": cmd,
                        "success": result.success
                    })
                
                results['setup_results'][session_name] = setup_results
        
        results['success'] = True
        
        return results
    
    def save_custom_scenario(
        self,
        scenario_id: str,
        scenario_data: Dict
    ):
        """保存自定义场景
        
        Args:
            scenario_id: 场景ID
            scenario_data: 场景数据
        """
        
        scenario = ScenarioTemplate(
            name=scenario_data['name'],
            description=scenario_data['description'],
            category=scenario_data.get('category', 'custom'),
            terminals=scenario_data.get('terminals', []),
            setup_commands=scenario_data.get('setup_commands', {}),
            cleanup_commands=scenario_data.get('cleanup_commands', {})
        )
        
        self.scenarios[scenario_id] = scenario

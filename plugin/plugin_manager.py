"""
弥娅 - 插件管理器
从VCPToolBox整合而来，支持本地和分布式插件
"""

import os
import json
import logging
import asyncio
import subprocess
import importlib.util
from typing import Dict, List, Optional, Any
from pathlib import Path
import aiofiles

logger = logging.getLogger(__name__)


class PluginManifest:
    """插件清单数据类"""
    def __init__(self, data: dict):
        self.name = data.get('name')
        self.display_name = data.get('displayName', self.name)
        self.plugin_type = data.get('pluginType')
        self.description = data.get('description', '')
        self.version = data.get('version', '1.0.0')
        self.author = data.get('author', '')
        self.entry_point = data.get('entryPoint', {})
        self.communication = data.get('communication', {})
        self.capabilities = data.get('capabilities', {})
        self.refresh_interval_cron = data.get('refreshIntervalCron')
        self.base_path = data.get('basePath', '')
        self.is_distributed = data.get('isDistributed', False)
        self.server_id = data.get('serverId', '')


class PluginManager:
    """插件管理器"""
    
    def __init__(self):
        self.plugins: Dict[str, PluginManifest] = {}
        self.plugin_modules: Dict[str, Any] = {}
        self.static_placeholder_values: Dict[str, Any] = {}
        self.scheduled_jobs: Dict[str, Any] = {}
        self.message_preprocessors: Dict[str, Any] = {}
        self.service_modules: Dict[str, Any] = {}
        self.preprocessor_order: List[str] = []
        self.plugin_dir = Path(__file__).parent.parent / "plugins"
        self.debug_mode = False
        self.project_base_path = Path(__file__).parent.parent.parent
        
    def set_debug_mode(self, enabled: bool):
        """设置调试模式"""
        self.debug_mode = enabled
        logger.info(f"插件管理器调试模式: {enabled}")
        
    def set_project_base_path(self, base_path: str):
        """设置项目基础路径"""
        self.project_base_path = Path(base_path)
        logger.info(f"插件管理器项目基础路径: {self.project_base_path}")
    
    async def load_plugins(self):
        """加载所有插件"""
        logger.info("[PluginManager] 开始加载插件...")
        
        # 确保插件目录存在
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        
        # 清理现有状态
        distributed_plugins = {
            name: manifest for name, manifest in self.plugins.items()
            if manifest.is_distributed
        }
        self.plugins = distributed_plugins.copy()
        self.plugin_modules.clear()
        self.static_placeholder_values.clear()
        self.service_modules.clear()
        self.message_preprocessors.clear()
        
        # 发现插件
        discovered_plugins = []
        
        for plugin_folder in self.plugin_dir.iterdir():
            if not plugin_folder.is_dir():
                continue
                
            manifest_path = plugin_folder / "plugin-manifest.json"
            if not manifest_path.exists():
                continue
                
            try:
                async with aiofiles.open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.loads(await f.read())
                
                if not manifest_data.get('name') or not manifest_data.get('pluginType'):
                    logger.warning(f"插件清单不完整: {plugin_folder.name}")
                    continue
                
                # 添加基础路径
                manifest_data['basePath'] = str(plugin_folder)
                
                manifest = PluginManifest(manifest_data)
                
                if manifest.name in self.plugins:
                    logger.warning(f"插件已存在，跳过: {manifest.name}")
                    continue
                
                # 加载插件配置
                config_env_path = plugin_folder / "config.env"
                if config_env_path.exists():
                    async with aiofiles.open(config_env_path, 'r', encoding='utf-8') as f:
                        manifest.plugin_config = {}
                        for line in (await f.read()).split('\n'):
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                key, value = line.split('=', 1)
                                manifest.plugin_config[key.strip()] = value.strip()
                
                discovered_plugins.append(manifest)
                self.plugins[manifest.name] = manifest
                logger.info(f"[PluginManager] 加载插件: {manifest.display_name} ({manifest.name})")
                
            except Exception as e:
                logger.error(f"加载插件失败 {plugin_folder.name}: {e}")
        
        # 初始化插件模块
        for plugin in discovered_plugins:
            await self._initialize_plugin(plugin)
        
        logger.info(f"[PluginManager] 插件加载完成，共 {len(self.plugins)} 个插件")
    
    async def _initialize_plugin(self, plugin: PluginManifest):
        """初始化单个插件"""
        try:
            # 加载Python插件模块
            if plugin.plugin_type in ['messagePreprocessor', 'hybridservice', 'service']:
                if plugin.entry_point.get('script'):
                    script_path = Path(plugin.base_path) / plugin.entry_point['script']
                    if script_path.exists():
                        try:
                            spec = importlib.util.spec_from_file_location(
                                f"plugin_{plugin.name}",
                                script_path
                            )
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            
                            self.plugin_modules[plugin.name] = module
                            
                            # 注册预处理器
                            if plugin.plugin_type in ['messagePreprocessor', 'hybridservice']:
                                if hasattr(module, 'processMessages'):
                                    self.message_preprocessors[plugin.name] = module
                            
                            # 注册服务模块
                            if plugin.plugin_type in ['service', 'hybridservice']:
                                self.service_modules[plugin.name] = module
                            
                            logger.info(f"[PluginManager] 插件模块加载成功: {plugin.name}")
                            
                        except Exception as e:
                            logger.error(f"插件模块加载失败 {plugin.name}: {e}")
            
            # 初始化插件
            module = self.plugin_modules.get(plugin.name)
            if module and hasattr(module, 'initialize'):
                config = getattr(plugin, 'plugin_config', {})
                config.update({
                    'PROJECT_BASE_PATH': str(self.project_base_path),
                    'DEBUG_MODE': self.debug_mode
                })
                
                try:
                    if asyncio.iscoroutinefunction(module.initialize):
                        await module.initialize(config)
                    else:
                        module.initialize(config)
                    logger.info(f"[PluginManager] 插件初始化成功: {plugin.name}")
                except Exception as e:
                    logger.error(f"插件初始化失败 {plugin.name}: {e}")
            
        except Exception as e:
            logger.error(f"初始化插件失败 {plugin.name}: {e}")
    
    async def execute_plugin(self, plugin_name: str, input_data: str = None) -> dict:
        """执行插件"""
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            return {
                "status": "error",
                "error": f"插件不存在: {plugin_name}"
            }
        
        try:
            # Python模块插件
            if plugin.plugin_type in ['messagePreprocessor', 'hybridservice', 'service']:
                module = self.plugin_modules.get(plugin_name)
                if module:
                    if hasattr(module, 'processToolCall'):
                        result = await module.processToolCall(json.loads(input_data) if input_data else {})
                        return {
                            "status": "success",
                            "result": result
                        }
            
            # 命令行插件（本地）
            if plugin.entry_point.get('command'):
                command = plugin.entry_point['command']
                env = os.environ.copy()
                
                # 注入配置
                if hasattr(plugin, 'plugin_config'):
                    env.update(plugin.plugin_config)
                
                env['PROJECT_BASE_PATH'] = str(self.project_base_path)
                
                # 执行命令
                process = await asyncio.create_subprocess_shell(
                    command,
                    cwd=plugin.base_path,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    try:
                        result = json.loads(stdout.decode('utf-8'))
                        return {
                            "status": "success",
                            "result": result
                        }
                    except json.JSONDecodeError:
                        return {
                            "status": "success",
                            "result": {"output": stdout.decode('utf-8')}
                        }
                else:
                    return {
                        "status": "error",
                        "error": stderr.decode('utf-8') or "命令执行失败"
                    }
            
            return {
                "status": "error",
                "error": "不支持的插件类型"
            }
            
        except Exception as e:
            logger.error(f"执行插件失败 {plugin_name}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def process_message(self, plugin_name: str, messages: list) -> list:
        """使用预处理器处理消息"""
        processor = self.message_preprocessors.get(plugin_name)
        if not processor or not hasattr(processor, 'processMessages'):
            return messages
        
        try:
            if asyncio.iscoroutinefunction(processor.processMessages):
                return await processor.processMessages(messages)
            else:
                return processor.processMessages(messages)
        except Exception as e:
            logger.error(f"消息预处理失败 {plugin_name}: {e}")
            return messages
    
    def get_plugin(self, plugin_name: str) -> Optional[PluginManifest]:
        """获取插件清单"""
        return self.plugins.get(plugin_name)
    
    def get_all_plugins(self) -> List[PluginManifest]:
        """获取所有插件"""
        return list(self.plugins.values())
    
    def get_placeholder_value(self, placeholder: str) -> Any:
        """获取占位符值"""
        value = self.static_placeholder_values.get(placeholder)
        if value is None:
            # 尝试带{{}}的旧格式
            value = self.static_placeholder_values.get(f"{{{{{placeholder}}}}}")
        
        if value is None:
            return f"[Placeholder {placeholder} not found]"
        
        # 处理对象格式
        if isinstance(value, dict) and 'value' in value:
            return value['value']
        
        return value
    
    def get_all_placeholders(self) -> Dict[str, Any]:
        """获取所有占位符值"""
        result = {}
        for key, value in self.static_placeholder_values.items():
            # 去除可能的{{}}
            clean_key = key.replace('{{', '').replace('}}', '')
            
            if isinstance(value, dict) and 'value' in value:
                result[clean_key] = value['value']
            else:
                result[clean_key] = value
        
        return result
    
    async def shutdown_all_plugins(self):
        """关闭所有插件"""
        logger.info("[PluginManager] 关闭所有插件...")
        
        # 调用插件的shutdown方法
        for plugin_name, module in self.plugin_modules.items():
            if hasattr(module, 'shutdown'):
                try:
                    if asyncio.iscoroutinefunction(module.shutdown):
                        await module.shutdown()
                    else:
                        module.shutdown()
                    logger.info(f"[PluginManager] 插件已关闭: {plugin_name}")
                except Exception as e:
                    logger.error(f"关闭插件失败 {plugin_name}: {e}")
        
        # 清理状态
        self.plugin_modules.clear()
        self.message_preprocessors.clear()
        self.service_modules.clear()
        
        logger.info("[PluginManager] 所有插件已关闭")


# 全局插件管理器实例
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """获取全局插件管理器实例"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager

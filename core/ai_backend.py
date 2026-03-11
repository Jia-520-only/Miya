"""
真实AI后端集成 - 弥娅V4.0

支持DeepSeek等多种AI服务的真实智能决策
"""

import asyncio
import aiohttp
import json
from typing import Dict, List, Optional, Any
from enum import Enum

class AIProvider(Enum):
    """AI服务提供商"""
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    SILICONFLOW = "siliconflow"

class AIBackend:
    """AI后端接口"""
    
    def __init__(self, provider: AIProvider = AIProvider.DEEPSEEK, config: Dict = None):
        self.provider = provider
        self.config = config or {}
        self.api_key = self.config.get('api_key', '')
        self.base_url = self.config.get('base_url', '')
        self.model = self.config.get('model', '')
        self.session = None
        
        # 初始化
        self._init_provider()
    
    def _init_provider(self):
        """初始化AI提供商"""
        
        if self.provider == AIProvider.DEEPSEEK:
            self.base_url = self.base_url or "https://api.deepseek.com/v1"
            self.model = self.model or "deepseek-chat"
        
        elif self.provider == AIProvider.OPENAI:
            self.base_url = self.base_url or "https://api.openai.com/v1"
            self.model = self.model or "gpt-4"
        
        elif self.provider == AIProvider.ANTHROPIC:
            self.base_url = self.base_url or "https://api.anthropic.com/v1"
            self.model = self.model or "claude-3-sonnet-20240229"
        
        elif self.provider == AIProvider.SILICONFLOW:
            self.base_url = self.base_url or "https://api.siliconflow.cn/v1"
            self.model = self.model or "Qwen/Qwen2.5-7B-Instruct"
    
    async def chat(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict:
        """对话
        
        Args:
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大token数
            
        Returns:
            AI响应
        """
        
        if not self.api_key:
            return {
                "success": False,
                "error": "API密钥未配置"
            }
        
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "success": True,
                        "content": data['choices'][0]['message']['content'],
                        "usage": data.get('usage', {})
                    }
                else:
                    error_text = await response.text()
                    return {
                        "success": False,
                        "error": f"API错误: {response.status}",
                        "details": error_text
                    }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def analyze_task(
        self,
        task: str,
        context: Dict
    ) -> Dict:
        """分析任务
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            分析结果
        """
        
        # 构建分析提示
        prompt = f"""分析以下任务并制定执行计划：

任务: {task}

上下文:
{json.dumps(context, indent=2, ensure_ascii=False)}

请分析：
1. 任务类型（单终端、并行、协同）
2. 需要的终端类型
3. 执行策略
4. 具体命令

请以JSON格式返回分析结果：
{{
    "task_type": "single|parallel|collaborative",
    "required_terminal_type": "cmd|powershell|bash|...",
    "strategy": "执行策略描述",
    "commands": ["具体命令列表"],
    "parallel_commands": {{
        "session_id": "command",
        ...
    }}
}}"""
        
        messages = [
            {"role": "system", "content": "你是一个智能任务分析助手，帮助用户规划和执行终端任务。"},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat(messages, temperature=0.3)
        
        if response['success']:
            try:
                # 提取JSON
                content = response['content']
                
                # 查找JSON内容
                start = content.find('{')
                end = content.rfind('}') + 1
                
                if start != -1 and end > start:
                    json_str = content[start:end]
                    analysis = json.loads(json_str)
                    
                    return {
                        "success": True,
                        "analysis": analysis,
                        "raw_response": response['content']
                    }
                else:
                    # 没有找到JSON，返回原始响应
                    return {
                        "success": True,
                        "analysis": {
                            "strategy": response['content'],
                            "task_type": "unknown"
                        },
                        "raw_response": response['content']
                    }
            
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": "无法解析AI响应",
                    "raw_response": response['content']
                }
        
        return response
    
    async def plan_collaborative_task(
        self,
        task: str
    ) -> Dict:
        """规划协同任务
        
        Args:
            task: 任务描述
            
        Returns:
            任务计划
        """
        
        prompt = f"""规划多终端协同任务：

任务: {task}

请制定详细的执行计划，包括：
1. 任务分解为多个步骤
2. 每个步骤涉及的终端
3. 步骤之间的依赖关系
4. 并行执行机会

请以JSON格式返回计划：
{{
    "steps": [
        {{
            "name": "步骤名称",
            "description": "详细描述",
            "parallel": true|false,
            "target_sessions": ["session_id1", "session_id2"],
            "commands": ["cmd1", "cmd2"]
        }}
    ]
}}"""
        
        messages = [
            {"role": "system", "content": "你是一个任务规划专家，擅长多终端协同工作。"},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat(messages, temperature=0.5)
        
        if response['success']:
            try:
                content = response['content']
                start = content.find('{')
                end = content.rfind('}') + 1
                
                if start != -1 and end > start:
                    json_str = content[start:end]
                    plan = json.loads(json_str)
                    
                    return {
                        "success": True,
                        "plan": plan,
                        "raw_response": response['content']
                    }
            
            except json.JSONDecodeError:
                pass
        
        return {
            "success": False,
            "error": "无法解析计划",
            "raw_response": response.get('content', '') if response['success'] else response.get('error', '')
        }
    
    async def analyze_terminal_status(
        self,
        status_data: Dict
    ) -> Dict:
        """分析终端状态
        
        Args:
            status_data: 所有终端状态
            
        Returns:
            分析结果
        """
        
        prompt = f"""分析终端系统状态：

终端状态:
{json.dumps(status_data, indent=2, ensure_ascii=False)}

请分析：
1. 系统整体健康状况
2. 每个终端的状态
3. 发现的问题
4. 建议的优化措施

请提供简洁的分析报告。"""
        
        messages = [
            {"role": "system", "content": "你是一个系统分析专家，擅长终端和系统状态分析。"},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat(messages, temperature=0.3)
        
        return response
    
    async def generate_fix(
        self,
        error: str,
        context: Dict
    ) -> Dict:
        """生成修复方案
        
        Args:
            error: 错误信息
            context: 上下文
            
        Returns:
            修复方案
        """
        
        prompt = f"""生成错误修复方案：

错误: {error}

上下文:
{json.dumps(context, indent=2, ensure_ascii=False)}

请生成：
1. 错误原因分析
2. 详细的修复步骤
3. 验证方法
4. 预防措施

请提供实用的修复方案。"""
        
        messages = [
            {"role": "system", "content": "你是一个问题解决专家，擅长诊断和修复技术问题。"},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat(messages, temperature=0.4)
        
        return response
    
    async def suggest_next_action(
        self,
        current_task: str,
        result: Dict,
        context: Dict
    ) -> Dict:
        """建议下一步操作
        
        Args:
            current_task: 当前任务
            result: 执行结果
            context: 上下文
            
        Returns:
            下一步建议
        """
        
        prompt = f"""建议下一步操作：

当前任务: {current_task}

执行结果:
{json.dumps(result, indent=2, ensure_ascii=False)}

上下文:
{json.dumps(context, indent=2, ensure_ascii=False)}

请建议：
1. 下一步最佳操作
2. 备选方案
3. 风险提示

请提供实用的建议。"""
        
        messages = [
            {"role": "system", "content": "你是一个智能助手，擅长分析结果并提供建议。"},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat(messages, temperature=0.5)
        
        return response
    
    async def close(self):
        """关闭连接"""
        
        if self.session:
            await self.session.close()
            self.session = None


# 便捷函数
async def create_ai_backend(config: Dict = None) -> AIBackend:
    """创建AI后端
    
    Args:
        config: 配置字典
        
    Returns:
        AIBackend实例
    """
    
    provider_name = config.get('provider', 'deepseek').lower()
    
    if provider_name == 'deepseek':
        provider = AIProvider.DEEPSEEK
    elif provider_name == 'openai':
        provider = AIProvider.OPENAI
    elif provider_name == 'anthropic':
        provider = AIProvider.ANTHROPIC
    elif provider_name == 'siliconflow':
        provider = AIProvider.SILICONFLOW
    else:
        provider = AIProvider.DEEPSEEK
    
    return AIBackend(provider, config)

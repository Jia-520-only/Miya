"""
API客户端工具

提供统一的HTTP/API调用接口，支持各种API请求。
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class APIRequest:
    """API请求"""

    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    params: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None
    json_data: Optional[Dict[str, Any]] = None
    timeout: int = 30


@dataclass
class APIResponse:
    """API响应"""

    status_code: int
    data: Any
    headers: Dict[str, str]
    elapsed_ms: float
    success: bool


class APIClient:
    """API客户端"""

    def __init__(
        self, base_url: Optional[str] = None, default_headers: Optional[Dict[str, str]] = None, timeout: int = 30
    ):
        """
        初始化API客户端

        Args:
            base_url: 基础URL
            default_headers: 默认请求头
            timeout: 超时时间（秒）
        """
        self.base_url = base_url or ""
        self.default_headers = default_headers or {}
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=self.timeout, headers=self.default_headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()

    def _build_url(self, endpoint: str) -> str:
        """
        构建完整URL

        Args:
            endpoint: 端点路径

        Returns:
            完整URL
        """
        if self.base_url and not endpoint.startswith("http"):
            endpoint = endpoint.lstrip("/")
            return f"{self.base_url}/{endpoint}"
        return endpoint

    async def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> APIResponse:
        """
        发送HTTP请求

        Args:
            method: HTTP方法（GET/POST/PUT/DELETE等）
            url: 请求URL
            headers: 请求头
            params: 查询参数
            data: 表单数据
            json_data: JSON数据

        Returns:
            API响应
        """
        start_time = datetime.now()

        if self.session is None:
            raise RuntimeError("APIClient must be used as async context manager")

        full_url = self._build_url(url)
        merged_headers = {**self.default_headers, **(headers or {})}

        try:
            async with self.session.request(
                method=method, url=full_url, headers=merged_headers, params=params, data=data, json=json_data
            ) as response:
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                response_headers = dict(response.headers)

                try:
                    response_data = await response.json()
                except:
                    response_data = await response.text()

                return APIResponse(
                    status_code=response.status,
                    data=response_data,
                    headers=response_headers,
                    elapsed_ms=elapsed,
                    success=response.status < 400,
                )

        except aiohttp.ClientError as e:
            logger.error(f"API请求失败: {method} {full_url} - {e}")
            return APIResponse(
                status_code=0,
                data={"error": str(e)},
                headers={},
                elapsed_ms=(datetime.now() - start_time).total_seconds() * 1000,
                success=False,
            )

    async def get(
        self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None
    ) -> APIResponse:
        """GET请求"""
        return await self.request("GET", url, params=params, headers=headers)

    async def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> APIResponse:
        """POST请求"""
        return await self.request("POST", url, data=data, json_data=json_data, headers=headers)

    async def put(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> APIResponse:
        """PUT请求"""
        return await self.request("PUT", url, data=data, json_data=json_data, headers=headers)

    async def delete(
        self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None
    ) -> APIResponse:
        """DELETE请求"""
        return await self.request("DELETE", url, params=params, headers=headers)

    async def batch_request(self, requests: List[APIRequest]) -> List[APIResponse]:
        """
        批量请求

        Args:
            requests: 请求列表

        Returns:
            响应列表
        """
        tasks = [
            self.request(
                req.method, req.url, headers=req.headers, params=req.params, data=req.data, json_data=req.json_data
            )
            for req in requests
        ]
        return await asyncio.gather(*tasks)

    async def health_check(self, endpoint: str = "/health") -> bool:
        """
        健康检查

        Args:
            endpoint: 健康检查端点

        Returns:
            是否健康
        """
        try:
            response = await self.get(endpoint)
            return response.success
        except:
            return False


class RESTClient(APIClient):
    """REST API客户端"""

    async def get_resource(
        self, resource_type: str, resource_id: Optional[str] = None, params: Optional[Dict[str, Any]] = None
    ) -> APIResponse:
        """
        获取资源

        Args:
            resource_type: 资源类型
            resource_id: 资源ID
            params: 查询参数

        Returns:
            API响应
        """
        url = f"/{resource_type}"
        if resource_id:
            url = f"{url}/{resource_id}"
        return await self.get(url, params=params)

    async def create_resource(self, resource_type: str, data: Dict[str, Any]) -> APIResponse:
        """
        创建资源

        Args:
            resource_type: 资源类型
            data: 资源数据

        Returns:
            API响应
        """
        return await self.post(f"/{resource_type}", json_data=data)

    async def update_resource(self, resource_type: str, resource_id: str, data: Dict[str, Any]) -> APIResponse:
        """
        更新资源

        Args:
            resource_type: 资源类型
            resource_id: 资源ID
            data: 更新数据

        Returns:
            API响应
        """
        return await self.put(f"/{resource_type}/{resource_id}", json_data=data)

    async def delete_resource(self, resource_type: str, resource_id: str) -> APIResponse:
        """
        删除资源

        Args:
            resource_type: 资源类型
            resource_id: 资源ID

        Returns:
            API响应
        """
        return await self.delete(f"/{resource_type}/{resource_id}")

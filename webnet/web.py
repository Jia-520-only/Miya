# ==================== GitHub 集成 ====================

from typing import Optional, Dict, Any, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class GitHubStore:
    """GitHub 博客存储管理"""

    def __init__(
        self,
        repo_owner: str,
        repo_name: str,
        token: Optional[str] = None,
        branch: str = "main"
    ):
        """
        初始化 GitHub 存储
        
        Args:
            repo_owner: 仓库所有者
            repo_name: 仓库名称
            token: GitHub Personal Access Token (需要 repo 权限)
            branch: 分支名称
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.token = token
        self.branch = branch
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        
        # 本地缓存路径
        self.cache_path = Path("data/blog_cache")
        self.cache_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[GitHubStore] GitHub 仓库已初始化: {repo_owner}/{repo_name}")
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers
    
    async def get_file_content(self, path: str) -> Optional[str]:
        """获取文件内容"""
        try:
            import aiohttp
            
            url = f"{self.base_url}/contents/{path}"
            params = {"ref": self.branch}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._get_headers(), params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        import base64
                        content = base64.b64decode(data["content"]).decode("utf-8")
                        
                        # 缓存到本地
                        local_path = self.cache_path / path
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        local_path.write_text(content, encoding="utf-8")
                        
                        return content
                    else:
                        logger.warning(f"[GitHubStore] 获取文件失败: {path}, 状态码: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"[GitHubStore] 获取文件异常: {e}")
            
            # 尝试从本地缓存读取
            local_path = self.cache_path / path
            if local_path.exists():
                return local_path.read_text(encoding="utf-8")
            
            return None
    
    async def list_files(self, path: str = "posts") -> List[Dict[str, str]]:
        """列出目录下的文件"""
        try:
            import aiohttp
            
            url = f"{self.base_url}/contents/{path}"
            params = {"ref": self.branch}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._get_headers(), params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [
                            {
                                "name": item["name"],
                                "path": item["path"],
                                "type": item["type"],
                                "sha": item["sha"],
                            }
                            for item in data
                            if item["type"] in ["file", "dir"]
                        ]
                    else:
                        logger.warning(f"[GitHubStore] 列出文件失败: {path}")
                        return []
        except Exception as e:
            logger.error(f"[GitHubStore] 列出文件异常: {e}")
            return []
    
    async def create_file(
        self,
        path: str,
        content: str,
        message: str
    ) -> bool:
        """创建或更新文件"""
        try:
            import aiohttp
            import base64
            
            # 检查文件是否存在
            sha = None
            existing = await self.get_file_info(path)
            if existing:
                sha = existing["sha"]
            
            url = f"{self.base_url}/contents/{path}"
            
            data = {
                "message": message,
                "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
                "branch": self.branch,
            }
            if sha:
                data["sha"] = sha
            
            async with aiohttp.ClientSession() as session:
                async with session.put(url, headers=self._get_headers(), json=data) as response:
                    if response.status in [200, 201]:
                        logger.info(f"[GitHubStore] 文件创建成功: {path}")
                        
                        # 更新本地缓存
                        local_path = self.cache_path / path
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        local_path.write_text(content, encoding="utf-8")
                        
                        return True
                    else:
                        error_data = await response.json()
                        logger.error(f"[GitHubStore] 文件创建失败: {error_data.get('message', '未知错误')}")
                        return False
        except Exception as e:
            logger.error(f"[GitHubStore] 文件创建异常: {e}")
            return False
    
    async def delete_file(self, path: str, message: str) -> bool:
        """删除文件"""
        try:
            import aiohttp
            
            # 获取文件 SHA
            file_info = await self.get_file_info(path)
            if not file_info:
                logger.warning(f"[GitHubStore] 文件不存在: {path}")
                return False
            
            url = f"{self.base_url}/contents/{path}"
            data = {
                "message": message,
                "sha": file_info["sha"],
                "branch": self.branch,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, headers=self._get_headers(), json=data) as response:
                    if response.status == 200:
                        logger.info(f"[GitHubStore] 文件删除成功: {path}")
                        
                        # 删除本地缓存
                        local_path = self.cache_path / path
                        if local_path.exists():
                            local_path.unlink()
                        
                        return True
                    else:
                        error_data = await response.json()
                        logger.error(f"[GitHubStore] 文件删除失败: {error_data.get('message', '未知错误')}")
                        return False
        except Exception as e:
            logger.error(f"[GitHubStore] 文件删除异常: {e}")
            return False
    
    async def get_file_info(self, path: str) -> Optional[Dict[str, str]]:
        """获取文件信息"""
        try:
            import aiohttp
            
            url = f"{self.base_url}/contents/{path}"
            params = {"ref": self.branch}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._get_headers(), params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return None
        except Exception as e:
            logger.error(f"[GitHubStore] 获取文件信息异常: {e}")
            return None
    
    async def sync_repo(self) -> Dict[str, Any]:
        """同步仓库到本地缓存"""
        try:
            files = await self.list_files("posts")
            synced_count = 0
            
            for file in files:
                if file["type"] == "file" and file["name"].endswith(".md"):
                    await self.get_file_content(file["path"])
                    synced_count += 1
            
            logger.info(f"[GitHubStore] 同步完成: {synced_count} 个文件")
            
            return {
                "success": True,
                "synced_count": synced_count,
                "message": f"成功同步 {synced_count} 个文件"
            }
        except Exception as e:
            logger.error(f"[GitHubStore] 同步失败: {e}")
            return {
                "success": False,
                "synced_count": 0,
                "message": str(e)
            }

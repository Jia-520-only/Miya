"""
GitHub 博客存储管理

用于将博客文章存储到 GitHub 仓库,实现版本控制和远程备份。
"""

import logging
import base64
import asyncio
from typing import Dict, List, Optional, Any
from pathlib import Path

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
    
    async def create_commit(
        self,
        files: List[Dict[str, str]],
        commit_message: str
    ) -> bool:
        """
        批量提交文件
        
        Args:
            files: 文件列表,格式 [{"path": "posts/test.md", "content": "..."}, ...]
            commit_message: 提交消息
        """
        try:
            import aiohttp
            
            # 获取最新的提交 SHA
            url = f"{self.base_url}/git/refs/heads/{self.branch}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._get_headers()) as response:
                    if response.status != 200:
                        logger.error(f"[GitHubStore] 获取提交 SHA 失败")
                        return False
                    ref_data = await response.json()
                    latest_commit_sha = ref_data["object"]["sha"]
            
            # 获取树 SHA
            url = f"{self.base_url}/git/commits/{latest_commit_sha}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._get_headers()) as response:
                    if response.status != 200:
                        logger.error(f"[GitHubStore] 获取树 SHA 失败")
                        return False
                    commit_data = await response.json()
                    tree_sha = commit_data["tree"]["sha"]
            
            # 创建新的树
            tree_items = []
            for file in files:
                # 先创建 blob
                blob_url = f"{self.base_url}/git/blobs"
                blob_data = {
                    "content": base64.b64encode(file["content"].encode("utf-8")).decode("utf-8"),
                    "encoding": "base64"
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(blob_url, headers=self._get_headers(), json=blob_data) as response:
                        if response.status != 201:
                            logger.error(f"[GitHubStore] 创建 blob 失败: {file['path']}")
                            return False
                        blob_data = await response.json()
                        blob_sha = blob_data["sha"]
                
                tree_items.append({
                    "path": file["path"],
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha
                })
            
            # 创建新树
            url = f"{self.base_url}/git/trees"
            tree_data = {
                "base_tree": tree_sha,
                "tree": tree_items
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self._get_headers(), json=tree_data) as response:
                    if response.status != 201:
                        logger.error(f"[GitHubStore] 创建树失败")
                        return False
                    tree_result = await response.json()
                    new_tree_sha = tree_result["sha"]
            
            # 创建新提交
            url = f"{self.base_url}/git/commits"
            commit_data = {
                "message": commit_message,
                "tree": new_tree_sha,
                "parents": [latest_commit_sha]
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self._get_headers(), json=commit_data) as response:
                    if response.status != 201:
                        logger.error(f"[GitHubStore] 创建提交失败")
                        return False
                    commit_result = await response.json()
                    new_commit_sha = commit_result["sha"]
            
            # 更新分支
            url = f"{self.base_url}/git/refs/heads/{self.branch}"
            ref_data = {
                "sha": new_commit_sha
            }
            async with aiohttp.ClientSession() as session:
                async with session.patch(url, headers=self._get_headers(), json=ref_data) as response:
                    if response.status != 200:
                        logger.error(f"[GitHubStore] 更新分支失败")
                        return False
            
            logger.info(f"[GitHubStore] 批量提交成功: {len(files)} 个文件")
            return True
            
        except Exception as e:
            logger.error(f"[GitHubStore] 批量提交异常: {e}")
            return False

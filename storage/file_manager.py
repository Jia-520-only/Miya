"""
弥娅 - 文件管理器
从VCPChat整合而来，提供文件上传、下载、管理功能
"""

import os
import logging
import hashlib
import aiofiles
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import mimetypes

logger = logging.getLogger(__name__)


class FileManager:
    """文件管理器"""
    
    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent.parent / "storage" / "files"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建子目录
        (self.base_dir / "uploads").mkdir(exist_ok=True)
        (self.base_dir / "downloads").mkdir(exist_ok=True)
        (self.base_dir / "temp").mkdir(exist_ok=True)
        
        # 元数据文件
        self.metadata_file = self.base_dir / "metadata.json"
        self.metadata: Dict[str, dict] = {}
        self._load_metadata()
        
        logger.info(f"文件管理器初始化完成: {self.base_dir}")
    
    def _load_metadata(self):
        """加载文件元数据"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            except Exception as e:
                logger.error(f"加载文件元数据失败: {e}")
                self.metadata = {}
        else:
            self.metadata = {}
    
    def _save_metadata(self):
        """保存文件元数据"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存文件元数据失败: {e}")
    
    def _generate_file_id(self, filename: str) -> str:
        """生成文件ID"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = "".join(c for c in filename if c.isalnum() or c in '._-')
        return f"{timestamp}_{safe_name}"
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件哈希"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    async def save_file(
        self, 
        file_data: bytes, 
        filename: str, 
        category: str = "uploads",
        metadata: dict = None
    ) -> dict:
        """保存文件"""
        try:
            # 生成文件ID
            file_id = self._generate_file_id(filename)
            file_ext = Path(filename).suffix
            
            # 确定存储路径
            if category == "uploads":
                storage_dir = self.base_dir / "uploads"
            elif category == "downloads":
                storage_dir = self.base_dir / "downloads"
            else:
                storage_dir = self.base_dir / category
                storage_dir.mkdir(exist_ok=True)
            
            # 保存文件
            file_path = storage_dir / f"{file_id}{file_ext}"
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_data)
            
            # 计算文件信息
            file_size = len(file_data)
            file_hash = self._calculate_file_hash(file_path)
            mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
            
            # 保存元数据
            file_metadata = {
                "file_id": file_id,
                "original_name": filename,
                "file_path": str(file_path),
                "file_size": file_size,
                "file_hash": file_hash,
                "mime_type": mime_type,
                "category": category,
                "upload_time": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            self.metadata[file_id] = file_metadata
            self._save_metadata()
            
            logger.info(f"文件保存成功: {filename} -> {file_id}")
            
            return {
                "success": True,
                "file_id": file_id,
                "metadata": file_metadata
            }
            
        except Exception as e:
            logger.error(f"保存文件失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_file(self, file_id: str) -> Optional[Tuple[bytes, dict]]:
        """获取文件内容"""
        try:
            file_metadata = self.metadata.get(file_id)
            if not file_metadata:
                logger.warning(f"文件不存在: {file_id}")
                return None
            
            file_path = Path(file_metadata["file_path"])
            if not file_path.exists():
                logger.warning(f"文件路径不存在: {file_path}")
                return None
            
            # 读取文件
            async with aiofiles.open(file_path, 'rb') as f:
                file_data = await f.read()
            
            return (file_data, file_metadata)
            
        except Exception as e:
            logger.error(f"获取文件失败: {e}")
            return None
    
    async def delete_file(self, file_id: str) -> bool:
        """删除文件"""
        try:
            file_metadata = self.metadata.get(file_id)
            if not file_metadata:
                logger.warning(f"文件不存在: {file_id}")
                return False
            
            file_path = Path(file_metadata["file_path"])
            if file_path.exists():
                file_path.unlink()
            
            del self.metadata[file_id]
            self._save_metadata()
            
            logger.info(f"文件删除成功: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False
    
    def list_files(self, category: str = None, limit: int = 100) -> List[dict]:
        """列出文件"""
        try:
            files = []
            
            for file_id, metadata in self.metadata.items():
                if category and metadata.get('category') != category:
                    continue
                
                files.append({
                    "file_id": file_id,
                    "filename": metadata.get('original_name'),
                    "size": metadata.get('file_size'),
                    "mime_type": metadata.get('mime_type'),
                    "upload_time": metadata.get('upload_time')
                })
            
            # 按时间排序，取最新的
            files.sort(key=lambda x: x['upload_time'], reverse=True)
            
            return files[:limit]
            
        except Exception as e:
            logger.error(f"列出文件失败: {e}")
            return []
    
    def search_files(self, keyword: str, limit: int = 50) -> List[dict]:
        """搜索文件"""
        try:
            results = []
            keyword_lower = keyword.lower()
            
            for file_id, metadata in self.metadata.items():
                filename = metadata.get('original_name', '').lower()
                file_metadata_str = json.dumps(metadata, ensure_ascii=False).lower()
                
                if keyword_lower in filename or keyword_lower in file_metadata_str:
                    results.append({
                        "file_id": file_id,
                        "filename": metadata.get('original_name'),
                        "size": metadata.get('file_size'),
                        "mime_type": metadata.get('mime_type'),
                        "upload_time": metadata.get('upload_time')
                    })
            
            # 按时间排序
            results.sort(key=lambda x: x['upload_time'], reverse=True)
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"搜索文件失败: {e}")
            return []
    
    async def update_file_metadata(self, file_id: str, new_metadata: dict) -> bool:
        """更新文件元数据"""
        try:
            if file_id not in self.metadata:
                logger.warning(f"文件不存在: {file_id}")
                return False
            
            # 合并元数据
            self.metadata[file_id]['metadata'].update(new_metadata)
            self.metadata[file_id]['update_time'] = datetime.now().isoformat()
            
            self._save_metadata()
            
            logger.info(f"文件元数据更新成功: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"更新文件元数据失败: {e}")
            return False
    
    def get_stats(self) -> dict:
        """获取文件管理统计"""
        try:
            total_files = len(self.metadata)
            total_size = sum(m.get('file_size', 0) for m in self.metadata.values())
            
            # 按类别统计
            category_stats = {}
            for metadata in self.metadata.values():
                category = metadata.get('category', 'unknown')
                if category not in category_stats:
                    category_stats[category] = {'count': 0, 'size': 0}
                category_stats[category]['count'] += 1
                category_stats[category]['size'] += metadata.get('file_size', 0)
            
            return {
                "total_files": total_files,
                "total_size": total_size,
                "total_size_mb": round(total_size / 1024 / 1024, 2),
                "category_stats": category_stats
            }
            
        except Exception as e:
            logger.error(f"获取文件统计失败: {e}")
            return {}


# 全局文件管理器实例
_file_manager: Optional[FileManager] = None


def get_file_manager(base_dir: str = None) -> FileManager:
    """获取全局文件管理器实例"""
    global _file_manager
    if _file_manager is None:
        _file_manager = FileManager(base_dir)
    return _file_manager

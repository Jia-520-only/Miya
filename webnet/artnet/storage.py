"""
图片存储管理 — 本地文件系统 + JSON 索引
"""

import json
import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("artnet.storage")


class ArtStorage:
    """图片存储管理

    目录结构:
      data/artwork/images/    — 图片文件
      data/artwork/index.json — 图片索引
    """

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent.parent.parent / "data" / "artwork"
        self.base_dir = base_dir
        self.images_dir = self.base_dir / "images"
        self.index_path = self.base_dir / "index.json"
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        image_data: bytes,
        *,
        task_id: str = "",
        provider: str = "",
        prompt: str = "",
        filename: str = "",
        metadata: dict | None = None,
    ) -> dict:
        """保存一张图片并记录索引"""
        if not filename:
            timestamp = int(time.time() * 1000)
            filename = f"{provider}_{timestamp}.png"

        filepath = self.images_dir / filename
        filepath.write_bytes(image_data)

        entry = {
            "id": task_id or f"img_{int(time.time())}",
            "filename": filename,
            "path": str(filepath.relative_to(self.base_dir.parent)),
            "size": len(image_data),
            "provider": provider,
            "prompt": prompt[:200],
            "width": 0,
            "height": 0,
            "created_at": datetime.now(datetime.UTC).isoformat(),
            "metadata": metadata or {},
        }

        try:
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(image_data))
            entry["width"] = img.width
            entry["height"] = img.height
        except Exception:
            pass

        index = self._read_index()
        index["images"].insert(0, entry)
        index["total"] = len(index["images"])
        self._write_index(index)

        logger.info(f"[ArtStorage] 已保存: {filename} ({len(image_data)} bytes)")
        return entry

    def save_batch(
        self,
        images: list[bytes],
        *,
        task_id: str = "",
        provider: str = "",
        prompt: str = "",
    ) -> list[dict]:
        """批量保存图片"""
        results = []
        for i, img_data in enumerate(images):
            filename = f"{provider}_{task_id}_{i}.png"
            entry = self.save(
                img_data,
                task_id=f"{task_id}_{i}",
                provider=provider,
                prompt=prompt,
                filename=filename,
            )
            results.append(entry)
        return results

    def get(self, filename: str) -> Optional[bytes]:
        """读取图片数据"""
        filepath = self.images_dir / filename
        if not filepath.exists():
            return None
        return filepath.read_bytes()

    def get_entry(self, image_id: str) -> Optional[dict]:
        """获取图片索引条目"""
        index = self._read_index()
        for img in index["images"]:
            if img["id"] == image_id:
                return img
        return None

    def list_images(
        self,
        *,
        provider: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """列出图片"""
        index = self._read_index()
        images = index["images"]
        if provider:
            images = [i for i in images if i.get("provider") == provider]
        return images[offset : offset + limit]

    def delete(self, image_id: str) -> bool:
        """删除图片"""
        index = self._read_index()
        for i, img in enumerate(index["images"]):
            if img["id"] == image_id:
                filepath = self.images_dir / img["filename"]
                try:
                    os.remove(filepath)
                except OSError:
                    pass
                index["images"].pop(i)
                index["total"] = len(index["images"])
                self._write_index(index)
                return True
        return False

    def delete_all(self) -> int:
        """删除所有图片"""
        count = 0
        try:
            if self.images_dir.exists():
                shutil.rmtree(self.images_dir)
                count += 1
            self.images_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"[ArtStorage] 清理图片目录失败: {e}")

        index = self._read_index()
        old_count = len(index["images"])
        index["images"] = []
        index["total"] = 0
        self._write_index(index)
        return old_count

    def stats(self) -> dict:
        """统计信息"""
        index = self._read_index()
        total_size = 0
        for img in index["images"]:
            try:
                filepath = self.images_dir / img["filename"]
                total_size += filepath.stat().st_size
            except OSError:
                pass
        return {
            "total_images": len(index["images"]),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }

    def _read_index(self) -> dict:
        if not self.index_path.exists():
            return {"images": [], "total": 0}
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            return {"images": [], "total": 0}

    def _write_index(self, index: dict):
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

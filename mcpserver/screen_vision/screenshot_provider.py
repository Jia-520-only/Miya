"""
跨平台截图提供器 — 从 NagaAgent 解耦提取

支持: Windows (mss), macOS (mss + screencapture), Linux (grim/scrot/gnome-screenshot)
"""

import base64
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ScreenshotResult:
    data_url: str
    width: int
    height: int
    monitor_index: int
    source: str = "screen"


class ScreenshotProvider:
    TEST_IMAGE_ENV: str = "MIYA_TEST_PIC_PATH"

    def capture_data_url(self, monitor_index: int = 1) -> ScreenshotResult:
        test_image_path = self._resolve_test_image_path()
        if test_image_path is not None:
            return ScreenshotResult(
                data_url=self._file_to_data_url(test_image_path),
                width=0,
                height=0,
                monitor_index=0,
                source=f"env:{self.TEST_IMAGE_ENV}",
            )

        use_monitor_index = max(monitor_index, 1)
        errors: list[str] = []

        for backend_name, backend_fn in self._get_backends():
            try:
                return backend_fn(use_monitor_index)
            except Exception as exc:
                errors.append(f"{backend_name}: {exc}")

        raise RuntimeError(
            "所有截图方式均失败:\n  "
            + "\n  ".join(errors)
            + "\n提示: 设置环境变量 MIYA_TEST_PIC_PATH 指向图片文件作为替代"
        )

    def _get_backends(self) -> list[tuple[str, Any]]:
        system = platform.system()
        backends: list[tuple[str, Any]] = []

        if system == "Windows":
            backends.append(("mss", self._capture_mss))
        elif system == "Darwin":
            backends.append(("mss", self._capture_mss))
            if shutil.which("screencapture"):
                backends.append(("screencapture", self._capture_macos_screencapture))
        else:
            if os.environ.get("WAYLAND_DISPLAY"):
                if shutil.which("grim"):
                    backends.append(("grim", self._capture_grim))
                if shutil.which("gnome-screenshot"):
                    backends.append(("gnome-screenshot", self._capture_gnome_screenshot))
                if os.environ.get("DISPLAY"):
                    backends.append(("mss", self._capture_mss))
            elif os.environ.get("DISPLAY"):
                backends.append(("mss", self._capture_mss))
                if shutil.which("scrot"):
                    backends.append(("scrot", self._capture_scrot))
                if shutil.which("gnome-screenshot"):
                    backends.append(("gnome-screenshot", self._capture_gnome_screenshot))
            else:
                if shutil.which("grim"):
                    backends.append(("grim", self._capture_grim))
                if shutil.which("gnome-screenshot"):
                    backends.append(("gnome-screenshot", self._capture_gnome_screenshot))
                backends.append(("mss", self._capture_mss))

        return backends

    def _capture_mss(self, monitor_index: int) -> ScreenshotResult:
        import mss
        import mss.tools

        with mss.mss() as sct:
            monitors: list[dict[str, Any]] = list(sct.monitors)
            if monitor_index < 1 or monitor_index >= len(monitors):
                monitor_index = 1
            monitor = monitors[monitor_index]
            shot = sct.grab(monitor)
            png_bytes = mss.tools.to_png(shot.rgb, shot.size)
            if png_bytes is None:
                raise RuntimeError("mss 返回空图片数据")
            encoded = base64.b64encode(png_bytes).decode("ascii")
            return ScreenshotResult(
                data_url=f"data:image/png;base64,{encoded}",
                width=int(shot.width),
                height=int(shot.height),
                monitor_index=monitor_index,
                source="mss",
            )

    def _capture_grim(self, monitor_index: int) -> ScreenshotResult:
        return self._capture_via_command(["grim", "-"], source="grim", read_stdout=True)

    def _capture_scrot(self, monitor_index: int) -> ScreenshotResult:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            subprocess.run(["scrot", tmp_path], check=True, capture_output=True, timeout=10)
            return self._result_from_file(Path(tmp_path), source="scrot")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _capture_gnome_screenshot(self, monitor_index: int) -> ScreenshotResult:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            subprocess.run(
                ["gnome-screenshot", "-f", tmp_path],
                check=True,
                capture_output=True,
                timeout=10,
            )
            return self._result_from_file(Path(tmp_path), source="gnome-screenshot")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _capture_macos_screencapture(self, monitor_index: int) -> ScreenshotResult:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            cmd = ["screencapture", "-x"]
            if monitor_index >= 1:
                cmd.extend(["-D", str(monitor_index)])
            cmd.append(tmp_path)
            subprocess.run(cmd, check=True, capture_output=True, timeout=10)
            return self._result_from_file(Path(tmp_path), source="screencapture")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _capture_via_command(self, cmd: list[str], source: str, read_stdout: bool = False) -> ScreenshotResult:
        result = subprocess.run(cmd, check=True, capture_output=True, timeout=10)
        png_bytes = result.stdout
        if not png_bytes:
            raise RuntimeError(f"{source} 未返回数据")
        encoded = base64.b64encode(png_bytes).decode("ascii")
        return ScreenshotResult(
            data_url=f"data:image/png;base64,{encoded}",
            width=0,
            height=0,
            monitor_index=0,
            source=source,
        )

    def _result_from_file(self, file_path: Path, source: str) -> ScreenshotResult:
        if not file_path.exists() or file_path.stat().st_size == 0:
            raise RuntimeError(f"{source} 未生成截图文件")
        png_bytes = file_path.read_bytes()
        encoded = base64.b64encode(png_bytes).decode("ascii")
        return ScreenshotResult(
            data_url=f"data:image/png;base64,{encoded}",
            width=0,
            height=0,
            monitor_index=0,
            source=source,
        )

    def _resolve_test_image_path(self) -> Path | None:
        raw_path = os.getenv(self.TEST_IMAGE_ENV, "").strip()
        if not raw_path:
            return None
        test_path = Path(raw_path).expanduser()
        if not test_path.is_absolute():
            test_path = (Path.cwd() / test_path).resolve()
        if not test_path.exists() or not test_path.is_file():
            raise FileNotFoundError(f"环境变量 {self.TEST_IMAGE_ENV} 指向的文件不存在: {test_path}")
        return test_path

    def _file_to_data_url(self, file_path: Path) -> str:
        mime_type = self._guess_image_mime(file_path)
        image_bytes = file_path.read_bytes()
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def _guess_image_mime(file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        mapping: dict[str, str] = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
        }
        mime_type = mapping.get(suffix)
        if mime_type is None:
            raise ValueError(f"不支持的图片格式: {file_path.suffix}")
        return mime_type


def compress_screenshot_data_url(data_url: str, max_width: int = 1280, quality: int = 80) -> str:
    """缩放截图到 max_width，转 JPEG 压缩。典型 8MB → 200KB，缩小 30-40 倍。"""
    import io

    from PIL import Image

    _header, b64data = data_url.split(",", 1)
    img_bytes = base64.b64decode(b64data)
    img = Image.open(io.BytesIO(img_bytes))

    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


_provider: ScreenshotProvider | None = None


def get_screenshot_provider() -> ScreenshotProvider:
    global _provider
    if _provider is None:
        _provider = ScreenshotProvider()
    return _provider

"""Contracts that fail silently, so they need a test rather than a code review.

Two of them, both measured in production:

* **Frontend/backend field names.** The API layer runs every response through
  ``camelcaseKeys``, so a component reading ``usable_indices`` gets ``undefined``
  - no error, no warning, just a feature that quietly never works. Three separate
  camera features were dead that way.
* **One camera at a time.** Several of Jia's cameras share one USB controller. A
  device that is already streaming makes the others fail to start their
  DirectShow pins, so the 4K camera pointed at his face reported "cannot open"
  for as long as the laptop camera's reader held the bus. Reading the cameras
  concurrently again would restore that bug without breaking any existing test.

Both are asserted against the source, because that is where the wiring lives.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAMERA_VISION = ROOT / "miya_frontend" / "src" / "utils" / "cameraVision.ts"
VISION_AGENT = ROOT / "mcpserver" / "screen_vision" / "vision_agent.py"
CORE_API = ROOT / "miya_frontend" / "src" / "api" / "core.ts"


def _code_only(text: str) -> str:
    """Strip comments, so a comment quoting the old key is not a failure.

    The fix for this very bug leaves a comment naming `usable_indices` to explain
    what went wrong; the test has to look at code, not at prose.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def test_the_frontend_never_reads_a_snake_case_field_name():
    """`usable_indices` is `usableIndices` by the time any component sees it."""
    source = _code_only(CAMERA_VISION.read_text(encoding="utf-8"))

    for snake in (
        "usable_indices",
        "sleeping_indices",
        "unopenable_indices",
        "browser_owned",
        "backend_owned",
        "readers_running",
        "usable_count",
        "default_index",
    ):
        assert snake not in source, (
            f"cameraVision.ts 又在代码里读 snake_case 的 {snake!r}："
            "响应经过 camelcaseKeys，这个键永远取不到值，而且不会报错"
        )

    for camel in ("usableIndices", "sleepingIndices", "browserOwned", "backendOwned"):
        assert camel in source, f"cameraVision.ts 应该读取 {camel}"


def test_the_api_types_describe_the_keys_that_actually_arrive():
    """The declared response types must name the camelCase keys, or they lie."""
    source = CORE_API.read_text(encoding="utf-8")

    assert "usableIndices" in source and "sleepingIndices" in source
    assert "browserOwned" in source and "backendOwned" in source
    assert "readersRunning" in source
    assert "usable_indices?: number[]" not in source, "类型声明不能再写 snake_case"


def test_camera_control_persists_stable_source_identity():
    """A selected camera must survive OpenCV index reordering."""
    source = (ROOT / "core" / "camera_control.py").read_text(encoding="utf-8")
    api = (ROOT / "miya_frontend" / "src" / "api" / "core.ts").read_text(encoding="utf-8")

    assert "camera_source_ids" in source
    assert "preferred_source_id" in source
    assert "camera_source_ids?: string[]" in api
    assert "preferred_source_id?: string" in api


def test_frontend_preserves_browser_source_ids_before_clearing_preview_state():
    """Stopping preview must release every browser-owned source on the backend."""
    source = CAMERA_VISION.read_text(encoding="utf-8")
    source_ids = "const releasedBrowserSourceIds = activeBrowserSources.value.map(item => item.sourceId)"
    clear_sources = "activeBrowserSources.value = []"
    release_payload = "browser_source_ids: releasedBrowserSourceIds"

    assert source_ids in source
    assert release_payload in source
    assert source.index(source_ids) < source.index(clear_sources) < source.index(release_payload)


def test_legacy_single_camera_index_is_migrated_to_stable_source(monkeypatch):
    """The first post-upgrade observation binds the already-selected named device."""
    from mcpserver.screen_vision.vision_agent import VisionAgent

    class _Source:
        def to_dict(self):
            return {"source_id": "dshow:face-camera", "name": "4K USB Camera"}

    class _Manager:
        def refresh_names(self):
            return [0]

        def sources(self):
            return {0: _Source()}

        def name_for(self, index):
            return "4K USB Camera" if index == 0 else ""

    saved = {}
    monkeypatch.setattr("core.camera_control.read_state", lambda: {
        "mode": "companion",
        "camera_policy": "single",
        "camera_indices": [0],
        "preferred_index": 0,
        "camera_source_ids": [],
        "preferred_source_id": None,
    })
    monkeypatch.setattr(
        "core.camera_control.write_state",
        lambda mode, **kwargs: saved.update({"mode": mode, **kwargs}) or saved,
    )

    policy, selected, preferred, _browser, _preferred_browser, locked = VisionAgent._camera_selection(_Manager())

    assert policy == "single"
    assert selected == {0}
    assert preferred == 0
    assert locked is True
    assert saved["preferred_source_id"] == "dshow:face-camera"
    assert saved["camera_source_ids"] == ["dshow:face-camera"]


def test_the_inventory_reports_what_each_camera_saw():
    """The backend must expose per-camera content, not only "it works"."""
    from mcpserver.screen_vision.camera_manager import CameraSource

    described = CameraSource(index=2, name="4K USB Camera").to_dict()

    for key in ("name", "label", "usable", "openable", "reason", "sees_people",
                "last_faces", "last_action", "last_reading_text", "last_reading_at"):
        assert key in described, f"设备清单缺少 {key}，面板无法说明这一路看到了什么"


def test_the_observation_loop_reads_one_camera_at_a_time():
    """Sequential observation is the fix; concurrent readers undo it."""
    source = VISION_AGENT.read_text(encoding="utf-8")

    assert "pool.stop_all" in source, (
        "观察前必须释放所有常驻读帧，否则占用 USB 总线的那一路会把其它摄像头挤死"
    )
    assert "manager.all_indices()" in source, (
        "观察必须遍历设备清单里的每一路，而不是只遍历上一轮认为可用的那几路"
    )

    # Everything from the per-camera loop up to the single reader restart that
    # follows it must not open a second device.
    loop_start = source.index("for index in manager.all_indices():")
    loop_end = source.index("Hold exactly one camera open")
    assert loop_start < loop_end, "找不到逐路观察循环的结束位置，测试需要跟着代码更新"
    assert "pool.start_reader" not in source[loop_start:loop_end], (
        "逐路观察的循环里不能再启动常驻读帧，那会让后面每一路都打不开"
    )
    assert "pool.start_reader" in source[loop_end:], (
        "循环之外仍应保留一个常驻读帧，否则姿态采样就只剩每轮一次"
    )


def test_autonomous_vision_checks_identity_before_calling_someone_jia():
    """Unenrolled or unknown faces must not be promoted to the user."""
    source = VISION_AGENT.read_text(encoding="utf-8")

    assert "identity=True" in source
    assert "身份未登记或未知时" in source
    assert "只能说画面里的人、有人" in source


def test_the_sweep_does_not_probe_before_it_walks():
    """The walk *is* the probe; probing first opened every device twice.

    Measured at 6.6 seconds of pure duplication per sweep on this machine - the
    inventory probe opened all three cameras and then the walk opened them again.
    """
    source = VISION_AGENT.read_text(encoding="utf-8")

    assert "manager.refresh_names()" in source, "巡检应该只刷新设备名"
    assert "manager.scan(force=True)" not in source, (
        "巡检不能先做一遍全量探测——那会把每台设备开两次"
    )


def test_the_inventory_can_be_refreshed_without_opening_anything(monkeypatch):
    """Name refresh must be pure bookkeeping, or it is just a probe by another name."""
    from mcpserver.screen_vision import camera_devices, camera_manager, camera_names

    monkeypatch.setattr(camera_names, "dshow_device_names",
                        lambda **_kwargs: ["Integrated Camera", "4K USB Camera"])
    probed: list[int] = []
    monkeypatch.setattr(camera_devices, "list_camera_devices",
                        lambda **_kwargs: probed.append(1) or {"devices": []})

    manager = camera_manager.CameraManager()
    indices = manager.refresh_names()

    assert indices == [0, 1]
    assert not probed, "刷新设备名不该去开任何设备"
    names = [item["name"] for item in manager.describe()["devices"]]
    assert names == ["Integrated Camera", "4K USB Camera"]


def test_tests_never_write_miyas_real_notes_file():
    """The guard that took a data loss to notice.

    Two test files drove the real agency singleton, whose store is
    ``data/camera_vision_agent.json``. Because ``record()`` saves, running the
    suite replaced Jia's intents and impressions with test fixtures - and the
    file is gitignored, so there was nothing to restore from. ``conftest.py`` now
    hands every test a temporary store; this asserts that it stays that way.
    """
    from mcpserver.screen_vision import vision_agent

    agency = vision_agent.get_vision_agency()

    assert Path(agency._path) != Path(vision_agent.DEFAULT_STORE_PATH), (
        "测试拿到了生产笔记文件，跑一次测试就会覆盖佳的观察记录"
    )

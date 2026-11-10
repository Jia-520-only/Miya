"""Exercise the built observatory against an isolated, changing SSE fixture.

Run after the renderer build: .venv/Scripts/python tests/browser/observatory_smoke.py
No live models, cameras, platforms or user data are used.
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(tempfile.mkdtemp(prefix="miya-observatory-preview-")))
    parser.add_argument(
        "--frontend-url", help="Optionally exercise a running frontend against the isolated API fixture"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    import sys

    sys.path.insert(0, str(ROOT))
    import core.observatory
    import core.log_stream
    from core.log_stream import LogStreamBuffer
    from core.management_api import ManagementAPI
    from core.observatory import ObservatoryNoteStore, ObservatoryService, utc_now
    from core.web_api.miya_api import MiyaAPI

    with tempfile.TemporaryDirectory(prefix="miya-observatory-fixture-") as directory:
        state = {"connected": True, "phase": "IDLE", "messages": 8, "memory": 2048}
        personality = SimpleNamespace(current_form="gentle", get_form_config=lambda _: {"name": "温柔的弥娅"})
        emotion = SimpleNamespace(
            get_emotion_state=lambda: {
                "dominant": "joy",
                "intensity": 0.72,
                "current": {"joy": 0.72, "love": 0.6, "calm": 0.4},
            }
        )
        service = ObservatoryService(
            SimpleNamespace(personality=personality, emotion=emotion), store=ObservatoryNoteStore(Path(directory))
        )
        service.store.write(
            {
                "id": "fixture-note",
                "title": "把今天的微光，\n留给你。",
                "body": "佳，愿你在忙碌的间隙，也能有一小片安静。我把这句话留在这里，等你慢慢读。",
                "created_at": utc_now(),
                "persona_name": "温柔的弥娅",
            }
        )
        service._platforms = lambda: {"online_count": 2, "enabled_count": 3}
        service._lifecycle = lambda: {
            "phase": state["phase"],
            "message_count": state["messages"],
            "observed_at": utc_now(),
        }

        async def memory():
            return {
                "total": state["memory"],
                "layers": {
                    key: value * (100000 if state.get("large_counts") else 1)
                    for key, value in {
                        "dialogue": 1000,
                        "short_term": 400,
                        "long_term": 500,
                        "semantic": 90,
                        "knowledge": 50,
                        "pinned": 8,
                    }.items()
                },
            }

        service._memory = memory
        collect = service.snapshot

        async def snapshot():
            return await collect() if state["connected"] else {"success": False}

        service.snapshot = snapshot
        core.observatory._service = service
        api = MiyaAPI(service.hub)
        app = FastAPI()
        app.add_middleware(CORSMiddleware, allow_origins=["*"])
        app.router.routes.extend(route for route in api.router.routes if route.path.startswith("/api/observatory/"))

        log_buffer = LogStreamBuffer()
        core.log_stream._buffer = log_buffer
        log_api = ManagementAPI(SimpleNamespace())
        app.router.routes.extend(route for route in log_api.app.routes if route.path.startswith("/api/v1/logs"))
        for name, text in (
            ("Miya.MemoryBus", "六层记忆索引已就绪"),
            ("memory.historian.worker", "最近记录整理完成"),
            ("Miya.Spine", "进入安静陪伴状态"),
            ("Tool.web_search", "检索任务执行完成"),
            ("Miya.Platform.OneBot", "平台连接已建立"),
            ("core.multi_vision_analyzer", "视觉来源已连接"),
            ("uvicorn.access", "GET /api/observatory/snapshot HTTP/1.1 200"),
        ):
            log_buffer.add("INFO", name, text)

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        @app.get("/api/{path:path}")
        async def unrelated_fixture(path: str):
            if path == "earth/notes":
                return []
            return {"success": False, "state": {"mode": "off"}, "data": [], "tracks": []}

        @app.websocket("/api/v1/ws")
        async def empty_platform_socket(ws: WebSocket):
            await ws.accept()
            await ws.send_json({"type": "initial_state", "platforms": []})
            try:
                while True:
                    await ws.receive_text()
            except Exception:
                pass

        app.mount("/", StaticFiles(directory=ROOT / "miya_frontend" / "dist", html=True))
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        if not server.started:
            raise RuntimeError("Fixture server failed to start")
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="msedge", headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
                context.add_init_script(
                    f"window.__MIYA_API_PORT__ = {port}; window.__MIYA_MANAGEMENT_PORT__ = {port}; localStorage.setItem('miya-home-gallery-visible', 'false');"
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(error.stack or str(error)))
                frontend_url = args.frontend_url or f"http://127.0.0.1:{port}"
                page.goto(f"{frontend_url.rstrip('/')}/#/observatory")
                expect(page.locator(".presence-note h2")).to_have_text("把今天的微光，\n留给你。")
                expect(page.locator(".connection-summary")).to_contain_text("实时同步")
                expect(page.locator(".observatory-view")).to_have_css("opacity", "1")
                scene = page.frames[1]
                scene.wait_for_function("window.MiyaFlux.geometry && window.MiyaFlux.state.composition === 'complete'")
                expect(page.locator(".ring-label")).to_have_count(6)
                expect(page.locator(".runtime-heading small")).to_have_text("● 日志实时连接")
                expect(page.locator(".log-ribbon")).to_have_count(6)
                expect(page.locator(".runtime-ring").nth(1).locator(".core-value")).to_have_text("0")
                expect(page.locator(".runtime-ring").nth(2).locator(".core-value")).to_have_text("2 / 3")
                expect(page.locator(".runtime-bridge g")).to_have_count(3)
                assert "GET /api/observatory" not in page.locator(".runtime-station").inner_text()
                log_buffer.add("INFO", "Tool.web_search", "星图资料检索完成")
                log_buffer.add("WARNING", "Miya.Platform.OneBot", "平台重连完成，保留原始诊断")
                expect(page.locator(".runtime-ring").nth(1).locator(".core-value")).to_have_text("1")
                expect(page.locator(".event-trace")).to_have_count(2)
                expect(page.locator(".event-trace.is-warning")).to_have_css("stroke", "rgb(232, 200, 159)")
                expect(page.locator(".runtime-transfer[data-category=execution]")).to_have_count(1)
                expect(page.locator(".runtime-transfer[data-category=connection]")).to_have_count(1)
                page.locator(".runtime-ring").nth(1).locator(".core-hit").hover()
                expect(page.locator(".runtime-inspector")).to_contain_text("星图资料检索完成")
                assert page.locator(".ring-turn").evaluate_all(
                    "elements => elements.map(element => getComputedStyle(element).animationPlayState)"
                ) == ["running", "paused", "running"]
                page.screenshot(path=str(args.output / "observatory-runtime-inspector.png"))
                page.mouse.move(100, 75)
                page.get_by_role("button", name="查看运行记录日志", exact=True).click()
                expect(page.locator(".runtime-log-list")).to_contain_text("星图资料检索完成")
                assert "GET /api/observatory" not in page.locator(".runtime-log-list").inner_text()
                page.get_by_role("button", name="关闭状态详情").click()
                page.evaluate(
                    "Object.defineProperty(document, 'hidden', {configurable: true, value: true}); document.dispatchEvent(new Event('visibilitychange'))"
                )
                assert page.locator(".runtime-station").evaluate(
                    "element => element.classList.contains('is-still') && element.classList.contains('is-offline')"
                )
                log_buffer.add("INFO", "Tool.web_search", "隐藏期间完成的历史任务")
                page.wait_for_timeout(300)
                page.evaluate(
                    "Object.defineProperty(document, 'hidden', {configurable: true, value: false}); document.dispatchEvent(new Event('visibilitychange'))"
                )
                expect(page.locator(".runtime-heading small")).to_have_text("● 日志实时连接")
                page.get_by_role("button", name="查看运行记录日志", exact=True).click()
                expect(page.locator(".runtime-log-list")).to_contain_text("隐藏期间完成的历史任务")
                expect(page.locator(".runtime-log-list li").first.locator("small")).to_have_text("历史")
                page.get_by_role("button", name="关闭状态详情").click()
                expect(page.locator(".event-trace")).to_have_count(2)
                # Freeze retains the exact readable list while new SSE records arrive.
                page.get_by_role("button", name="查看运行记录日志", exact=True).click()
                page.get_by_role("button", name="停止跟随", exact=True).click()
                retained_text = page.locator(".runtime-log-list").inner_text()
                log_buffer.add("INFO", "Tool.web_search", "阅读校验：新的查询已完成")
                log_buffer.add("ERROR", "Tool.web_search", "阅读校验：失败的查询保留诊断")
                expect(page.get_by_role("button", name="查看新增 2 条", exact=True)).to_be_visible()
                assert page.locator(".runtime-log-list").inner_text() == retained_text
                page.get_by_role("button", name="查看新增 2 条", exact=True).click()
                expect(page.locator(".runtime-log-list li").first).to_contain_text("失败的查询保留诊断")
                page.get_by_role("searchbox", name="搜索运行日志").fill("阅读校验")
                expect(page.locator(".runtime-log-list li")).to_have_count(2)
                page.get_by_role("combobox", name="日志级别").select_option("error")
                expect(page.locator(".runtime-log-list li")).to_have_count(1)
                expect(page.locator(".runtime-log-list")).to_contain_text("保留诊断")
                page.screenshot(path=str(args.output / "observatory-log-filter.png"))
                page.get_by_role("searchbox", name="搜索运行日志").fill("不存在的内容")
                expect(page.locator(".runtime-log-empty")).to_have_text("没有符合筛选条件的记录。")
                page.get_by_role("searchbox", name="搜索运行日志").fill("")
                page.get_by_role("combobox", name="日志级别").select_option("all")
                for index in range(40):
                    log_buffer.add("INFO", "Tool.web_search", f"连续记录 {index}：用于检查翻阅位置")
                expect(page.get_by_role("button", name="查看新增 40 条", exact=True)).to_be_visible()
                page.get_by_role("button", name="查看新增 40 条", exact=True).click()
                page.locator(".runtime-log-list").evaluate("element => element.scrollTop = 180")
                expect(page.get_by_role("button", name="跟随最新", exact=True)).to_have_attribute("aria-pressed", "false")
                scroll_before = page.locator(".runtime-log-list").evaluate("element => element.scrollTop")
                retained_text = page.locator(".runtime-log-list").inner_text()
                log_buffer.add("INFO", "Tool.web_search", "翻阅期间收到的新记录")
                expect(page.get_by_role("button", name="查看新增 1 条", exact=True)).to_be_visible()
                assert page.locator(".runtime-log-list").evaluate("element => element.scrollTop") == scroll_before
                assert page.locator(".runtime-log-list").inner_text() == retained_text
                page.get_by_role("button", name="关闭状态详情").click()
                page.get_by_role("button", name="状态详情 ＋").click()
                expect(page.locator(".reading-value strong").nth(1)).to_have_text("2,048")
                expect(page.locator(".emotion-reading strong")).to_have_text("喜悦 · 72%")
                page.get_by_role("button", name="关闭状态详情").click()

                def assert_reachable(locator):
                    locator.scroll_into_view_if_needed()
                    assert locator.evaluate("""element => {
                        const r = element.getBoundingClientRect();
                        const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
                        return r.left >= -1 && r.top >= 0 && r.right <= innerWidth + 1
                            && r.bottom <= innerHeight && element.contains(hit);
                    }"""), f"Clipped or covered: {locator}"

                def assert_layout(width, height, composition):
                    page.set_viewport_size({"width": width, "height": height})
                    page.get_by_role(
                        "button", name="完整圆环" if composition == "complete" else "局部特写", exact=True
                    ).click()
                    scene = page.frames[1]
                    scene.wait_for_function(
                        """composition => {
                        const canvas = document.getElementById('stage');
                        const r = canvas.getBoundingClientRect(), g = window.MiyaFlux.geometry;
                        return window.MiyaFlux.state.composition === composition && g
                            && Math.abs(g.width - r.width) < 2 && Math.abs(g.height - r.height) < 2;
                    }""",
                        arg=composition,
                    )
                    scene.wait_for_function("window.MiyaFlux.state.transition === null")
                    if composition == "complete":
                        expect(page.locator(".ring-label").first).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    assert page.locator(".observatory-view").evaluate(
                        "element => element.scrollWidth <= element.clientWidth + 1"
                    )
                    if composition == "complete":
                        expect(page.locator(".ring-label")).to_have_count(6)
                        g = scene.evaluate("window.MiyaFlux.geometry")
                        assert g["x"] - g["outerRadius"] >= 0
                        assert g["x"] + g["outerRadius"] <= g["width"]
                        assert g["y"] - g["outerRadius"] >= 0
                        assert g["y"] + g["outerRadius"] <= g["height"]
                    else:
                        g = scene.evaluate("window.MiyaFlux.geometry")
                        assert g["x"] - g["outerRadius"] < 0
                    if page.locator(".runtime-station").evaluate(
                        "element => getComputedStyle(element).position === 'absolute'"
                    ):
                        panel = page.locator(".presence-panel").bounding_box()
                        station = page.locator(".runtime-station").bounding_box()
                        assert not panel or panel["y"] + panel["height"] <= station["y"] + 2, (
                            f"Note overlaps runtime rings: {width}x{height}/{composition} panel={panel} station={station}"
                        )
                    if width >= 900 and height >= 640:
                        # Do not scroll here: all three satellite rings must be in the first view.
                        expect(page.locator(".runtime-ring")).to_have_count(3)
                        for ring in page.locator(".runtime-ring > .hairline:not(.inner-line)").all():
                            assert ring.evaluate("""element => {
                                const r = element.getBoundingClientRect();
                                const view = document.querySelector('.observatory-view').getBoundingClientRect();
                                return r.width > 60 && r.top >= view.top && r.bottom <= view.bottom
                                    && r.left >= view.left && r.right <= view.right;
                            }"""), f"Satellite ring outside first view: {width}x{height}/{composition}"
                        assert page.locator(".observatory-view").evaluate("element => element.scrollTop === 0")
                    for label in page.locator(".ring-label, .ring-core, .memory-core").all():
                        try:
                            assert_reachable(label)
                        except AssertionError:
                            page.screenshot(path=str(args.output / f"failed-{width}-{height}-{composition}.png"))
                            raise AssertionError(f"Covered ring label at {width} x {height} / {composition}")
                    for selector in (".presence-chat", ".presence-memory", ".details-trigger"):
                        assert_reachable(page.locator(selector))
                    page.locator(".observatory-view").evaluate("element => element.scrollTop = 0")

                for size in (
                    (1920, 1080),
                    (1440, 1000),
                    (1366, 768),
                    (1280, 720),
                    (1024, 640),
                    (900, 700),
                    (768, 1024),
                    (390, 844),
                    (320, 700),
                    (1280, 500),
                ):
                    for composition in ("complete", "closeup"):
                        assert_layout(*size, composition)
                page.locator(".miya-shell").evaluate("element => element.classList.add('is-electron')")
                assert_layout(1280, 720, "complete")
                page.locator(".observatory-footer").scroll_into_view_if_needed()
                assert (
                    page.locator(".observatory-footer").bounding_box()["y"]
                    + page.locator(".observatory-footer").bounding_box()["height"]
                    <= page.locator(".bottom-bar").bounding_box()["y"]
                )
                page.locator(".miya-shell").evaluate("element => element.classList.remove('is-electron')")
                for composition in ("complete", "closeup"):
                    assert_layout(1440, 1000, composition)
                    page.screenshot(path=str(args.output / f"observatory-{composition}.png"), animations="disabled")
                assert_layout(1280, 720, "complete")
                page.screenshot(path=str(args.output / "observatory-compact.png"), animations="disabled")
                page.get_by_role("button", name="弥娅的短笺 ↗").click()
                expect(page.get_by_role("dialog", name="弥娅的短笺")).to_contain_text("把今天的微光")
                page.get_by_role("button", name="关闭短笺").click()
                assert_layout(1280, 720, "closeup")
                page.screenshot(path=str(args.output / "observatory-compact-closeup.png"), animations="disabled")
                assert_layout(1280, 720, "complete")

                state.update({"memory": 2049, "phase": "RUNNING", "messages": 9})
                service._cached = None
                expect(page.locator(".phase-label")).to_contain_text("运行中", timeout=8000)
                scene = page.frames[1]
                scene.wait_for_function("window.MiyaFlux.state.memoryCount === 2049")
                page.get_by_role("button", name="静谧", exact=True).click()
                scene.wait_for_function("window.MiyaFlux.state.mode === 'quiet'")
                page.get_by_role("button", name="局部特写", exact=True).click()
                scene.wait_for_function("window.MiyaFlux.state.cameraTime > 0.5")
                first_camera = scene.evaluate("window.MiyaFlux.screenGeometry.radius")
                scene.wait_for_function("radius => window.MiyaFlux.screenGeometry.radius > radius", arg=first_camera)
                page.screenshot(path=str(args.output / "observatory-closeup-camera.png"), animations="disabled")
                page.get_by_role("button", name="暂停共鸣动画").click()
                scene.wait_for_function("window.MiyaFlux.paused === true")
                paused_time = scene.evaluate("window.MiyaFlux.state.cameraTime")
                page.wait_for_timeout(250)
                assert scene.evaluate("window.MiyaFlux.state.cameraTime") == paused_time
                page.get_by_role("button", name="局部特写", exact=True).click()
                scene.wait_for_function("window.MiyaFlux.state.composition === 'closeup'")
                page.reload()
                expect(page.get_by_role("button", name="局部特写", exact=True)).to_have_attribute(
                    "aria-pressed", "true"
                )
                expect(page.get_by_role("button", name="静谧", exact=True)).to_have_attribute("aria-pressed", "true")
                scene = page.frames[1]
                scene.wait_for_function(
                    "window.MiyaFlux.paused === true && window.MiyaFlux.state.composition === 'closeup'"
                )
                expect(page.locator(".runtime-station")).to_have_class(re.compile("is-still"))
                page.get_by_role("button", name="继续共鸣动画").click()
                page.get_by_role("button", name="沉浸观测").click()
                expect(page.locator(".presence-panel")).to_be_hidden()
                page.get_by_role("button", name="退出沉浸").click()
                assert_layout(1440, 1000, "complete")
                label = page.locator(".ring-label").first
                label.click()
                expect(page.get_by_role("dialog", name="对话记忆")).to_be_visible()
                expect(page.locator(".selected-memory strong")).to_have_text("1,000")
                scene.wait_for_function("window.MiyaFlux.state.selectedLayer === 'dialogue'")
                page.keyboard.press("Escape")
                expect(page.locator("dialog[aria-labelledby=observatory-details-title]")).not_to_be_visible()
                scene.wait_for_function("window.MiyaFlux.state.selectedLayer === null")

                for composition in ("complete", "closeup"):
                    assert_layout(390, 844, composition)
                    page.screenshot(
                        path=str(args.output / f"observatory-mobile-{composition}.png"), animations="disabled"
                    )
                page.locator(".runtime-station").screenshot(
                    path=str(args.output / "observatory-mobile-runtime.png"), animations="disabled"
                )
                page.get_by_role("button", name="头像设置", exact=True).click()
                editor = page.get_by_role("dialog", name="自定义弥娅头像")
                expect(editor).to_be_visible()
                assert_reachable(editor.get_by_role("slider", name="头像数据流强度"))
                page.get_by_role("button", name="关闭头像设置").click()
                page.get_by_role("button", name="状态详情 ＋").click()
                assert_reachable(page.locator(".refresh-reading"))
                page.screenshot(path=str(args.output / "observatory-mobile-details.png"), animations="disabled")
                page.get_by_role("button", name="关闭状态详情").click()

                original_note = service.store.read()
                service.store.write(
                    {
                        **original_note,
                        "id": "long-note",
                        "title": "愿所有温柔的星光都在漫长的夜晚为你安静守候",
                        "body": "让今天的微光陪你慢慢走。" * 8,
                    }
                )
                state.update({"memory": 1234567890, "large_counts": True})
                service._cached = None
                expect(page.locator(".presence-note h2")).to_have_text(
                    "愿所有温柔的星光都在漫长的夜晚为你安静守候", timeout=8000
                )
                for composition in ("complete", "closeup"):
                    assert_layout(1280, 720, composition)
                    assert_layout(390, 844, composition)
                page.get_by_role("button", name="展开短笺 ↓").click()
                expect(page.locator(".presence-panel")).to_have_class("presence-panel note-expanded")
                service.store.write(original_note)
                state.update({"memory": 2049, "large_counts": False})
                service._cached = None
                expect(page.locator(".presence-note h2")).to_have_text(original_note["title"], timeout=8000)
                assert_layout(1440, 1000, "complete")
                state["connected"] = False
                expect(page.locator(".connection-summary")).to_contain_text("等待重新连接", timeout=35000)
                expect(page.locator(".ring-label .layer-value").first).to_have_text("—")
                expect(page.locator(".presence-note h2")).to_have_text(original_note["title"])
                page.screenshot(path=str(args.output / "observatory-disconnected.png"), animations="disabled")
                state["connected"] = True
                service._cached = None
                expect(page.locator(".connection-summary")).to_contain_text("实时同步", timeout=8000)
                page.get_by_role("button", name="查看记忆日志", exact=True).click()
                expect(page.locator(".runtime-log-list")).to_contain_text("六层记忆索引已就绪")
                page.screenshot(path=str(args.output / "observatory-runtime-details.png"), animations="disabled")
                page.get_by_role("button", name="关闭状态详情").click()
                page.get_by_role("button", name="返回首页").click()
                expect(page.locator(".cmd-mascot-val")).to_have_text("2049")
                expect(page.locator(".cmd-level-label")).to_contain_text("运行中")
                assert errors == [], errors
                browser.close()
                print(
                    json.dumps(
                        {
                            "result": "passed",
                            "checks": [
                                "live SSE",
                                "classified runtime logs and access-noise filtering",
                                "history versus live activity",
                                "category-specific transfers and warning colors",
                                "individual hover pause and readable preview",
                                "log search, severity filters and retained reading position",
                                "smooth composition transitions",
                                "hidden-page disconnect and resume",
                                "two compositions at ten viewport sizes",
                                "all satellite rings visible without scrolling at laptop sizes",
                                "ring geometry and accessible labels",
                                "desktop title bar clearance",
                                "independent persisted composition/motion",
                                "layer selection and keyboard dismissal",
                                "portrait settings",
                                "mobile details",
                                "long notes and large counters",
                                "disconnect/reconnect",
                                "home consistency",
                                "no browser exceptions",
                            ],
                            "output": str(args.output),
                        },
                        ensure_ascii=False,
                    )
                )
        finally:
            server.should_exit = True
            thread.join(timeout=5)


if __name__ == "__main__":
    main()

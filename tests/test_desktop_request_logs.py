"""Regression checks for desktop / backend console access-log separation."""

import asyncio
import io
import logging
import socket

import pytest
from uvicorn.logging import AccessFormatter

from core import log_stream
from core.desktop_request_logs import DesktopRequestLogMiddleware


@pytest.fixture
def logs(monkeypatch):
    buffer = log_stream.LogStreamBuffer()
    monkeypatch.setattr(log_stream, "_buffer", buffer)
    output = io.StringIO()
    logger = logging.getLogger("uvicorn.access")
    old = logger.handlers[:], logger.filters[:], logger.level, logger.propagate
    other_filters = {name: logging.getLogger(name).filters[:] for name in ("uvicorn.error", "Miya.ManagementAPI")}
    handler = logging.StreamHandler(output)
    # Real Uvicorn formatter requires the original five record arguments.
    handler.setFormatter(AccessFormatter('%(request_line)s %(status_code)s', use_colors=False))
    logger.handlers = [handler]
    logger.filters = []
    logger.setLevel(logging.INFO)
    logger.propagate = False
    yield logger, output, buffer
    logger.handlers, logger.filters, logger.level, logger.propagate = old
    for name, filters in other_filters.items():
        logging.getLogger(name).filters = filters


async def run_request(logger, *, desktop=False, host="127.0.0.1", fail=False, yield_once=False, status=200):
    scope = {
        "type": "http", "method": "GET", "path": "/api/status",
        "client": (host, 50000),
        "headers": [(b"x-miya-client", b"desktop")] if desktop else [],
    }

    async def app(scope, receive, send):
        if yield_once:
            await asyncio.sleep(0)
        if fail:
            raise ValueError("backend failed")
        await send({"type": "http.response.start", "status": status})

    async def send(message):
        logger.info('%s - "%s %s HTTP/%s" %d', host, "GET", "/api/status", "1.1", message["status"])

    await DesktopRequestLogMiddleware(app)(scope, None, send)


def test_desktop_access_only_goes_to_shared_buffer(logs):
    logger, output, buffer = logs
    asyncio.run(run_request(logger, desktop=True))
    assert output.getvalue() == ""
    entries, _ = buffer.snapshot()
    assert len(entries) == 1
    assert entries[0]["name"] == "Miya.DesktopFrontend"
    assert entries[0]["source"] == "frontend"
    assert 'GET /api/status HTTP/1.1' in entries[0]["text"]


@pytest.mark.parametrize("status,level", [(200, "INFO"), (404, "WARNING"), (500, "ERROR")])
def test_frontend_request_status_keeps_severity(logs, status, level):
    logger, output, buffer = logs
    asyncio.run(run_request(logger, desktop=True, status=status))
    assert output.getvalue() == ""
    entry = buffer.snapshot()[0][0]
    assert entry["source"] == "frontend"
    assert entry["level"] == level


@pytest.mark.parametrize("desktop,host", [(False, "127.0.0.1"), (True, "192.0.2.1")])
def test_other_clients_keep_original_access_output(logs, desktop, host):
    logger, output, buffer = logs
    asyncio.run(run_request(logger, desktop=desktop, host=host))
    assert "GET /api/status HTTP/1.1 200 OK" in output.getvalue()
    assert buffer.snapshot()[0] == []


def test_concurrent_requests_do_not_share_desktop_marker(logs):
    logger, output, buffer = logs

    async def run():
        await asyncio.gather(
            run_request(logger, desktop=True, yield_once=True),
            run_request(logger, yield_once=True),
        )

    asyncio.run(run())
    assert output.getvalue().count("GET /api/status") == 1
    assert len(buffer.snapshot()[0]) == 1


def test_marker_resets_after_exception(logs):
    logger, output, _ = logs

    async def run():
        with pytest.raises(ValueError, match="backend failed"):
            await run_request(logger, desktop=True, fail=True)
        logger.info('%s - "%s %s HTTP/%s" %d', "127.0.0.1", "GET", "/health", "1.1", 200)

    asyncio.run(run())
    assert "GET /health" in output.getvalue()


def test_capture_failure_keeps_original_record(logs, monkeypatch):
    logger, output, _ = logs

    def broken_capture(text, **kwargs):
        raise RuntimeError("capture unavailable")

    monkeypatch.setattr("core.desktop_request_logs.log_desktop_request", broken_capture)
    asyncio.run(run_request(logger, desktop=True))
    assert "GET /api/status" in output.getvalue()


def test_business_errors_and_websocket_connections(logs):
    _, _, buffer = logs
    logger = logging.getLogger("Miya.ManagementAPI")
    old_level, old_handlers, old_propagate = logger.level, logger.handlers[:], logger.propagate
    output = io.StringIO()
    logger.handlers = [logging.StreamHandler(output)]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    async def app(scope, receive, send):
        logger.info("WS 客户端连接 type=desktop")
        logger.info("AI response completed")
        logger.warning("camera unavailable")
        logger.error("backend failed")

    try:
        asyncio.run(DesktopRequestLogMiddleware(app)({
            "type": "websocket", "client": ("::1", 50000),
            "headers": [(b"x-miya-client", b"desktop")],
        }, None, None))
        assert "WS 客户端连接" not in output.getvalue()
        assert "AI response completed" in output.getvalue()
        assert "camera unavailable" in output.getvalue()
        assert "backend failed" in output.getvalue()
        assert "WS 客户端连接" in buffer.snapshot()[0][0]["text"]
    finally:
        logger.setLevel(old_level)
        logger.handlers, logger.propagate = old_handlers, old_propagate


@pytest.mark.parametrize("ws_protocol", ["websockets", "websockets-sansio"])
def test_real_uvicorn_cors_and_streaming(logs, ws_protocol):
    import httpx
    import uvicorn
    from fastapi import FastAPI, WebSocket
    from fastapi.middleware.cors import CORSMiddleware
    from starlette.responses import StreamingResponse
    from websockets.asyncio.client import connect

    _, output, buffer = logs
    ws_output = io.StringIO()
    ws_logger = logging.getLogger("uvicorn.error")
    old_ws_logger = ws_logger.handlers[:], ws_logger.level, ws_logger.propagate
    ws_logger.handlers = [logging.StreamHandler(ws_output)]
    ws_logger.setLevel(logging.INFO)
    ws_logger.propagate = False

    async def run():
        app = FastAPI()
        stream_finished = asyncio.Event()
        app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
        app.add_middleware(DesktopRequestLogMiddleware)

        @app.get("/api/status")
        async def status():
            return {"status": "ok"}

        @app.get("/api/stream")
        async def stream():
            async def data():
                yield "data: ready\n\n"
                await stream_finished.wait()

            return StreamingResponse(data(), media_type="text/event-stream")

        @app.websocket("/api/ws")
        async def websocket(ws: WebSocket):
            await ws.accept()
            await ws.receive_text()
            await ws.send_text("ok")
            await ws.close()

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_config=None, lifespan="off", access_log=True, ws=ws_protocol))
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            async with asyncio.timeout(5):
                while not server.started:
                    await asyncio.sleep(0.01)
                async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
                    responses = await asyncio.gather(
                        client.get("/api/status", headers={"x-miya-client": "desktop"}),
                        client.get("/api/status"),
                    )
                    assert all(response.status_code == 200 for response in responses)
                    preflight = await client.options("/api/status", headers={
                        "origin": "http://localhost:5173", "access-control-request-method": "GET",
                        "access-control-request-headers": "x-miya-client", "x-miya-client": "desktop",
                    })
                    assert preflight.status_code == 200
                    async with client.stream("GET", "/api/stream", headers={"x-miya-client": "desktop"}) as response:
                        assert response.status_code == 200
                        assert await anext(response.aiter_lines()) == "data: ready"
                        assert any("GET /api/stream" in e["text"] for e in buffer.snapshot()[0])
                    stream_finished.set()
                for headers in ({"x-miya-client": "desktop"}, {}):
                    async with connect(f"ws://127.0.0.1:{port}/api/ws", additional_headers=headers) as ws:
                        await ws.send("hello")
                        assert await ws.recv() == "ok"
            assert output.getvalue().count("GET /api/status") == 1
            assert "OPTIONS" not in output.getvalue()
            assert "GET /api/stream" not in output.getvalue()
        finally:
            stream_finished.set()
            server.should_exit = True
            await asyncio.wait_for(task, timeout=5)
            listener.close()
        assert ws_output.getvalue().count("connection open") == 1
        # The legacy protocol logs close; SansIO emits acceptance/open only.
        closes = 1 if ws_protocol == "websockets" else 0
        assert ws_output.getvalue().count("connection closed") == closes
        assert ws_output.getvalue().count("[accepted]") == 1
        assert len(buffer.snapshot()[0]) == 5 + closes

    try:
        asyncio.run(run())
    finally:
        ws_logger.handlers, old_level, ws_logger.propagate = old_ws_logger
        ws_logger.setLevel(old_level)

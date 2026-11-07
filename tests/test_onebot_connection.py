"""Regression tests for the OneBot WebSocket lifecycle."""

import asyncio
import os
import socket
import unittest
from unittest.mock import patch

from aiohttp import web


class OneBotConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_reconnect_cancels_previous_history_recovery(self):
        from core.unified_platform_impl.onebot_platform import OneBotPlatform

        first_close = asyncio.Event()
        started = [asyncio.Event(), asyncio.Event()]
        cancelled = [asyncio.Event(), asyncio.Event()]
        recovery_tasks = []
        connections = []

        async def websocket_handler(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            connections.append(ws)
            if len(connections) == 1:
                await first_close.wait()
                await ws.close()
            else:
                async for _ in ws:
                    pass
            return ws

        async def recover():
            index = len(recovery_tasks)
            recovery_tasks.append(asyncio.current_task())
            if index == 1:
                self.assertTrue(cancelled[0].is_set())
            started[index].set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled[index].set()

        app = web.Application()
        app.router.add_get("/", websocket_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        platform = OneBotPlatform()
        platform._ws_url = f"ws://127.0.0.1:{port}/"
        platform._recover_recent_group_history_with_retry = recover
        try:
            self.assertTrue(await platform._do_connect())
            await asyncio.wait_for(started[0].wait(), timeout=2)
            first_close.set()
            await asyncio.wait_for(started[1].wait(), timeout=5)
            self.assertTrue(recovery_tasks[0].cancelled())
        finally:
            first_close.set()
            await platform._do_disconnect()
            await platform._cancel_tasks()
            await runner.cleanup()
        self.assertTrue(recovery_tasks[1].cancelled())
        self.assertIsNone(platform._history_recovery_task)

    async def test_waits_for_napcat_start_and_sends_access_token(self):
        from core.unified_platform_impl.onebot_platform import OneBotPlatform

        connected = asyncio.Event()
        received_auth = []

        async def websocket_handler(request):
            received_auth.append(request.headers.get("Authorization"))
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            connected.set()
            async for _ in ws:
                pass
            return ws

        app = web.Application()
        app.router.add_get("/", websocket_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        site = web.TCPSite(runner, "127.0.0.1", port)

        with patch.dict(os.environ, {"QQ_ONEBOT_TOKEN": "test-token"}):
            platform = OneBotPlatform()
            platform._ws_url = f"ws://127.0.0.1:{port}/"
            try:
                connect_task = asyncio.create_task(platform._do_connect())
                await asyncio.sleep(1.1)  # Let the first refused attempt back off.
                self.assertFalse(connect_task.done(), connect_task.result() if connect_task.done() else "")
                await site.start()

                self.assertTrue(await asyncio.wait_for(connect_task, timeout=5))
                await asyncio.wait_for(connected.wait(), timeout=1)
                self.assertEqual(received_auth, ["Bearer test-token"])
                self.assertTrue(platform._connected)
            finally:
                await platform._do_disconnect()
                await platform._cancel_tasks()
                await runner.cleanup()


if __name__ == "__main__":
    unittest.main()

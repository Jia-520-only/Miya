"""Regression tests for the OneBot WebSocket lifecycle."""

import asyncio
import os
import socket
import unittest
from unittest.mock import patch

from aiohttp import web


class OneBotConnectionTests(unittest.IsolatedAsyncioTestCase):
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

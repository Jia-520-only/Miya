import asyncio
import json

import pytest
import websockets

from mcpserver.vam_bridge.service import VAMBridgeService


class FakeWebSocket:
    def __init__(self):
        self.sent = []
        self.incoming = asyncio.Queue()
        self.closed = False

    async def send(self, payload):
        message = json.loads(payload)
        self.sent.append(message)
        await self.incoming.put(
            json.dumps(
                {
                    "id": message["id"],
                    "type": "response",
                    "ok": True,
                    "data": {"action": message["action"]},
                }
            )
        )

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.closed:
            raise StopAsyncIteration
        return await self.incoming.get()

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_vam_action_uses_request_response_protocol():
    service = VAMBridgeService()
    fake = FakeWebSocket()
    service._ws = fake
    service._listen_task = asyncio.create_task(service._listen_loop(fake))

    result = json.loads(
        await service.handle_handoff(
            {
                "tool_name": "vam_set_expression",
                "atom": "Person",
                "expression": "happy",
                "duration": 0.5,
            }
        )
    )

    assert result["ok"] is True
    assert fake.sent[-1]["action"] == "set_expression"
    assert fake.sent[-1]["params"] == {"atom": "Person", "expression": "happy", "duration": 0.5}
    await service._disconnect()


@pytest.mark.asyncio
async def test_vam_rejects_non_local_override():
    service = VAMBridgeService()
    result = json.loads(await service.handle_handoff({"tool_name": "vam_connect", "url": "ws://192.168.1.4:8765"}))
    assert result["ok"] is False
    assert "127.0.0.1" in result["error"]
    result = json.loads(await service.handle_handoff({"tool_name": "vam_connect", "url": "ws://127.0.0.1.evil:8765"}))
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_vam_validates_action_arguments_without_connecting():
    service = VAMBridgeService()
    result = json.loads(await service.handle_handoff({"tool_name": "vam_set_expression", "atom": "Person"}))
    assert result["ok"] is False
    assert "expression" in result["error"]
    assert "morphs" in result["error"]


@pytest.mark.asyncio
async def test_vam_real_websocket_round_trip():
    async def fake_vam(websocket):
        async for raw in websocket:
            message = json.loads(raw)
            await websocket.send(
                json.dumps(
                    {
                        "id": message["id"],
                        "type": "response",
                        "ok": True,
                        "data": {"action": message["action"]},
                    }
                )
            )

    server = await websockets.serve(fake_vam, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    service = VAMBridgeService()
    try:
        result = json.loads(
            await service.handle_handoff(
                {"tool_name": "vam_connect", "url": f"ws://127.0.0.1:{port}/miya-vam"}
            )
        )
        assert result["ok"] is True
        result = json.loads(
            await service.handle_handoff(
                {"tool_name": "vam_look_at", "atom": "Person", "target": "camera"}
            )
        )
        assert result == {"ok": True, "action": "look_at", "data": {"action": "look_at"}}
    finally:
        await service._disconnect()
        server.close()
        await server.wait_closed()

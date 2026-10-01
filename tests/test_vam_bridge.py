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


class AutonomyWebSocket(FakeWebSocket):
    def __init__(self, *, active=False, scene_state=None):
        super().__init__()
        self.active = active
        self.scene_state = scene_state

    async def send(self, payload):
        message = json.loads(payload)
        self.sent.append(message)
        action = message["action"]
        if action == "list_atoms":
            data = [{"uid": "Person", "type": "Person", "allowed": True}]
        elif action == "get_status":
            data = {"activity": {"active": self.active}}
            if self.scene_state is not None:
                data["sceneState"] = self.scene_state
        elif action == "run_sequence":
            data = {"sequenceId": "auto-sequence"}
        else:
            data = {"action": action}
        await self.incoming.put(
            json.dumps({"id": message["id"], "type": "response", "ok": True, "data": data})
        )


@pytest.mark.asyncio
async def test_vam_autonomy_parses_simplejson_boolean_strings():
    service = VAMBridgeService()
    fake = AutonomyWebSocket()
    service._ws = fake
    service._listen_task = asyncio.create_task(service._listen_loop(fake))

    result = json.loads(
        await service.handle_handoff(
            {"tool_name": "vam_autonomy_start", "atom": "Person", "interval": 15}
        )
    )

    assert result["ok"] is True
    assert result["autonomy"]["last_decision"] == "sequence_started"
    assert any(message["action"] == "run_sequence" for message in fake.sent)
    await service.handle_handoff({"tool_name": "vam_autonomy_stop"})
    await service._disconnect()


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
async def test_vam_person_controls_use_discovery_and_typed_requests():
    service = VAMBridgeService()
    fake = FakeWebSocket()
    service._ws = fake
    service._listen_task = asyncio.create_task(service._listen_loop(fake))

    before_inspect = len(fake.sent)
    result = json.loads(
        await service.handle_handoff(
            {"tool_name": "vam_inspect_person", "atom": "Person", "storable": "headControl"}
        )
    )
    assert result["ok"] is False
    assert "堆耗尽" in result["error"]
    assert len(fake.sent) == before_inspect

    result = json.loads(
        await service.handle_handoff(
            {"tool_name": "vam_get_person_state", "atom": "Person", "storable": "plugin"}
        )
    )
    assert result["ok"] is True
    assert fake.sent[-1]["action"] == "get_person_state"
    assert fake.sent[-1]["params"] == {"atom": "Person", "storable": "plugin"}

    result = json.loads(
        await service.handle_handoff({"tool_name": "vam_get_person_state", "atom": "Person"})
    )
    assert result["ok"] is False
    assert "storable" in result["error"]

    result = json.loads(
        await service.handle_handoff(
            {
                "tool_name": "vam_set_person_params",
                "atom": "Person",
                "storable": "headControl",
                "values": {"positionState": "Hold", "xPosition": 0.1},
            }
        )
    )
    assert result["ok"] is True
    assert fake.sent[-1]["action"] == "set_person_params"
    assert fake.sent[-1]["params"]["values"] == {"positionState": "Hold", "xPosition": 0.1}

    result = json.loads(
        await service.handle_handoff(
            {
                "tool_name": "vam_call_person_action",
                "atom": "Person",
                "storable": "headControl",
                "action": "reset",
            }
        )
    )
    assert result["ok"] is True
    assert fake.sent[-1]["action"] == "call_person_action"
    assert fake.sent[-1]["params"]["action"] == "reset"
    await service._disconnect()


@pytest.mark.asyncio
async def test_vam_person_param_batch_is_bounded_before_network_call():
    service = VAMBridgeService()
    result = json.loads(
        await service.handle_handoff(
            {
                "tool_name": "vam_set_person_params",
                "atom": "Person",
                "storable": "headControl",
                "values": {f"param_{index}": index for index in range(33)},
            }
        )
    )
    assert result["ok"] is False
    assert "32" in result["error"]


@pytest.mark.asyncio
async def test_vam_run_sequence_normalizes_timing_and_actions():
    service = VAMBridgeService()
    fake = FakeWebSocket()
    service._ws = fake
    service._listen_task = asyncio.create_task(service._listen_loop(fake))

    result = json.loads(
        await service.handle_handoff(
            {
                "tool_name": "vam_run_sequence",
                "atom": "Person",
                "loop": True,
                "steps": [
                    {"action": "set_expression", "expression": "happy", "duration": 0.8, "wait": 1.2},
                    {"action": "call_person_action", "storable": "plugin", "actionName": "start"},
                ],
            }
        )
    )

    assert result["ok"] is True
    assert fake.sent[-1]["action"] == "run_sequence"
    sequence = fake.sent[-1]["params"]
    assert sequence["atom"] == "Person"
    assert sequence["loop"] is True
    assert sequence["gap"] == 0.5
    assert sequence["steps"][0]["duration"] == 0.8
    assert sequence["steps"][0]["wait"] == 1.2
    assert sequence["steps"][1]["actionName"] == "start"
    await service._disconnect()


@pytest.mark.asyncio
async def test_vam_run_sequence_rejects_unsafe_actions_and_too_many_steps():
    service = VAMBridgeService()
    result = json.loads(
        await service.handle_handoff(
            {"tool_name": "vam_run_sequence", "atom": "Person", "steps": [{"action": "execute_code"}]}
        )
    )
    assert result["ok"] is False
    assert "不允许" in result["error"]

    result = json.loads(
        await service.handle_handoff(
            {"tool_name": "vam_run_sequence", "atom": "Person", "steps": [{"action": "look_at", "target": "user"}] * 33}
        )
    )
    assert result["ok"] is False
    assert "32" in result["error"]


@pytest.mark.asyncio
async def test_vam_move_person_is_bounded_and_added_to_sequences():
    service = VAMBridgeService()
    fake = FakeWebSocket()
    service._ws = fake
    service._listen_task = asyncio.create_task(service._listen_loop(fake))

    result = json.loads(
        await service.handle_handoff(
            {
                "tool_name": "vam_run_sequence",
                "atom": "Person",
                "steps": [
                    {"action": "move_person", "offset": {"x": 0.08, "y": 0, "z": -0.04}, "duration": 0.8}
                ],
            }
        )
    )
    assert result["ok"] is True
    assert fake.sent[-1]["params"]["steps"][0] == {
        "action": "move_person",
        "offset": {"x": 0.08, "y": 0.0, "z": -0.04},
        "duration": 0.8,
        "wait": 0.8,
    }
    await service._disconnect()

    service = VAMBridgeService()
    result = json.loads(
        await service.handle_handoff(
            {"tool_name": "vam_move_person", "atom": "Person", "offset": {"x": 0.26, "y": 0, "z": 0}}
        )
    )
    assert result["ok"] is False
    assert "0.25" in result["error"]


@pytest.mark.asyncio
async def test_vam_autonomy_starts_only_when_scene_is_idle_and_can_stop():
    service = VAMBridgeService()
    fake = AutonomyWebSocket()
    service._ws = fake
    service._listen_task = asyncio.create_task(service._listen_loop(fake))

    result = json.loads(
        await service.handle_handoff(
            {"tool_name": "vam_autonomy_start", "atom": "Person", "interval": 15, "mode": "responsive"}
        )
    )
    assert result["ok"] is True
    assert result["autonomy"]["enabled"] is True
    await asyncio.sleep(0.01)
    assert any(message["action"] == "get_status" for message in fake.sent)
    sequence = next(message for message in fake.sent if message["action"] == "run_sequence")
    assert sequence["params"]["atom"] == "Person"
    assert sequence["params"]["steps"][0]["target"] == "user"

    result = json.loads(await service.handle_handoff({"tool_name": "vam_autonomy_status"}))
    assert result["ok"] is True
    assert result["autonomy"]["task_alive"] is True

    result = json.loads(await service.handle_handoff({"tool_name": "vam_autonomy_stop"}))
    assert result["ok"] is True
    assert result["autonomy"]["enabled"] is False
    await service._disconnect()


@pytest.mark.asyncio
async def test_vam_autonomy_waits_while_scene_is_active():
    service = VAMBridgeService()
    fake = AutonomyWebSocket(active=True)
    service._ws = fake
    service._listen_task = asyncio.create_task(service._listen_loop(fake))

    result = json.loads(
        await service.handle_handoff(
            {"tool_name": "vam_autonomy_start", "atom": "Person", "interval": 15}
        )
    )

    assert result["ok"] is True
    assert result["autonomy"]["last_decision"] == "wait:scene_active"
    assert not any(message["action"] == "run_sequence" for message in fake.sent)
    await service.handle_handoff({"tool_name": "vam_autonomy_stop"})
    await service._disconnect()


@pytest.mark.asyncio
async def test_vam_autonomy_selects_strategy_from_user_context():
    service = VAMBridgeService()
    fake = AutonomyWebSocket(
        scene_state={
            "persons": [
                {"uid": "Person", "userDistance": 0.9, "userGazeAngle": 18.0, "userInView": True}
            ]
        }
    )
    service._ws = fake
    service._listen_task = asyncio.create_task(service._listen_loop(fake))

    result = json.loads(
        await service.handle_handoff(
            {"tool_name": "vam_autonomy_start", "atom": "Person", "interval": 15, "mode": "responsive"}
        )
    )

    assert result["ok"] is True
    assert result["autonomy"]["last_context"] == "close_engaged"
    assert result["autonomy"]["last_strategy"] == "welcome_close"
    assert result["autonomy"]["user_distance"] == 0.9
    sequence = next(message for message in fake.sent if message["action"] == "run_sequence")
    assert sequence["params"]["steps"][0] == {"action": "look_at", "target": "user", "wait": 0.5}
    await service.handle_handoff({"tool_name": "vam_autonomy_stop"})
    await service._disconnect()


@pytest.mark.asyncio
async def test_vam_manual_sequence_pauses_autonomy():
    service = VAMBridgeService()
    fake = AutonomyWebSocket()
    service._ws = fake
    service._listen_task = asyncio.create_task(service._listen_loop(fake))
    await service.handle_handoff({"tool_name": "vam_autonomy_start", "atom": "Person"})
    result = json.loads(
        await service.handle_handoff(
            {
                "tool_name": "vam_run_sequence",
                "atom": "Person",
                "steps": [{"action": "look_at", "target": "camera"}],
            }
        )
    )
    assert result["ok"] is True
    status = json.loads(await service.handle_handoff({"tool_name": "vam_autonomy_status"}))
    assert status["autonomy"]["enabled"] is False
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

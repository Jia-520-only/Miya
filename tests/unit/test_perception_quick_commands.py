import pytest

from hub.services.context import ProcessRequest, ProcessState
from hub.services.perception import PerceptionService


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["~状态", "~认知"])
async def test_quick_status_commands_return_without_unpacking_error(command):
    state = await PerceptionService()._check_quick_commands(
        ProcessRequest(content=command, raw_perception={}),
        ProcessState(),
    )

    assert state.is_quick_command is True
    assert state.quick_response

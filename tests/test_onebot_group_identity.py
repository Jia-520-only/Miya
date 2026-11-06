import asyncio

from core.unified_platform_impl.onebot_platform import OneBotPlatform


def _pending_message(user_id, user_name, content, message_id):
    return {
        "data": {"message_type": "group", "group_id": 2001, "message_id": message_id},
        "content": content,
        "user_id": user_id,
        "user_name": user_name,
        "group_id": "2001",
        "group_name": "test group",
        "sender_role": "member",
        "is_at_bot": True,
        "extra": {"message_id": message_id},
    }


def _group_event(user_id, text, message_id, *at_ids):
    segments = [{"type": "at", "data": {"qq": target}} for target in at_ids]
    segments.append({"type": "text", "data": {"text": text}})
    return {
        "post_type": "message",
        "message_type": "group",
        "group_id": 2001,
        "message_id": message_id,
        "sender": {"user_id": user_id, "card": f"member-{user_id}"},
        "message": segments,
    }


def test_group_burst_coalesces_only_adjacent_messages_from_same_sender():
    alice_first = _group_event("1001", "弥娅", 11, "999")
    alice_second = _group_event("1001", "在吗", 12, "999")
    bob = _group_event("1002", "帮忙看看", 13, "999")

    batches = OneBotPlatform._coalesce_group_events([alice_first, alice_second, bob])

    assert [[event["message_id"] for event in batch] for batch in batches] == [[11, 12], [13]]
    merged = OneBotPlatform._merge_group_events(batches[0])
    assert merged["sender"]["user_id"] == "1001"
    assert merged["batch_message_ids"] == ["11", "12"]
    assert merged["batch_count"] == 2
    assert {segment["data"]["qq"] for segment in merged["message"] if segment["type"] == "at"} == {"999"}
    merged_text = "".join(
        segment["data"]["text"] for segment in merged["message"] if segment["type"] == "text"
    )
    assert "弥娅" in merged_text and "在吗" in merged_text


def test_group_burst_keeps_commands_and_media_as_separate_events():
    command = _group_event("1001", "/help", 21, "999")
    image = _group_event("1001", "看这个", 22, "999")
    image["message"].insert(0, {"type": "image", "data": {"file": "img"}})

    batches = OneBotPlatform._coalesce_group_events([command, image])

    assert [[event["message_id"] for event in batch] for batch in batches] == [[21], [22]]


def test_group_worker_dispatches_one_identity_safe_burst():
    async def run():
        platform = OneBotPlatform.__new__(OneBotPlatform)
        platform.platform_id = "aiocqhttp"
        platform._event_tasks = set()
        platform._group_event_queues = {}
        platform._group_event_workers = {}
        platform._group_worker_queue_size = lambda: 10
        platform._max_event_tasks = lambda: 100
        platform._group_burst_window = lambda: 0.02
        platform._group_batch_max = lambda: 15
        platform._group_batching_enabled = lambda: True
        handled = []
        handled_event = asyncio.Event()

        async def handle(event):
            handled.append(event)
            handled_event.set()

        platform._handle_onebot_message = handle
        platform._enqueue_group_event(_group_event("1001", "第一句", 31, "999"))
        platform._enqueue_group_event(_group_event("1001", "第二句", 32, "999"))
        await asyncio.wait_for(handled_event.wait(), timeout=1)

        assert len(handled) == 1
        assert handled[0]["sender"]["user_id"] == "1001"
        assert handled[0]["batch_message_ids"] == ["31", "32"]
        assert "第一句" in handled[0]["message"][-1]["data"]["text"]
        assert "第二句" in handled[0]["message"][-1]["data"]["text"]

        worker = platform._group_event_workers["2001"]
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    asyncio.run(run())


def test_group_pending_messages_keep_each_sender_identity():
    async def run():
        platform = OneBotPlatform.__new__(OneBotPlatform)
        platform.platform_id = "aiocqhttp"
        platform._pending_group_messages = {
            "2001": [
                _pending_message("1001", "Alice", "first message", 11),
                _pending_message("1002", "Bob", "second message", 12),
            ]
        }
        routed = []
        replies = []

        async def route(**kwargs):
            routed.append(kwargs)
            return f"reply for {kwargs['user_id']}"

        async def send_reply(data, text):
            replies.append((data["message_id"], text))

        platform.route_to_decision_hub = route
        platform._send_onebot_reply = send_reply

        await platform._flush_group_pending("2001", asyncio.Lock())

        assert [(item["user_id"], item["user_name"], item["content"]) for item in routed] == [
            ("1001", "Alice", "first message"),
            ("1002", "Bob", "second message"),
        ]
        assert [item["extra"] for item in routed] == [{"message_id": 11}, {"message_id": 12}]
        assert replies == [(11, "reply for 1001"), (12, "reply for 1002")]
        assert "2001" not in platform._pending_group_messages

    asyncio.run(run())


def test_group_buffer_overflow_waits_instead_of_dropping_message():
    async def run():
        platform = OneBotPlatform.__new__(OneBotPlatform)
        platform.platform_id = "aiocqhttp"
        platform.config = {}
        platform._pending_group_messages = {
            "2001": [_pending_message("1001", "Alice", "queued", 11)]
        }
        platform._group_batching_enabled = lambda: True
        platform._group_batch_max = lambda: 1
        platform.route_to_decision_hub = lambda **kwargs: asyncio.sleep(0, result="reply")
        replies = []

        async def send_reply(data, text):
            replies.append(data["message_id"])

        platform._send_onebot_reply = send_reply
        lock = asyncio.Lock()
        await lock.acquire()

        async def release():
            await asyncio.sleep(0)
            lock.release()

        release_task = asyncio.create_task(release())
        await platform._route_group_with_merge(
            lock=lock,
            data={"message_type": "group", "group_id": 2001, "message_id": 12},
            content="overflow message",
            user_id="1002",
            user_name="Bob",
            group_id="2001",
            group_name="test group",
            sender_role="member",
            is_at_bot=True,
            extra={},
        )
        await release_task

        assert replies == [11, 12]
        assert "2001" not in platform._pending_group_messages

    asyncio.run(run())

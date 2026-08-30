"""
冒烟测试: 斜杠命令系统整合验证
- Bug1: "?"/"？" 不再误触发帮助命令; 无斜杠文本不触发斜杠命令
- Bug2: 群聊未@且无关键词时命令守卫拦截
- Bug3: OneBot 触发预过滤 + 合并窗口逻辑
- 整合: 两套命令系统收敛为统一斜杠命令系统（唯一入口）
- /help: 输出包含注册表命令 + 弥娅专属命令，准确完整
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_command_registry_slash_only():
    from core.command_system import get_command_registry

    registry = get_command_registry()
    assert registry.match("？") is None, "全角问号不应匹配任何命令"
    assert registry.match("?") is None, "半角问号不应匹配任何命令"
    assert registry.match("帮助") is None, "无斜杠'帮助'不应匹配斜杠命令"
    assert registry.match("/help") is not None, "/help 应匹配"
    assert registry.match("/帮助") is not None, "/帮助 应匹配（别名）"
    assert registry.match("/h") is not None, "/h 别名应匹配"
    print("[OK] CommandRegistry: 斜杠命令必须带 /, /help /帮助 /h 可用")


def test_legacy_handler_removed():
    """旧版兜底命令系统应已删除（整合为单一入口）"""
    import core.unified_platform_impl.message_mixin as mm

    assert not hasattr(mm, "_handle_slash_command"), "旧版 _handle_slash_command 应已删除"
    print("[OK] 旧版兜底命令系统已移除（唯一入口 = 统一斜杠命令系统）")


def test_group_command_guard():
    from core.unified_platform_impl.message_mixin import MessageMixin

    assert MessageMixin._group_command_allowed("/help", "private", False, {}) is True
    assert MessageMixin._group_command_allowed("/help", "group", True, {}) is True
    assert MessageMixin._group_command_allowed("/help", "group", False, {"is_owner": True}) is True
    assert MessageMixin._group_command_allowed("弥娅 /help", "group", False, {}) is True
    assert MessageMixin._group_command_allowed("/help", "group", False, {}) is False
    assert MessageMixin._group_command_allowed("/状态", "group", False, {}) is False
    assert MessageMixin._group_command_allowed("今天天气不错", "group", False, {}) is False
    print("[OK] 群聊命令守卫: 未@且无关键词时命令不执行")


def test_command_keywords_cleaned():
    """配置清理: 冗余关键词已删除, 专属命令清单已建立"""
    import json

    cfg = json.loads((ROOT / "config" / "text_config.json").read_text(encoding="utf-8"))
    ck = cfg.get("command_keywords", {})

    # 问号不再触发帮助
    assert "help" not in ck, "command_keywords 不应再有 help（/help 由统一系统接管）"
    # 冗余/占位符关键词已删除
    for gone in ("trpg", "exit", "stats", "admin", "faq", "system"):
        assert gone not in ck, f"冗余关键词 {gone} 应已删除"
    # 保留的弥娅专属命令关键词
    for keep in ("status", "form", "speak", "exist", "voice", "text", "local_playback",
                 "tts_engine", "version", "game_play", "memory_stats", "memory_search",
                 "memory_recent", "memory_tags", "memory_my", "sing"):
        assert keep in ck, f"保留关键词 {keep} 不应被误删"
    # slash_commands 节已删除
    assert "slash_commands" not in cfg, "旧版 slash_commands 节应已删除"
    # command_responses.help 硬编码文本已删除
    assert "help" not in cfg.get("command_responses", {}), "command_responses.help 硬编码应已删除"
    # 专属命令清单存在
    builtin = cfg.get("builtin_commands", {})
    assert builtin.get("items"), "builtin_commands.items 应存在"
    assert builtin.get("group_hint"), "builtin_commands.group_hint 应存在"
    print("[OK] 配置: 冗余关键词已清理, builtin_commands 清单已建立")


def test_help_output_complete():
    """/help 输出应包含统一命令系统的全部命令 + 弥娅专属命令"""
    from core.command_system import get_command_registry

    registry = get_command_registry()
    help_text = registry.get_help("")

    # 注册表命令（public 可见）
    for name in ("help", "profile", "summary", "faq", "feedback", "knowledge"):
        assert f"/{name}" in help_text, f"/help 输出应包含 /{name}"
    # stats/admin 仅管理员可见, public 权限下不应出现
    assert "/stats" not in help_text, "public 权限下 /help 不应列出管理员命令 /stats"
    assert "/admin" not in help_text, "public 权限下 /help 不应列出管理员命令 /admin"
    # 弥娅专属命令
    for name in ("/状态", "/形态", "/说话", "/存在", "/语音", "/文本", "/本地播放",
                 "/tts", "/版本", "记忆统计", "记忆搜索", "/游戏", "唱一下"):
        assert name in help_text, f"/help 输出应包含专属命令 {name}"
    # 不应包含已删除的占位符子命令
    assert "/system" not in help_text, "/help 不应再列出已删除的 /system"
    assert "trpg" not in help_text, "/help 不应再列出已删除的 trpg"

    # 管理员视角包含 stats/admin
    help_admin = registry.get_help("", permission="admin")
    assert "/stats" in help_admin and "/admin" in help_admin, "admin 权限下 /help 应列出 /stats /admin"

    # 指定命令的详细帮助
    faq_help = registry.get_help("faq")
    assert "ls" in faq_help and "search" in faq_help, "/help faq 应列出子命令"
    print("[OK] /help 输出: 完整准确, 权限过滤生效")


def test_onebot_prefilter_and_merge():
    """轻量验证 OneBot 平台的预过滤与合并窗口逻辑（不建立真实 WS 连接）"""
    from core.unified_platform_impl.onebot_platform import OneBotPlatform

    plat = OneBotPlatform.__new__(OneBotPlatform)
    plat.platform_id = "aiocqhttp"
    plat.config = {"bot_qq": "123456"}

    assert plat._should_dispatch({"post_type": "message", "message_type": "private"}) is True
    assert plat._should_dispatch({"post_type": "notice"}) is True
    assert (
        plat._should_dispatch(
            {
                "post_type": "message",
                "message_type": "group",
                "message": [{"type": "at", "data": {"qq": "123456"}}, {"type": "text", "data": {"text": "/help"}}],
                "sender": {"user_id": "999"},
            }
        )
        is True
    )
    assert (
        plat._should_dispatch(
            {
                "post_type": "message",
                "message_type": "group",
                "message": [{"type": "text", "data": {"text": "弥娅在吗"}}],
                "sender": {"user_id": "999"},
            }
        )
        is True
    )
    assert (
        plat._should_dispatch(
            {
                "post_type": "message",
                "message_type": "group",
                "message": [{"type": "text", "data": {"text": "/help"}}],
                "sender": {"user_id": "999"},
            }
        )
        is False
    )
    print("[OK] OneBot 预过滤: 裸命令/无关群消息被丢弃, @/关键词消息保留")

    async def _merge_test():
        plat._pending_group_messages = {}
        plat._process_locks = {}
        routed = []

        async def fake_route(**kwargs):
            routed.append(kwargs["content"])
            return "弥娅收到啦"

        async def fake_reply(data, text):
            return None

        plat.route_to_decision_hub = fake_route
        plat._send_onebot_reply = fake_reply
        plat._group_batching_enabled = lambda: True
        plat._group_batch_max = lambda: 15

        lock = asyncio.Lock()
        await lock.acquire()
        release_task = asyncio.create_task(_release_later(lock, 0.05))
        await plat._route_group_with_merge(
            lock=lock,
            data={"message_type": "group", "group_id": 100, "sender": {"user_id": 1}},
            content="弥娅你好",
            user_id="1",
            user_name="小明",
            group_id="100",
            group_name="测试群",
            sender_role="member",
            is_at_bot=True,
            extra={},
        )
        await release_task
        assert "100" in plat._pending_group_messages and len(plat._pending_group_messages["100"]) == 1
        print("[OK] 合并窗口: 群锁忙时消息进入缓冲而非排队")

        await asyncio.wait_for(plat._flush_group_pending("100", lock), timeout=5)
        assert "100" not in plat._pending_group_messages, "缓冲应已清空"
        assert routed and any("弥娅你好" in c for c in routed), f"合并消息应被路由处理: {routed}"
        print("[OK] 合并窗口: flush 合并处理不死锁, 缓冲正确清空")

    async def _release_later(lock, delay):
        await asyncio.sleep(delay)
        lock.release()

    asyncio.run(_merge_test())


if __name__ == "__main__":
    test_command_registry_slash_only()
    test_legacy_handler_removed()
    test_group_command_guard()
    test_command_keywords_cleaned()
    test_help_output_complete()
    test_onebot_prefilter_and_merge()
    print("\nALL_SMOKE_TESTS_PASSED")

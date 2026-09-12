"""OneBot 图片视觉分析触发条件回归测试。"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _platform():
    from core.unified_platform_impl.onebot_platform import OneBotPlatform

    platform = OneBotPlatform.__new__(OneBotPlatform)
    platform.platform_id = "aiocqhttp"
    platform.config = {"bot_qq": "123456"}
    return platform


def _image_message(*segments):
    return {
        "post_type": "message",
        "message_type": "group",
        "message": list(segments),
        "sender": {"user_id": "999"},
        "group_id": "10001",
    }


def _image():
    return {"type": "image", "data": {"file": "demo.jpg"}}


def _text(value):
    return {"type": "text", "data": {"text": value}}


def test_group_direct_image_requires_trigger(monkeypatch):
    import core.text_loader as text_loader

    monkeypatch.setattr(text_loader, "get_chatbot_keywords", lambda: ["弥娅"])
    platform = _platform()

    # OneBot 仍需保留消息处理机会（例如自动保存表情），但群聊触发判断
    # 必须阻止它进入视觉模型。
    assert platform._should_dispatch(_image_message(_image())) is True
    assert platform._should_dispatch(_image_message(_image(), _text("随便看看"))) is True
    assert platform._direct_image_analysis_allowed("随便看看", message_type="group") is False

    # @ 或关键词仍然可以触发图片视觉分析。
    assert platform._should_dispatch(
        _image_message(
            {"type": "at", "data": {"qq": "123456"}},
            _image(),
        )
    ) is True
    assert platform._should_dispatch(_image_message(_image(), _text("弥娅看看这个"))) is True
    assert platform._direct_image_analysis_allowed("弥娅看看这个", message_type="group") is True


def test_group_reply_and_non_image_media_are_retained(monkeypatch):
    import core.text_loader as text_loader

    monkeypatch.setattr(text_loader, "get_chatbot_keywords", lambda: ["弥娅"])
    platform = _platform()

    # 引用消息需要继续进入处理流程，由 OneBot 查询引用内容并按需分析。
    assert platform._should_dispatch(
        _image_message(
            {"type": "reply", "data": {"id": "42"}},
            _text("请看看"),
        )
    ) is True

    # 文件/语音不能因图片触发规则而被一并丢弃。
    assert platform._should_dispatch(
        _image_message(
            {"type": "file", "data": {"file": "demo.txt"}},
            _text("附件"),
        )
    ) is True


def test_direct_image_analysis_requires_quote_in_private(monkeypatch):
    import core.text_loader as text_loader

    monkeypatch.setattr(text_loader, "get_chatbot_keywords", lambda: ["弥娅"])
    platform = _platform()

    # 私聊直接图片不自动调用视觉模型；私聊引用图片由 reply 分支处理。
    assert platform._direct_image_analysis_allowed("随便", message_type="private") is False
    assert platform._direct_image_analysis_allowed("弥娅看看", message_type="private") is False

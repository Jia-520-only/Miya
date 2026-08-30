"""AI 客户端工具参数解析回归测试

背景: 无参数工具调用时模型会发送 arguments="{}"，空字典是合法解析结果，
但旧判断 `if raw_arguments and not tool_args:` 把 {} 当成失败，
导致所有无参数工具 (earth_summary/earth_checkin 等) 全部"参数解析失败"。
"""

from core.ai_client import BaseAIClient


def _fixer():
    return BaseAIClient(api_key="test", model="test")._fix_json_arguments


def test_empty_object_is_valid_no_arg_call():
    fix = _fixer()
    assert fix("{}") == {}
    assert fix("") == {}
    assert fix(None) == {}
    assert fix('{"limit": 20}') == {"limit": 20}
    assert fix("{\n  \"limit\": 3\n}") == {"limit": 3}


def test_garbage_arguments_return_none_not_empty_dict():
    fix = _fixer()
    assert fix("这不是JSON") is None
    assert fix("null") is None
    assert fix("[1, 2, 3]") is None  # 非对象 JSON 不能当工具参数


def test_failure_guard_distinguishes_empty_from_broken():
    """复现 _execute_tool_call 的判定逻辑: 只有 None 才算失败，{} 必须放行"""
    for raw, parsed, should_fail in [
        ("{}", {}, False),
        ("", {}, False),
        ('{"limit": 5}', {"limit": 5}, False),
        ("垃圾", None, True),
    ]:
        assert bool(raw and parsed is None) == should_fail, f"{raw!r} 判定错误"

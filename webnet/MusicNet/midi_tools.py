"""弥娅 MIDI 作曲工具 — ToolNet BaseTool 风格

提供 5 个 AI Agent 可调用的 MIDI 作曲工具:
    - midi_write       (写音符)
    - midi_diff        (精确编辑)
    - midi_batch_edit  (批量编辑/力度曲线)
    - midi_query       (查询统计)
    - midi_inspect     (逐音符查看)
"""

from __future__ import annotations

import json
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

from .music_project import (
    midi_batch_edit,
    midi_diff,
    midi_inspect,
    midi_query,
    midi_write,
    project_summary,
)


# ─── 辅助函数 ────────────────────────────────────────────────────


def _format_tool_result(
    title: str,
    operation_summary: dict[str, Any],
    session_summary: dict[str, Any],
) -> str:
    lines = [f"{title}"]
    lines.append(f"操作详情: {json.dumps(operation_summary, ensure_ascii=False)}")
    lines.append(
        f"项目概况: {session_summary['track_count']} 轨, "
        f"{session_summary['note_count']} 音符, "
        f"{session_summary.get('midi_event_count', 0)} MIDI事件, "
        f"{session_summary['tempo']} BPM"
    )
    return "\n".join(lines)


# ─── 5 个 MIDI 工具 ──────────────────────────────────────────────


class MidiWriteTool(BaseTool):
    """写 MIDI 音符：覆盖或追加"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "midi_write",
            "description": (
                "【作曲/编曲必调】当用户要求写旋律、创作音乐、编曲、生成乐谱、写歌时，"
                "必须调用此工具将音符写入弥娅音乐工作站轨道，不要只回复文字讨论。"
                "用于生成旋律、和弦、贝斯线、鼓点，或替换指定时间范围。"
                "时间单位均为「拍」(beat)。写入后自动持久化为 project.json。"
                "C 大调音高参考: C4=60, D4=62, E4=64, F4=65, G4=67, A4=69, B4=71, C5=72"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "track_id": {
                        "type": "integer",
                        "description": "目标轨道 ID",
                    },
                    "start": {
                        "type": "number",
                        "description": "覆盖范围的起始拍",
                    },
                    "end": {
                        "type": "number",
                        "description": "覆盖范围的结束拍",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["replace", "append"],
                        "default": "replace",
                        "description": "replace=替换重叠音符, append=保留已有音符",
                    },
                    "notes": {
                        "type": "array",
                        "description": "音符列表。start 和 duration 单位为拍。",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "pitch": {"type": "integer", "minimum": 0, "maximum": 127},
                                "start": {"type": "number", "minimum": 0},
                                "duration": {"type": "number", "minimum": 0},
                                "velocity": {"type": "integer", "minimum": 1, "maximum": 127},
                            },
                            "required": ["pitch", "start", "duration", "velocity"],
                        },
                    },
                },
                "required": ["track_id", "notes"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        project, summary = midi_write(
            args["track_id"],
            args["notes"],
            start=args.get("start"),
            end=args.get("end"),
            mode=args.get("mode", "replace"),
        )
        return _format_tool_result("MIDI 已写入", summary, project_summary(project))


class MidiDiffTool(BaseTool):
    """精确 MIDI 编辑：增删改音符和事件"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "midi_diff",
            "description": (
                "对弥娅音乐工作站中的现有 MIDI 音符和 MIDI 事件进行精确原子编辑。"
                "用于人性化、音符修正、力度变化、CC 自动化、弯音曲线、触后曲线等。"
                "时间均为拍 (beat)。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "track_id": {
                        "type": "integer",
                        "description": "目标轨道 ID",
                    },
                    "operations": {
                        "type": "array",
                        "description": "原子 MIDI 编辑操作列表",
                        "items": {
                            "type": "object",
                            "properties": {
                                "op": {
                                    "type": "string",
                                    "enum": [
                                        "add_note",
                                        "delete_note",
                                        "update_note",
                                        "modify_note",
                                        "add_event",
                                        "add_midi_event",
                                        "delete_event",
                                        "delete_midi_event",
                                        "update_event",
                                        "modify_event",
                                        "update_midi_event",
                                        "modify_midi_event",
                                        "draw_event_curve",
                                        "set_event_curve",
                                        "replace_event_curve",
                                        "draw_controller_curve",
                                        "set_controller_curve",
                                        "cc_curve",
                                        "pitch_bend_curve",
                                        "aftertouch_curve",
                                        "channel_pressure_curve",
                                        "velocity_curve",
                                        "draw_velocity_curve",
                                        "set_velocity_curve",
                                    ],
                                },
                                "id": {"type": "string", "description": "已有音符 ID"},
                                "note_id": {"type": "string"},
                                "event_id": {"type": "string"},
                                "clip_id": {"type": "string"},
                                "note": {"type": "object", "description": "add_note 时的音符"},
                                "event": {"type": "object", "description": "add_event 时的 MIDI 事件"},
                                "pitch": {"type": "integer", "minimum": 0, "maximum": 127},
                                "start": {"type": "number", "minimum": 0},
                                "duration": {"type": "number", "minimum": 0},
                                "velocity": {"type": "integer", "minimum": 1, "maximum": 127},
                                "channel": {"type": "integer", "minimum": 0, "maximum": 15},
                                "controller": {"type": "integer", "minimum": 0, "maximum": 127},
                                "value": {"type": "integer"},
                                "points": {"type": "array", "description": "曲线点 [{start, value}]"},
                                "mode": {"type": "string", "enum": ["replace", "append"]},
                            },
                            "required": ["op"],
                        },
                    },
                },
                "required": ["track_id", "operations"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        project, summary = midi_diff(args["track_id"], args["operations"])
        return _format_tool_result("MIDI diff 已应用", summary, project_summary(project))


class MidiBatchEditTool(BaseTool):
    """批量 MIDI 编辑：力度曲线、CC 曲线、人性化"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "midi_batch_edit",
            "description": (
                "基于音乐意图进行高级批量 MIDI 编辑。"
                "在编辑大量音符力度或绘制 CC、表情、调制、弯音、触后曲线时，"
                "请使用此工具而非低阶的 midi_diff。"
                "支持按轨道、Clip、拍范围、音高范围、控制器等进行筛选。"
                "必须提供写入范围：track_id、selection.track_ids 或 all_tracks=true。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "track_id": {
                        "type": "integer",
                        "description": "目标轨道 ID（除非 selection.track_ids 已设置或 all_tracks=true）",
                    },
                    "all_tracks": {
                        "type": "boolean",
                        "default": False,
                        "description": "显式允许批量编辑影响所有轨道",
                    },
                    "selection": {
                        "type": "object",
                        "description": "筛选条件: track_ids, clip_ids, range [start,end], pitch_range [low,high], note_ids, event_ids, controllers, event_types, channel",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "default": False,
                        "description": "仅预览摘要，不保存或同步",
                    },
                    "operations": {
                        "type": "array",
                        "description": "高级批量编辑操作",
                        "items": {
                            "type": "object",
                            "properties": {
                                "op": {
                                    "type": "string",
                                    "enum": [
                                        "velocity_set",
                                        "velocity_scale",
                                        "velocity_humanize",
                                        "velocity_accent",
                                        "velocity_shape",
                                        "velocity_ramp",
                                        "velocity_curve",
                                        "cc_curve",
                                        "controller_curve",
                                        "expression_curve",
                                        "modulation_curve",
                                        "pitch_bend_curve",
                                        "aftertouch_curve",
                                        "channel_pressure_curve",
                                        "cc_clear",
                                        "controller_clear",
                                        "event_clear",
                                    ],
                                },
                                "selection": {"type": "object", "description": "操作级筛选覆盖"},
                                "range": {
                                    "type": "array",
                                    "description": "拍范围 [start, end]",
                                    "items": {"type": "number"},
                                    "minItems": 2,
                                    "maxItems": 2,
                                },
                                "shape": {
                                    "type": "string",
                                    "enum": [
                                        "linear",
                                        "crescendo",
                                        "decrescendo",
                                        "swell",
                                        "phrase_swell",
                                        "fade_in",
                                        "fade_out",
                                        "ease_in",
                                        "ease_out",
                                        "ease_in_out",
                                        "lfo",
                                        "step",
                                        "hold",
                                    ],
                                },
                                "value": {"type": "integer"},
                                "velocity": {"type": "integer", "minimum": 1, "maximum": 127},
                                "from": {"type": "integer"},
                                "to": {"type": "integer"},
                                "start_value": {"type": "integer"},
                                "end_value": {"type": "integer"},
                                "min": {"type": "integer"},
                                "max": {"type": "integer"},
                                "amount": {"type": "integer", "description": "人性化/重音力度偏移量"},
                                "factor": {"type": "number"},
                                "offset": {"type": "number"},
                                "pattern": {
                                    "type": "string",
                                    "description": "velocity_accent 重音模式: downbeats, backbeat, offbeat, 或自定义 every/offset",
                                },
                                "every": {"type": "number"},
                                "controller": {"type": "integer", "minimum": 0, "maximum": 127},
                                "channel": {"type": "integer", "minimum": 0, "maximum": 15},
                                "points": {"type": "array", "description": "显式曲线点 [{start, value}]"},
                                "mode": {"type": "string", "enum": ["replace", "append"]},
                            },
                            "required": ["op"],
                        },
                    },
                },
                "required": ["operations"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        project, summary = midi_batch_edit(
            args["operations"],
            track_id=args.get("track_id"),
            selection=args.get("selection"),
            all_tracks=args.get("all_tracks", False),
            dry_run=args.get("dry_run", False),
        )
        prefix = "MIDI 批量编辑 [预览]" if args.get("dry_run") else "MIDI 批量编辑已应用"
        return _format_tool_result(prefix, summary, summary.get("project", project_summary(project)))


class MidiQueryTool(BaseTool):
    """MIDI 查询：项目/选区摘要统计"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "midi_query",
            "description": (
                "读取弥娅 MIDI 项目或选定区域的紧凑摘要，用于编辑前规划。"
                "查看轨道/Clip 数量、力度统计、音高范围、已有 CC/事件通道等信息。"
                "只读工具，支持并行调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "track_id": {"type": "integer", "description": "可选：限定查询某轨道"},
                    "selection": {
                        "type": "object",
                        "description": "筛选: track_ids, clip_ids, range, pitch_range, controllers, event_types",
                    },
                    "include": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["tracks", "clips", "notes", "velocity", "events", "controllers"],
                        },
                        "description": "要包含的信息类别（默认全部）",
                    },
                },
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        result = midi_query(
            track_id=args.get("track_id"),
            selection=args.get("selection"),
            include=args.get("include"),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class MidiInspectTool(BaseTool):
    """MIDI 检查：逐音符/事件查看，支持分页"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "midi_inspect",
            "description": (
                "读取选中区域内的 MIDI 音符和事件详情，支持有界分页。"
                "需要精确查看音符 ID、力度、时间、CC/事件值用于精确编辑时使用。"
                "只读工具，支持并行调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "track_id": {"type": "integer", "description": "可选：限定查询某轨道"},
                    "selection": {
                        "type": "object",
                        "description": "筛选: track_ids, clip_ids, range, pitch_range, note_ids, event_ids, controllers, event_types",
                    },
                    "include": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["notes", "events", "midi_events"]},
                        "description": "要包含的信息（默认 notes + events）",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 500,
                        "default": 120,
                        "description": "每页返回条数",
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0,
                        "description": "分页偏移",
                    },
                },
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        result = midi_inspect(
            track_id=args.get("track_id"),
            selection=args.get("selection"),
            include=args.get("include"),
            limit=args.get("limit", 120),
            offset=args.get("offset", 0),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class MidiPlayTool(BaseTool):
    """播放 MIDI 项目：渲染并播放当前音乐工作站项目"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "midi_play",
            "description": (
                "将弥娅音乐工作站当前项目渲染为音频并播放。"
                "在用户写完/编辑完旋律后调用此工具让他们聆听效果。"
                "如需导出为文件请使用 midi_render。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bpm": {
                        "type": "number",
                        "description": "覆盖项目 BPM（默认使用项目 BPM）",
                    },
                },
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        from .music_project import load_project, project_summary
        from .audio_engine import play_project

        proj = load_project()
        summary = project_summary(proj)
        bpm = args.get("bpm") or summary["tempo"]

        play_project(proj, bpm=bpm)

        dur = summary["length_beats"] / (bpm / 60.0)
        return (
            f"播放完成: {summary['title']}\n"
            f"{summary['track_count']} 轨, {summary['note_count']} 音符, "
            f"{dur:.1f} 秒 @ {bpm} BPM"
        )


class MidiRenderTool(BaseTool):
    """导出 MIDI 项目为 WAV 音频文件"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "midi_render",
            "description": ("将弥娅音乐工作站当前项目渲染为 WAV 音频文件。用于导出、分享或后续处理。返回文件路径。"),
            "parameters": {
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "输出 WAV 文件的绝对路径（可选，默认使用临时路径）",
                    },
                    "bpm": {
                        "type": "number",
                        "description": "覆盖项目 BPM（默认使用项目 BPM）",
                    },
                },
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        from pathlib import Path
        from .music_project import load_project, project_summary
        from .audio_engine import render_project_to_wav

        proj = load_project()
        summary = project_summary(proj)
        bpm = args.get("bpm") or summary["tempo"]
        output = Path(args["output_path"]) if args.get("output_path") else None

        path = render_project_to_wav(proj, output_path=output, bpm=bpm)
        size_kb = path.stat().st_size / 1024
        dur = summary["length_beats"] / (bpm / 60.0)

        return (
            f"渲染完成: {summary['title']}\n"
            f"文件: {path}\n"
            f"{summary['track_count']} 轨, {summary['note_count']} 音符, "
            f"{dur:.1f} 秒 @ {bpm} BPM, {size_kb:.0f} KB"
        )

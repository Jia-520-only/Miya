"""Local expression analysis: interpretable geometry over a fragile classifier.

The five landmarks YuNet provides are not enough to score emotion, but they are
enough to measure a few things honestly. These tests pin the geometry and pin
the honesty rules: a classifier that never varies must not be quoted.
"""

from __future__ import annotations

import math

import pytest

from mcpserver.screen_vision import local_camera
from mcpserver.screen_vision.local_camera import (
    MOUTH_OPEN_RATIO,
    describe_expression,
    expression_model_status,
    expression_signals,
    rig_parameters,
)


def _face(
    *,
    eye_gap: float = 0.20,
    mouth_open: float = 0.0,
    nose_shift: float = 0.0,
    tilt: float = 0.0,
    box_width: float = 0.40,
) -> dict:
    """A face with realistic 2D proportions, expressed in inter-eye units.

    Eyes sit one inter-eye distance apart, the nose about 0.55 below the eye
    line, and the closed mouth about 0.45 below the nose. `mouth_open` adds
    jaw drop in the same units, which is what a real open mouth does.

    Landmarks are emitted in YuNet's real order - the person's right eye first -
    not in the (left, right, ...) order this helper used to assume. Because the
    module read the pair left-first, a helper that agreed with it kept the
    mirrored tilt sign invisible.
    """
    nose_below_eyes = 0.55
    closed_mouth_below_nose = 0.45
    # Convert inter-eye units to normalized frame coordinates.
    unit = eye_gap
    eye_y = 0.40
    # `tilt` rotates the eye line around its midpoint, which is what a real head
    # tilt does. Raising only one eye (as this helper used to) drags the mouth
    # measurably closer to the eye line, so an "open mouth" on a tilted head read
    # as closed - a geometry that cannot happen on a person.
    drop = math.tan(math.radians(tilt)) * eye_gap / 2 if tilt else 0.0
    right_eye = {"x": 0.50 + eye_gap / 2, "y": eye_y + drop}
    left_eye = {"x": 0.50 - eye_gap / 2, "y": eye_y - drop}
    nose = {"x": 0.50 + nose_shift * eye_gap, "y": eye_y + nose_below_eyes * unit}
    mouth_y = eye_y + (nose_below_eyes + closed_mouth_below_nose + mouth_open) * unit
    left_mouth = {"x": 0.50 - 0.45 * unit, "y": mouth_y}
    right_mouth = {"x": 0.50 + 0.45 * unit, "y": mouth_y}
    return {
        "x": 0.50 - box_width / 2, "y": 0.25, "width": box_width, "height": 0.55,
        "score": 0.95,
        "keypoints": [right_eye, left_eye, nose, right_mouth, left_mouth],
    }


def _real_frame():
    """A real image, so the face-crop geometry is exercised rather than stubbed.

    Anything that reaches ``_face_crop`` through ``analyze_local_frame`` must be
    able to multiply the normalized box by real pixel dimensions; stubbing the
    crop out is exactly how a 0x0 crop survived.
    """
    from PIL import Image

    return Image.new("RGB", (640, 480), (130, 130, 130))


@pytest.fixture(autouse=True)
def _fresh_adaptive_state():
    """Learned mouth/pose state must not leak between tests."""
    local_camera.reset_adaptive_state()
    yield
    local_camera.reset_adaptive_state()


def test_expression_signals_are_available_from_five_landmarks():
    signals = expression_signals(_face())
    assert signals["available"] is True
    assert signals["mouth_open_ratio"] > 0
    assert signals["eye_span_ratio"] > 0
    assert signals["mouth_open"] is False
    assert signals["head_tilted"] is False
    assert signals["head_turned"] is False


def test_an_open_mouth_raises_the_open_ratio_and_flags_it():
    closed = expression_signals(_face(mouth_open=0.0))
    opened = expression_signals(_face(mouth_open=0.45))
    assert opened["mouth_open_ratio"] > closed["mouth_open_ratio"]
    # With real proportions a closed mouth stays under the threshold and a wide
    # open jaw clearly crosses it.
    assert closed["mouth_open"] is False
    assert opened["mouth_open"] is True


def test_the_old_mouth_threshold_could_never_fire():
    """Regression: the default used to be 1.9 against a scale that peaks near 1.4."""
    widest = expression_signals(_face(mouth_open=0.9))["mouth_open_ratio"]
    closed = expression_signals(_face(mouth_open=0.0))["mouth_open_ratio"]
    assert widest > MOUTH_OPEN_RATIO, "阈值高到任何真实人脸都触发不了"
    assert closed < MOUTH_OPEN_RATIO, "阈值低到闭着嘴也会被当成张口"


def test_mouth_open_ratio_is_independent_of_mouth_width():
    """The measure must track the jaw, not how wide someone's mouth is."""
    for width_factor in (0.30, 0.45, 0.60):
        face = _face(mouth_open=0.30)
        left, right = face["keypoints"][3], face["keypoints"][4]
        centre = (float(left["x"]) + float(right["x"])) / 2
        half = 0.20 * width_factor
        left["x"], right["x"] = centre - half, centre + half
        assert expression_signals(face)["mouth_open_ratio"] == pytest.approx(
            expression_signals(_face(mouth_open=0.30))["mouth_open_ratio"], rel=0.03)


def test_an_open_mouth_is_also_caught_by_the_dark_cavity_cue(monkeypatch):
    """The ratio alone is person-dependent, so the dark cavity backs it up."""
    monkeypatch.setattr(local_camera, "_dark_fraction", lambda _image: 0.4)
    signals = expression_signals(_face(mouth_open=0.0), face_image=object())
    assert signals["mouth_open"] is False
    assert signals["mouth_likely_open"] is True


def test_mouth_width_is_measured_independently_of_opening():
    narrow = expression_signals(_face(eye_gap=0.20))
    assert narrow["mouth_width_ratio"] == pytest.approx(0.90, abs=0.05)


def test_mouth_wide_flags_a_stretched_mouth_only():
    neutral = expression_signals(_face())
    assert neutral["mouth_wide"] is False
    # Widen around the mouth centre. The corner carrying the larger x is the
    # *left* one, so pushing index 3 outward means increasing x - the reverse of
    # what the old mirrored landmark order implied, which narrowed the mouth and
    # still passed.
    stretched = _face()
    stretched["keypoints"][3]["x"] += 0.11
    stretched["keypoints"][4]["x"] -= 0.11
    assert expression_signals(stretched)["mouth_wide"] is True


# --- rig parameters --------------------------------------------------------


def test_rig_jaw_stays_near_closed_for_a_closed_mouth():
    """A closed mouth must not visibly open the jaw.

    The baseline (`RIG_MOUTH_CLOSED`) is where the jaw offset reaches zero, and
    real closed mouths measure a little above or below it, so the honest claim
    is "barely moves" rather than "exactly zero".
    """
    closed = expression_signals(_face(mouth_open=0.0))
    rig = rig_parameters(closed)
    assert rig["JawOpen"] <= 0.15
    # And it must be a small fraction of a deliberately open mouth.
    opened = rig_parameters(expression_signals(_face(mouth_open=0.6)))
    assert opened["JawOpen"] > rig["JawOpen"] * 2


def test_rig_parameters_open_the_jaw_monotonically():
    values = [rig_parameters(expression_signals(_face(mouth_open=amount)))["JawOpen"]
              for amount in (0.0, 0.2, 0.45, 0.9)]
    assert values == sorted(values)
    assert values[-1] > values[0]
    # Clamped at the top rather than running away.
    assert max(values) <= 0.55 + 1e-6


def test_rig_parameters_never_go_out_of_range():
    extreme = expression_signals(_face(mouth_open=99.0, tilt=90.0, nose_shift=99.0))
    rig = rig_parameters(extreme)
    assert all(isinstance(value, float) for value in rig.values())
    assert -22.0 <= rig["ParamAngleZ"] <= 22.0
    assert -14.0 <= rig["ParamAngleX"] <= 14.0
    assert 0.0 <= rig["JawOpen"] <= 0.55


def test_rig_parameters_turn_the_head_the_way_it_actually_turned():
    """Opposite head tilts must roll the rig in opposite directions.

    Which absolute sign Live2D's ParamAngleZ wants depends on the model's own
    rotation convention, which this layer cannot see, so the honest claim is the
    one that can be checked here: the two tilts must not collapse to the same
    roll. The direction itself is carried by ``head_tilt_degrees``.
    """
    lean_viewer_left = expression_signals(_face(tilt=20.0))
    lean_viewer_right = expression_signals(_face(tilt=-20.0))
    # A positive tilt lowers the person's own left eye, which is a lean toward
    # the viewer's left, so the measured angle is negative on that side.
    assert lean_viewer_left["head_tilt_degrees"] < 0 < lean_viewer_right["head_tilt_degrees"]
    roll_left = rig_parameters(lean_viewer_left)["ParamAngleZ"]
    roll_right = rig_parameters(lean_viewer_right)["ParamAngleZ"]
    # Opposite directions, not the same one twice - the mirrored-tilt bug made
    # these two collapse onto each other.
    assert roll_left * roll_right < 0
    assert abs(roll_left) > 1.0 and abs(roll_right) > 1.0

    yaw_left = rig_parameters(expression_signals(_face(nose_shift=-0.5)))
    yaw_right = rig_parameters(expression_signals(_face(nose_shift=0.5)))
    assert yaw_left["ParamAngleX"] < 0 < yaw_right["ParamAngleX"]


def test_rig_parameters_do_not_invent_brows_or_eyelids():
    """There are no landmarks for brows or lids, so no parameters for them."""
    rig = rig_parameters(expression_signals(_face(mouth_open=0.5, tilt=15.0)))
    assert rig, "至少应该产出一些参数"
    for param in rig:
        assert "Brow" not in param, f"{param} 没有关键点支撑，不该被编出来"
        assert "Eye" not in param, f"{param} 没有关键点支撑，不该被编出来"


def test_rig_parameters_are_empty_without_a_measurable_face():
    assert rig_parameters(None) == {}
    assert rig_parameters({}) == {}
    assert rig_parameters({"available": False}) == {}


def test_rig_parameters_survive_nonsense_numbers():
    """They land in a render loop, so NaN must not poison the rig."""
    rig = rig_parameters({"available": True, "mouth_open_ratio": float("nan"),
                          "head_tilt_degrees": float("nan"), "nose_offset_ratio": float("nan"),
                          "mouth_width_ratio": float("nan")})
    assert all(value == value for value in rig.values()), "NaN 泄漏进了参数"


def test_analysis_result_carries_ready_to_apply_rig_parameters(monkeypatch):
    """The frontend must not need a second copy of the conversion."""
    monkeypatch.setattr(local_camera, "_decode_image", lambda _d: _real_frame())
    monkeypatch.setattr(local_camera, "frame_luminance", lambda _i: 90.0)
    monkeypatch.setattr(local_camera, "_detect_faces", lambda _i, threshold=None: [_face(mouth_open=0.45)])
    monkeypatch.setattr(local_camera, "_pose", lambda _i: {"keypoints": [{"x": 0.5, "y": 0.5, "confidence": 0.9}] * 17})

    result = local_camera.analyze_local_frame(
        "data:image/jpeg;base64,ZmFrZQ==", identity=False, emotion=False, pose=True, faces=True)
    observation = result["observations"][0]
    assert observation["rig"]["JawOpen"] > 0
    assert set(observation["rig"]) == {
        "JawOpen", "ParamMouthOpenY", "MouthFunnel", "ParamMouthForm",
        "ParamAngleZ", "ParamBodyAngleZ", "ParamAngleX", "ParamBodyAngleX",
    }


# --- face detection on demand ----------------------------------------------


def test_faces_flag_runs_detection_even_with_identity_and_emotion_off(monkeypatch):
    """Expression geometry needs the detector; the rig would stall without it."""
    local_camera._emotion_probe = {"label": "", "same_count": 0, "distinct": 0}
    monkeypatch.setattr(local_camera, "_decode_image", lambda _d: _real_frame())
    monkeypatch.setattr(local_camera, "frame_luminance", lambda _i: 90.0)
    monkeypatch.setattr(local_camera, "_pose", lambda _i: {"keypoints": [{"x": 0.5, "y": 0.5, "confidence": 0.9}] * 17})
    seen: list[int] = []

    def detector(_image, threshold=None):
        seen.append(1)
        return [_face()]

    monkeypatch.setattr(local_camera, "_detect_faces", detector)
    result = local_camera.analyze_local_frame(
        "data:image/jpeg;base64,ZmFrZQ==", identity=False, emotion=False, pose=True, faces=True
    )
    assert seen, "faces=True 必须触发人脸检测"
    assert result["faces"] == 1
    assert result["observations"][0]["expression"]["available"] is True
    # Identity must not be matched just because a face was detected.
    assert "identity" not in result["observations"][0]


def test_faces_false_skips_the_detector_entirely(monkeypatch):
    monkeypatch.setattr(local_camera, "_decode_image", lambda _d: _real_frame())
    monkeypatch.setattr(local_camera, "frame_luminance", lambda _i: 90.0)
    monkeypatch.setattr(local_camera, "_pose", lambda _i: {"keypoints": [{"x": 0.5, "y": 0.5, "confidence": 0.9}] * 17})

    def fail_detector(*_args, **_kwargs):
        raise AssertionError("faces=False 时不应该跑人脸检测")

    monkeypatch.setattr(local_camera, "_detect_faces", fail_detector)
    result = local_camera.analyze_local_frame(
        "data:image/jpeg;base64,ZmFrZQ==", identity=False, emotion=False, pose=True, faces=False
    )
    assert result["faces"] == 0


def test_default_detection_still_follows_identity_and_emotion(monkeypatch):
    monkeypatch.setattr(local_camera, "_decode_image", lambda _d: _real_frame())
    monkeypatch.setattr(local_camera, "frame_luminance", lambda _i: 90.0)
    monkeypatch.setattr(local_camera, "_pose", lambda _i: {"keypoints": [{"x": 0.5, "y": 0.5, "confidence": 0.9}] * 17})
    calls: list[int] = []
    monkeypatch.setattr(local_camera, "_detect_faces",
                        lambda _i, threshold=None: (calls.append(1), [_face()])[1])

    local_camera.analyze_local_frame("data:image/jpeg;base64,ZmFrZQ==", identity=False, emotion=False, pose=True)
    assert calls == [], "默认（未指定 faces）在关闭身份与表情时不该检测人脸"

    monkeypatch.setattr(local_camera, "_embedding", lambda _image, **_kwargs: [1.0, 0.0, 0.0])
    local_camera.analyze_local_frame("data:image/jpeg;base64,ZmFrZQ==", identity=True, pose=True)
    assert calls, "开启身份时必须检测人脸"


def test_a_turned_head_shows_as_a_nose_offset():
    frontal = expression_signals(_face(nose_shift=0.0))
    turned = expression_signals(_face(nose_shift=0.6))
    assert abs(turned["nose_offset_ratio"]) > abs(frontal["nose_offset_ratio"])
    assert turned["head_turned"] is True
    assert frontal["head_turned"] is False


def test_a_tilted_head_is_measured_in_degrees():
    level = expression_signals(_face(tilt=0.0))
    tilted = expression_signals(_face(tilt=20.0))
    assert abs(level["head_tilt_degrees"]) < 1.0
    assert abs(tilted["head_tilt_degrees"]) > 15.0
    assert tilted["head_tilted"] is True
    assert level["head_tilted"] is False


def test_measurements_are_normalised_so_distance_does_not_matter():
    """Leaning toward or away from the camera must not change the reading."""
    near = expression_signals(_face(eye_gap=0.30, mouth_open=0.30, box_width=0.60))
    far = expression_signals(_face(eye_gap=0.15, mouth_open=0.30, box_width=0.30))
    assert near["mouth_open_ratio"] == pytest.approx(far["mouth_open_ratio"], rel=0.02)
    assert near["mouth_width_ratio"] == pytest.approx(far["mouth_width_ratio"], rel=0.02)


def test_missing_landmarks_report_unavailable_instead_of_guessing():
    signals = expression_signals({"keypoints": [{"x": 0.1, "y": 0.1}]})
    assert signals["available"] is False
    assert "关键点不足" in signals["reason"]
    assert describe_expression(signals) == ""


def test_describe_expression_stays_silent_when_nothing_holds():
    assert describe_expression(expression_signals(_face())) == ""


def test_describe_expression_speaks_only_about_what_it_measured():
    # Settle the resting-mouth baseline first: without it the code refuses to
    # claim an open mouth at all, which is the intended cold-start behaviour.
    for _ in range(45):
        expression_signals(_face(mouth_open=0.0))
    text = describe_expression(expression_signals(_face(mouth_open=0.45, tilt=20.0)))
    assert "嘴是张着的" in text
    assert "歪着" in text
    # No emotion words: geometry cannot know how someone feels.
    for word in ("开心", "难过", "生气", "情绪", "表情"):
        assert word not in text


def test_unavailable_signals_never_produce_a_sentence():
    assert describe_expression(None) == ""
    assert describe_expression({}) == ""


# --- the honesty rules for the classifier ----------------------------------


def test_a_classifier_that_never_varies_is_flagged_uninformative(monkeypatch):
    local_camera._emotion_probe = {"label": "", "same_count": 0, "distinct": 0}
    monkeypatch.setattr(local_camera, "_decode_image", lambda _d: _real_frame())
    monkeypatch.setattr(local_camera, "frame_luminance", lambda _i: 90.0)
    monkeypatch.setattr(local_camera, "_detect_faces", lambda _i, threshold=None: [_face()])
    monkeypatch.setattr(local_camera, "_emotion", lambda _i: {"label": "开心", "confidence": 0.74, "distribution": []})

    result = None
    for _ in range(14):
        result = local_camera.analyze_local_frame("data:image/jpeg;base64,ZmFrZQ==", identity=False, emotion=True)
    emotion = result["observations"][0]["emotion"]
    assert emotion["uninformative"] is True
    assert "不能当作表情线索" in emotion["reason"]
    # And the sentence must not quote the constant label as if it meant something.
    assert "表情看着有点开心" not in result["message"]
    local_camera._emotion_probe = {"label": "", "same_count": 0, "distinct": 0}


def test_a_classifier_that_varies_is_left_alone(monkeypatch):
    local_camera._emotion_probe = {"label": "", "same_count": 0, "distinct": 0}
    labels = iter(["开心", "中性", "开心", "惊讶"])
    monkeypatch.setattr(local_camera, "_decode_image", lambda _d: _real_frame())
    monkeypatch.setattr(local_camera, "frame_luminance", lambda _i: 90.0)
    monkeypatch.setattr(local_camera, "_detect_faces", lambda _i, threshold=None: [_face()])
    monkeypatch.setattr(local_camera, "_emotion",
                        lambda _i: {"label": next(labels, "中性"), "confidence": 0.8, "distribution": []})

    result = None
    for _ in range(4):
        result = local_camera.analyze_local_frame("data:image/jpeg;base64,ZmFrZQ==", identity=False, emotion=True)
    emotion = result["observations"][0]["emotion"]
    assert "uninformative" not in emotion
    local_camera._emotion_probe = {"label": "", "same_count": 0, "distinct": 0}


def test_expression_status_is_reported_without_leaking_frames():
    local_camera._emotion_probe = {"label": "", "same_count": 0, "distinct": 0}
    status = expression_model_status()
    assert set(status) == {"distinct_labels_seen", "identical_run", "stuck"}
    assert status["stuck"] is False


def test_analysis_exposes_expression_geometry_in_the_result(monkeypatch):
    local_camera._emotion_probe = {"label": "", "same_count": 0, "distinct": 0}
    monkeypatch.setattr(local_camera, "_decode_image", lambda _d: _real_frame())
    monkeypatch.setattr(local_camera, "frame_luminance", lambda _i: 90.0)
    monkeypatch.setattr(local_camera, "_detect_faces", lambda _i, threshold=None: [_face(mouth_open=0.45, tilt=18.0)])
    monkeypatch.setattr(local_camera, "_emotion", lambda _i: {"label": "中性", "confidence": 0.6, "distribution": []})
    # Establish this face's resting mouth before judging the open one; a cold
    # baseline deliberately refuses to call a mouth open.
    for _ in range(45):
        expression_signals(_face(mouth_open=0.0))

    result = local_camera.analyze_local_frame("data:image/jpeg;base64,ZmFrZQ==", identity=False, emotion=True)
    observation = result["observations"][0]
    assert observation["expression"]["mouth_open"] is True
    assert observation["expression"]["head_tilted"] is True
    assert "嘴是张着的" in observation["expression_text"]
    assert "嘴是张着的" in result["message"]
    local_camera._emotion_probe = {"label": "", "same_count": 0, "distinct": 0}

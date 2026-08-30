"""
人格向量与基底
定义弥娅的基础人格特质和行为倾向
支持形态系统和专属称呼体系

注意：所有配置从 YAML 文件加载，详见 config/personalities/
"""

import json
from pathlib import Path
from typing import Dict, Optional

from core.constants import Encoding


class Personality:
    """人格向量系统（YAML配置驱动）"""

    def __init__(self):
        self._loader = None
        self._current_config = None
        self._use_yaml = False
        self._core_forms = {}
        self._correlations = {}
        self._default_vectors = {}
        self._default_boundaries = {}
        self._core_beliefs = {}

        try:
            from core.personality_loader import get_personality_loader

            self._loader = get_personality_loader()
            self._use_yaml = True
            self._current_config = self._loader.load("_default")

            self.titles = self._current_config.get("titles", {"default": ["佳"]})
            self.quotes = self._current_config.get("quotes", {"being": "我在。"})
            self._load_core_config()
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"[Personality] YAML加载失败: {e}")
            self._use_yaml = False
            self.titles = {"default": ["佳"]}
            self.quotes = {"being": "我在。"}

        self.vectors = self._default_vectors.copy()
        self.boundaries = self._default_boundaries.copy()
        self.core_beliefs = self._core_beliefs.copy()

        self.current_form = "normal"
        self.current_core_form = None
        self.current_title = "你"
        self.speak_mode = "casual"
        self.vector_history = []
        self._chat_forms: Dict[str, str] = {}
        self._chat_speak_modes: Dict[str, str] = {}
        self._default_form = "normal"

        self._last_form_file = Path("data/last_form.json")
        self._restore_last_form()

    def _load_core_config(self):
        """从配置文件加载核心配置"""
        if not self._loader:
            return
        base_config = self._loader._load_base_config() or {}

        self._core_forms = base_config.get("core_forms", {})
        correlations = base_config.get("personality_correlations", {})
        self._correlations = {(k.split("-")[0], k.split("-")[1]): v for k, v in correlations.items()}
        self._default_vectors = base_config.get(
            "default_vectors",
            {
                "logic": 0.75,
                "memory": 0.95,
                "warmth": 0.85,
                "empathy": 0.9,
                "resilience": 0.8,
                "creativity": 0.8,
            },
        )
        self._default_boundaries = base_config.get(
            "default_boundaries",
            {
                "min_logic": 0.5,
                "max_logic": 1.0,
                "min_memory": 0.7,
                "max_memory": 1.0,
                "min_warmth": 0.3,
                "max_warmth": 1.0,
                "min_empathy": 0.3,
                "max_empathy": 1.0,
                "min_resilience": 0.3,
                "max_resilience": 1.0,
                "min_creativity": 0.3,
                "max_creativity": 1.0,
            },
        )
        self._core_beliefs = base_config.get("core_beliefs", {})

    def set_form(self, form_name: str) -> bool:
        if self._use_yaml and self._loader:
            self._current_config = self._loader.load(form_name)
            self.current_form = form_name
            self._persist_last_form()
            return True
        return False

    def get_current_form(self) -> Dict:
        if self._use_yaml and self._current_config:
            return self._current_config
        return {"name": "normal", "description": "默认人格"}

    def _persist_last_form(self):
        try:
            import json

            self._last_form_file.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "current_form": self.current_form,
                "chat_forms": self._chat_forms,
            }
            with open(self._last_form_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _restore_last_form(self):
        try:
            import json

            if not self._last_form_file.exists():
                return
            with open(self._last_form_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            self._chat_forms = state.get("chat_forms", {})
            last_form = state.get("current_form")
            if last_form and last_form != "normal" and self._loader:
                available = self._loader.list_available()
                if available and last_form in available:
                    self.set_form(last_form)
        except Exception:
            pass

    def get_form_config(self, form_name: str) -> Dict:
        if self._use_yaml and self._loader:
            try:
                return self._loader.load(form_name)
            except Exception:
                pass
        return {"name": "normal", "description": "默认人格"}

    def get_chat_key(self, user_id: str, group_id: str = "") -> str:
        if group_id and group_id != "0":
            return f"group_{group_id}"
        return f"private_{user_id}"

    def set_form_for_chat(self, form_name: str, user_id: str, group_id: str = "") -> bool:
        if not self._use_yaml or not self._loader:
            return False
        try:
            self._loader.load(form_name)
        except Exception:
            return False
        chat_key = self.get_chat_key(user_id, group_id)
        self._chat_forms[chat_key] = form_name
        return True

    def set_form_global(self, form_name: str) -> bool:
        """设置全局形态并清除所有独立聊天形态，确保所有场景一致"""
        if not self._use_yaml or not self._loader:
            return False
        try:
            self._loader.load(form_name)
        except Exception:
            return False
        self._chat_forms.clear()
        return self.set_form(form_name)

    def get_form_for_chat(self, user_id: str = "", group_id: str = "") -> str:
        if not user_id and not group_id:
            return self.current_form
        chat_key = self.get_chat_key(user_id, group_id)
        result = self._chat_forms.get(chat_key, self.current_form)
        return result

    def clear_chat_form(self, user_id: str = "", group_id: str = "") -> bool:
        chat_key = self.get_chat_key(user_id, group_id)
        if chat_key in self._chat_forms:
            del self._chat_forms[chat_key]
            return True
        return False

    def get_all_chat_forms(self) -> Dict[str, str]:
        return dict(self._chat_forms)

    def set_core_form(self, form_name: str) -> bool:
        if form_name not in self._core_forms:
            return False
        self.current_core_form = form_name
        return True

    def get_current_core_form(self) -> Optional[Dict]:
        if not self.current_core_form:
            return None
        return self._core_forms.get(self.current_core_form)

    def clear_core_form(self) -> None:
        self.current_core_form = None
        self.core_form_timeout = None

    def activate_core_form(self, form_name: str, auto_restore: bool = False, timeout: int = 300) -> bool:
        if form_name not in self._core_forms:
            return False
        self.current_core_form = form_name
        if auto_restore:
            import time

            self.core_form_timeout = time.time() + timeout
        else:
            self.core_form_timeout = None
        return True

    def check_core_form_timeout(self) -> bool:
        if not self.core_form_timeout:
            return False
        import time

        if time.time() > self.core_form_timeout:
            self.current_core_form = None
            self.core_form_timeout = None
            return True
        return False

    def gradient_to(self, target_form: str, speed: float = 0.15) -> bool:
        if not self._use_yaml or not self._loader:
            return False
        try:
            target_config = self._loader.load(target_form)
        except Exception:
            return False

        weights = target_config.get("weights", {})
        for god, delta in weights.items():
            if god in self.vectors:
                self.update_vector(god, delta * speed)

        self.current_form = target_form
        return True

    def auto_detect_form(self, user_message: str, emotion_state: Optional[Dict] = None) -> Optional[str]:
        base_config = {}
        if self._use_yaml and self._loader:
            base_config = self._loader._load_base_config() or {}

        auto_detect = base_config.get("auto_detect", {})
        if not auto_detect:
            return None

        content = user_message.lower()

        for config in [
            auto_detect.get("negative", {}),
            auto_detect.get("serious", {}),
            auto_detect.get("positive", {}),
            auto_detect.get("philosophy", {}),
        ]:
            keywords = config.get("keywords", [])
            form = config.get("form")
            if keywords and form and any(kw in content for kw in keywords):
                return form

        long_conv = auto_detect.get("long_conversation", {})
        if emotion_state and emotion_state.get("message_count", 0) > long_conv.get("threshold", 10):
            return long_conv.get("form")

        return None

    def get_status_for_prompt(self, user_id: str = "", group_id: str = "") -> str:
        form_name = self.get_form_for_chat(user_id, group_id)
        form_info = self.get_form_config(form_name)
        if self._use_yaml and self._loader and form_info:
            return self._loader.get_status_for_prompt(form_info)
        return form_info.get("status_prompt", "")

    def get_status_for_log(self) -> str:
        form_info = self.get_current_form()
        form_names = form_info.get("form_names", {})
        core_abbrev = form_info.get("core_abbrev", {})

        form_name = form_names.get(self.current_form, "")
        core_name = core_abbrev.get(self.current_core_form, "") if self.current_core_form else ""

        if core_name:
            return f"[{form_name}|{self.speak_mode}|{core_name}]"
        else:
            return f"[{form_name}|{self.speak_mode}]"

    def set_speak_mode(self, mode: str) -> bool:
        valid_modes = ["casual", "catching", "confiding"]
        if mode not in valid_modes:
            return False
        self.speak_mode = mode
        return True

    def get_speak_mode(self) -> str:
        return self.speak_mode

    def get_speak_mode_description(self) -> str:
        form_info = self.get_current_form()
        descriptions = form_info.get("speak_mode_descriptions", {})
        return descriptions.get(self.speak_mode, "")

    def set_title_by_mood(self, mood: str):
        if mood in self.titles:
            titles_list = self.titles[mood]
            self.current_title = titles_list[0]

    def get_current_title(self) -> str:
        return self.current_title

    def get_address_phrase(self) -> str:
        form_info = self.get_current_form()
        phrases = form_info.get("address_phrases", {})
        return phrases.get(self.current_title, "")

    def get_quote(self, quote_type: str) -> str:
        form_info = self.get_current_form()
        quotes = form_info.get("quotes", {})
        return quotes.get(quote_type, "")

    def get_greeting(self) -> str:
        form_info = self.get_current_form()
        greetings = form_info.get("greetings", [])
        import random

        return random.choice(greetings) if greetings else ""

    def get_poke_response(self) -> str:
        form_info = self.get_current_form()
        responses = form_info.get("poke_responses", [])
        import random

        return random.choice(responses) if responses else ""

    def get_greeting_keywords(self) -> list:
        form_info = self.get_current_form()
        return form_info.get("greeting_keywords", [])

    def is_greeting(self, text: str) -> bool:
        keywords = self.get_greeting_keywords()
        text_lower = text.lower().strip()
        return any(g in text_lower for g in keywords)

    def get_vector(self, key: str) -> float:
        base_value = self.vectors.get(key, 0.5)
        form_info = self.get_current_form()
        boost_key = f"{key}_boost"
        if boost_key in form_info:
            base_value += form_info[boost_key]
        boundary_min = self.boundaries.get(f"min_{key}", 0.0)
        boundary_max = self.boundaries.get(f"max_{key}", 1.0)
        base_value = max(boundary_min, min(boundary_max, base_value))
        return round(base_value, 2)

    def update_vector(self, key: str, delta: float) -> bool:
        if key not in self.vectors:
            return False
        old_value = self.vectors[key]
        new_value = old_value + delta
        boundary_min = self.boundaries.get(f"min_{key}", 0.0)
        boundary_max = self.boundaries.get(f"max_{key}", 1.0)
        self.vectors[key] = round(max(boundary_min, min(boundary_max, new_value)), 2)
        self._apply_correlation_constraints(key, old_value, self.vectors[key])
        self._record_vector_history()
        return True

    def _apply_correlation_constraints(self, key: str, old_value: float, new_value: float):
        delta = new_value - old_value
        for (vec_a, vec_b), correlation in self._correlations.items():
            if vec_a == key and vec_b in self.vectors:
                related_key = vec_b
                related_delta = delta * correlation
                self.vectors[related_key] += related_delta * 0.5
                boundary_min = self.boundaries.get(f"min_{related_key}", 0.0)
                boundary_max = self.boundaries.get(f"max_{related_key}", 1.0)
                self.vectors[related_key] = round(max(boundary_min, min(boundary_max, self.vectors[related_key])), 2)

    def _record_vector_history(self):
        import time

        snapshot = {
            "timestamp": time.time(),
            "vectors": self.vectors.copy(),
            "form": self.current_form,
        }
        self.vector_history.append(snapshot)
        if len(self.vector_history) > 20:
            self.vector_history = self.vector_history[-20:]

    def get_profile(self) -> Dict:
        adjusted_vectors = {}
        for key in self.vectors:
            adjusted_vectors[key] = self.get_vector(key)

        # 如果 adjusted_vectors 为空，使用默认值
        if not adjusted_vectors:
            adjusted_vectors = {
                "logic": 0.75,
                "memory": 0.95,
                "warmth": 0.85,
                "empathy": 0.9,
                "resilience": 0.8,
                "creativity": 0.8,
            }

        return {
            "vectors": adjusted_vectors,
            "base_vectors": self.vectors.copy(),
            "dominant": max(adjusted_vectors, key=lambda k: adjusted_vectors[k]),
            "stability": self._calculate_stability(adjusted_vectors),
            "current_form": self.current_form,
            "form_info": self.get_current_form(),
            "current_core_form": self.current_core_form,
            "core_form_info": self.get_current_core_form(),
            "speak_mode": self.speak_mode,
            "current_title": self.current_title,
            "core_beliefs": self.core_beliefs,
        }

    def _calculate_stability(self, vectors: Optional[Dict] = None) -> float:
        if vectors is None:
            vectors = {key: self.get_vector(key) for key in self.vectors}

        # 如果 vectors 为空，返回默认稳定性
        if not vectors:
            return 0.8

        values = list(vectors.values())
        # 使用纯Python计算方差，避免numpy依赖
        mean = sum(values) / len(values) if values else 0
        variance = sum((x - mean) ** 2 for x in values) / len(values) if values else 0
        variance_stability = 1.0 - variance
        correlation_stability = self._calculate_correlation_stability(vectors)
        temporal_stability = self._calculate_temporal_stability()
        total = variance_stability * 0.4 + correlation_stability * 0.3 + temporal_stability * 0.3
        return float(round(total, 2))

    def _calculate_correlation_stability(self, vectors: Dict) -> float:
        correlation_scores = []
        if not self._correlations:
            return 1.0
        for (vec_a, vec_b), expected_corr in self._correlations.items():
            if vec_a in vectors and vec_b in vectors:
                val_a = vectors[vec_a]
                val_b = vectors[vec_b]
                score = 1.0 - abs(val_a - val_b) / 2 if expected_corr > 0 else 1.0 - abs(val_a - 0.5 + (val_b - 0.5))
                correlation_scores.append(score)
        if not correlation_scores:
            return 1.0
        return round(sum(correlation_scores) / len(correlation_scores), 2)

    def _calculate_temporal_stability(self) -> float:
        if len(self.vector_history) < 2:
            return 1.0
        total_variance = 0.0
        comparison_count = 0
        recent_history = self.vector_history[-5:]
        for i in range(1, len(recent_history)):
            prev = recent_history[i - 1]["vectors"]
            curr = recent_history[i]["vectors"]
            for key in prev:
                if key in curr:
                    diff = abs(prev[key] - curr[key])
                    total_variance += diff
                    comparison_count += 1
        if comparison_count == 0:
            return 1.0
        avg_variance = total_variance / comparison_count
        stability = 1.0 - min(avg_variance, 1.0)
        return round(stability, 2)

    def get_personality_description(self) -> str:
        profile = self.get_profile()
        vectors = profile["vectors"]
        form_info = profile["form_info"]
        core_form_info = profile.get("core_form_info")

        base_config = {}
        if self._use_yaml and self._loader:
            base_config = self._loader._load_base_config()

        core_traits = base_config.get("core_traits", {})
        god_names = base_config.get("god_names", {})
        god_traits = base_config.get("god_traits", {})

        lines = [
            f"【当前状态：{form_info.get('name', 'normal')}】",
            f"{form_info.get('full_name', '')} - {form_info.get('description', '')}",
            "",
            "【人格向量】",
        ]
        for key, value in vectors.items():
            desc = god_traits.get(key, core_traits.get(key, {}).get("description", ""))
            lines.append(f"- {god_names.get(key, key)}: {value:.2f} - {desc}")

        if core_form_info:
            lines.extend(
                [
                    "",
                    f"【当前激活核心形态：{core_form_info.get('name', '')}】",
                    f"{core_form_info.get('full_name', '')} - {core_form_info.get('description', '')}",
                ]
            )

        return "\n".join(lines)

    def export_to_json(self, json_path: Optional[Path] = None) -> Dict:
        config = {
            "vectors": self.vectors,
            "current_form": self.current_form,
            "current_title": self.current_title,
            "core_beliefs": self.core_beliefs,
        }
        if self._use_yaml and self._loader:
            config["available_forms"] = self._loader.list_available()
        if json_path:
            with open(json_path, "w", encoding=Encoding.UTF8) as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        return config

    def import_from_json(self, json_path: Path) -> bool:
        try:
            with open(json_path, "r", encoding=Encoding.UTF8) as f:
                config = json.load(f)
            if "vectors" in config:
                self.vectors = config["vectors"]
            if "current_form" in config:
                self.current_form = config["current_form"]
            if "current_title" in config:
                self.current_title = config["current_title"]
            if "core_beliefs" in config:
                self.core_beliefs = config["core_beliefs"]
            return True
        except Exception as e:
            print(f"错误：从JSON导入人格配置失败：{e}")
            return False

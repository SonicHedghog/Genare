import json
import os
from typing import Any


def default_settings() -> dict[str, Any]:
    return {
        "voice_quality": "Balanced",
        "read_output_aloud": True,
        "whisper_language": "en",
        "speech_hints": "Genare, Windsurf, Ollama, coding, Python",
        "ambient_duration": 0.8,
        "listen_timeout": 6.0,
        "silence_stop_seconds": 0.9,
        "terminal_workdir": os.getcwd(),
        "terminal_timeout_seconds": 120,
        "max_context_messages": 18,
        "max_context_tokens": 12000,
        "whisper_model": "base",
        "whisper_fallback_model": "small",
        "max_attachment_text_bytes": 120000,
        "max_path_preview_lines": 200,
        "max_image_attachment_bytes": 8000000,
        "tts_rate": 155,
        "tts_voice": "female-natural",
        "tts_backend": "windows-sapi" if os.name == "nt" else "pyttsx3",
        "work_check_interval_minutes": 0,
    }


def load_settings(config_path: str) -> dict[str, Any]:
    settings = default_settings()
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                settings.update(data)
    except Exception:
        # Fall back to defaults if config cannot be loaded.
        pass
    return settings


def get_env_or_setting(
    settings: dict[str, Any],
    env_name: str,
    setting_key: str,
    default: Any,
    caster: type,
) -> Any:
    raw = os.getenv(env_name)
    value = raw if raw is not None else settings.get(setting_key, default)
    try:
        if caster is bool:
            if isinstance(value, bool):
                return value
            value_text = str(value).strip().lower()
            return value_text in ("1", "true", "yes", "on")
        return caster(value)
    except Exception:
        return default

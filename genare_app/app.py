import os
import queue
import re
import threading
from pathlib import Path
from typing import Any, cast

import pyttsx3
import speech_recognition as sr
import tkinter as tk
from openai import OpenAI

from .mixins.ai import AIMixin
from .mixins.audio import AudioMixin
from .mixins.conversation import ConversationMixin
from .mixins.notifications import NotificationMixin
from .mixins.terminal import TerminalMixin
from .mixins.ui import UIMixin
from .settings import get_env_or_setting, load_settings


class GenareApp(UIMixin, ConversationMixin, TerminalMixin, AudioMixin, AIMixin, NotificationMixin):
    def __init__(self, root, base_url, api_key="sk-no-key-needed", model="gpt-4o-mini"):
        self.root = root
        self.tk = tk
        self.root.title("Genare Assistant")
        self.root.geometry("760x820")
        self.root.minsize(640, 700)
        self.root.configure(bg="#f2f4f8")

        # AI Setup
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.config_path = os.getenv("GENARE_CONFIG_PATH", os.path.join(os.getcwd(), "genare_config.json"))
        self.settings = load_settings(self.config_path)
        self.system_prompt = {
            "role": "system",
            "content": (
                "You are a helpful assistant. Keep conversational responses concise. "
                "If the user asks to start a coding task, reply starting with the exact phrase: "
                "'WINDSURF_LAUNCH|/path/to/dir|Task description'. "
                "If a terminal command is needed, provide one line in this exact format: "
                "'TERMINAL_COMMAND|the command to run'. "
                "To read files, list folders, or search files, you may request one line using: "
                "'FILE_READ|path', 'FILE_LIST|path', or 'FILE_SEARCH|query'. "
                "Do not suggest destructive commands such as deleting system files, formatting disks, "
                "or shutting down/restarting the machine."
            ),
        }
        self.messages = [cast(Any, self.system_prompt)]

        # Audio Setup
        self.pyttsx3 = pyttsx3
        self.sr = sr
        self.tts_rate = int(self.get_env_or_setting("GENARE_TTS_RATE", "tts_rate", 155, int))
        self.tts_voice = str(
            self.get_env_or_setting(
                "GENARE_TTS_VOICE",
                "tts_voice",
                "female-natural",
                str,
            )
        )
        self.tts_backend = str(
            self.get_env_or_setting(
                "GENARE_TTS_BACKEND",
                "tts_backend",
                "windows-sapi" if os.name == "nt" else "pyttsx3",
                str,
            )
        )
        self.tts_queue = queue.Queue()
        self.tts_shutdown = threading.Event()
        self.tts_worker = threading.Thread(target=self.tts_worker_loop, daemon=True)
        self.tts_worker.start()
        self.recognizer = sr.Recognizer()
        self.whisper_model = str(self.get_env_or_setting("GENARE_WHISPER_MODEL", "whisper_model", "base", str))
        self.whisper_fallback_model = str(self.get_env_or_setting("GENARE_WHISPER_FALLBACK_MODEL", "whisper_fallback_model", "small", str))
        self.whisper_language = str(self.get_env_or_setting("GENARE_WHISPER_LANGUAGE", "whisper_language", "en", str))
        self.speech_hints = str(self.get_env_or_setting("GENARE_SPEECH_HINTS", "speech_hints", "Genare, Windsurf, Ollama, coding, Python", str))
        self.ambient_duration = float(self.get_env_or_setting("GENARE_AMBIENT_CALIBRATION_SECONDS", "ambient_duration", 0.8, float))
        self.listen_timeout = float(self.get_env_or_setting("GENARE_LISTEN_TIMEOUT", "listen_timeout", 6.0, float))
        self.silence_stop_seconds = float(self.get_env_or_setting("GENARE_SILENCE_STOP_SECONDS", "silence_stop_seconds", 0.9, float))
        self.voice_quality_var = tk.StringVar(value=str(self.get_env_or_setting("GENARE_VOICE_QUALITY", "voice_quality", "Balanced", str)))
        self.voice_profiles = {
            "Fast": {
                "model": "tiny",
                "fallback": "base",
                "ambient": 0.45,
                "timeout": 5.0,
                "silence": 0.75,
            },
            "Balanced": {
                "model": "base",
                "fallback": "small",
                "ambient": 0.8,
                "timeout": 6.0,
                "silence": 0.9,
            },
            "Accurate": {
                "model": "small",
                "fallback": "medium",
                "ambient": 1.0,
                "timeout": 7.0,
                "silence": 1.1,
            },
        }
        self.apply_voice_profile(self.voice_quality_var.get(), announce=False)
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = self.silence_stop_seconds
        self.recognizer.non_speaking_duration = 0.5
        self.recognizer.phrase_threshold = 0.25
        self.max_context_messages = int(self.get_env_or_setting("GENARE_MAX_CONTEXT_MESSAGES", "max_context_messages", 18, int))
        self.max_context_tokens = int(self.get_env_or_setting("GENARE_MAX_CONTEXT_TOKENS", "max_context_tokens", 12000, int))
        self.terminal_workdir = str(self.get_env_or_setting("GENARE_TERMINAL_WORKDIR", "terminal_workdir", os.getcwd(), str))
        self.terminal_timeout_seconds = int(self.get_env_or_setting("GENARE_TERMINAL_TIMEOUT_SECONDS", "terminal_timeout_seconds", 120, int))
        self.workspace_root = Path.cwd()
        self.blocked_command_patterns = [
            (re.compile(r"(^|\s)rm\s+-rf(\s|$)", re.IGNORECASE), "Dangerous delete pattern (rm -rf) is blocked."),
            (re.compile(r"(^|\s)del\s+/[a-zA-Z]*[fqs][a-zA-Z]*(\s|$)", re.IGNORECASE), "Forced recursive delete commands are blocked."),
            (re.compile(r"(^|\s)rmdir\s+/[a-zA-Z]*s[a-zA-Z]*(\s|$)", re.IGNORECASE), "Recursive directory removal is blocked."),
            (re.compile(r"(^|\s)format(\s|$)", re.IGNORECASE), "Disk format commands are blocked."),
            (re.compile(r"(^|\s)(shutdown|restart-computer|stop-computer)(\s|$)", re.IGNORECASE), "Shutdown/restart commands are blocked."),
            (re.compile(r"(^|\s)(diskpart|bcdedit|cipher\s+/w)(\s|$)", re.IGNORECASE), "High-risk system commands are blocked."),
        ]

        # UI State Variables
        self.read_output_var = tk.BooleanVar(value=self.get_env_or_setting("GENARE_READ_OUTPUT_ALOUD", "read_output_aloud", True, bool))
        self.status_var = tk.StringVar(value="Ready")
        self.is_listening = False
        self.is_processing = False
        self.pending_attachments = []
        self.max_attachment_text_bytes = int(self.get_env_or_setting("GENARE_MAX_ATTACHMENT_TEXT_BYTES", "max_attachment_text_bytes", 120000, int))
        self.max_path_preview_lines = int(self.get_env_or_setting("GENARE_MAX_PATH_PREVIEW_LINES", "max_path_preview_lines", 200, int))
        self.max_image_attachment_bytes = int(self.get_env_or_setting("GENARE_MAX_IMAGE_ATTACHMENT_BYTES", "max_image_attachment_bytes", 8_000_000, int))
        self.work_check_interval_minutes = int(
            self.get_env_or_setting(
                "GENARE_WORK_CHECK_INTERVAL_MINUTES",
                "work_check_interval_minutes",
                0,
                int,
            )
        )
        self.last_context_tokens = 0

        self.build_ui()
        self.initialize_work_check_notifications()

    def get_env_or_setting(self, env_name, setting_key, default, caster):
        return get_env_or_setting(self.settings, env_name, setting_key, default, caster)

    def collect_settings(self):
        return {
            "voice_quality": self.voice_quality_var.get(),
            "read_output_aloud": bool(self.read_output_var.get()),
            "whisper_language": self.whisper_language,
            "speech_hints": self.speech_hints,
            "ambient_duration": self.ambient_duration,
            "listen_timeout": self.listen_timeout,
            "silence_stop_seconds": self.silence_stop_seconds,
            "terminal_workdir": self.terminal_workdir,
            "terminal_timeout_seconds": self.terminal_timeout_seconds,
            "max_context_messages": self.max_context_messages,
            "max_context_tokens": self.max_context_tokens,
            "whisper_model": self.whisper_model,
            "whisper_fallback_model": self.whisper_fallback_model,
            "max_attachment_text_bytes": self.max_attachment_text_bytes,
            "max_path_preview_lines": self.max_path_preview_lines,
            "max_image_attachment_bytes": self.max_image_attachment_bytes,
            "tts_rate": self.tts_rate,
            "tts_voice": self.tts_voice,
            "tts_backend": self.tts_backend,
            "work_check_interval_minutes": self.work_check_interval_minutes,
        }

    def save_settings(self):
        try:
            settings = self.collect_settings()
            with open(self.config_path, "w", encoding="utf-8") as f:
                import json

                json.dump(settings, f, indent=2)
            self.update_chat("System", f"Settings saved to {self.config_path}")
            self.update_config_hint()
        except Exception as e:
            self.update_chat("System Error", f"Failed to save settings: {e}")

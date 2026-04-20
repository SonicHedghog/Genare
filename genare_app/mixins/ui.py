from datetime import datetime
import os
import tkinter as tk
from tkinter import messagebox, scrolledtext


class UIMixin:
    def safe_after(self, callback):
        try:
            self.root.after(0, callback)
        except RuntimeError:
            # Ignore updates after Tk main loop has already stopped.
            pass

    def build_ui(self):
        self.build_menu_bar()

        # Header
        header = tk.Frame(self.root, bg="#f2f4f8")
        header.pack(padx=16, pady=(16, 8), fill=tk.X)
        tk.Label(
            header,
            text="Genare",
            font=("Segoe UI Semibold", 20),
            bg="#f2f4f8",
            fg="#1d2733",
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Chat, voice input, and coding task handoff",
            font=("Segoe UI", 10),
            bg="#f2f4f8",
            fg="#5d6875",
        ).pack(anchor="w")

        status_row = tk.Frame(self.root, bg="#f2f4f8")
        status_row.pack(padx=16, pady=(0, 10), fill=tk.X)
        tk.Label(
            status_row,
            text="Status:",
            font=("Segoe UI", 9),
            bg="#f2f4f8",
            fg="#5d6875",
        ).pack(side=tk.LEFT)
        tk.Label(
            status_row,
            textvariable=self.status_var,
            font=("Segoe UI Semibold", 9),
            bg="#f2f4f8",
            fg="#1f6f50",
        ).pack(side=tk.LEFT, padx=(4, 0))
        tk.Label(
            status_row,
            text="Voice shortcuts: Ctrl+Shift+V/F8 listen, Esc stop speech",
            font=("Segoe UI", 9),
            bg="#f2f4f8",
            fg="#5d6875",
        ).pack(side=tk.RIGHT)

        context_row = tk.Frame(self.root, bg="#f2f4f8")
        context_row.pack(padx=16, pady=(0, 8), fill=tk.X)
        tk.Label(
            context_row,
            text="Context",
            font=("Segoe UI", 9),
            bg="#f2f4f8",
            fg="#5d6875",
        ).pack(side=tk.LEFT, padx=(0, 8))
        self.context_canvas = tk.Canvas(
            context_row,
            width=250,
            height=12,
            bg="#ffffff",
            highlightthickness=1,
            highlightbackground="#ccd6e3",
            bd=0,
        )
        self.context_canvas.pack(side=tk.LEFT, padx=(0, 8))
        self.context_fill = self.context_canvas.create_rectangle(0, 0, 0, 12, fill="#4a90e2", width=0)
        self.context_label_var = tk.StringVar(value="0 / 12000 tokens")
        tk.Label(
            context_row,
            textvariable=self.context_label_var,
            font=("Segoe UI", 9),
            bg="#f2f4f8",
            fg="#5d6875",
        ).pack(side=tk.LEFT)

        chat_shell = tk.Frame(self.root, bg="#ffffff", highlightthickness=1, highlightbackground="#dce2ea")
        chat_shell.pack(padx=16, pady=(0, 12), fill=tk.BOTH, expand=True)

        # Chat History Display
        self.chat_display = scrolledtext.ScrolledText(
            chat_shell,
            wrap=tk.WORD,
            state='disabled',
            font=("Segoe UI", 11),
            bg="#ffffff",
            fg="#1f2a36",
            padx=14,
            pady=12,
            borderwidth=0,
            highlightthickness=0,
            insertbackground="#1f2a36",
        )
        self.chat_display.pack(padx=2, pady=2, fill=tk.BOTH, expand=True)
        self.chat_display.tag_configure("sender_you", foreground="#0f5bb5", font=("Segoe UI Semibold", 10))
        self.chat_display.tag_configure("sender_ai", foreground="#6f2dbd", font=("Segoe UI Semibold", 10))
        self.chat_display.tag_configure("sender_system", foreground="#1f6f50", font=("Segoe UI Semibold", 10))
        self.chat_display.tag_configure("message", foreground="#1f2a36", font=("Segoe UI", 11))

        # Input Area Frame
        input_frame = tk.Frame(self.root, bg="#f2f4f8")
        input_frame.pack(padx=16, pady=(0, 10), fill=tk.X)

        self.msg_entry = tk.Entry(
            input_frame,
            font=("Segoe UI", 12),
            relief=tk.FLAT,
            bg="#ffffff",
            fg="#1f2a36",
            insertbackground="#1f2a36",
            highlightthickness=1,
            highlightbackground="#ccd6e3",
            highlightcolor="#8fb3d9",
        )
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=8)
        self.msg_entry.bind("<Return>", lambda event: self.handle_text_send())

        self.add_file_btn = tk.Button(
            input_frame,
            text="Add File",
            command=self.handle_add_file,
            bg="#e8f0fe",
            fg="#17467a",
            activebackground="#d6e6fd",
            activeforeground="#17467a",
            relief=tk.FLAT,
            padx=10,
            pady=8,
            font=("Segoe UI", 9),
            cursor="hand2",
        )
        self.add_file_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.paste_attachment_btn = tk.Button(
            input_frame,
            text="Paste",
            command=self.handle_paste_attachment,
            bg="#eef7f1",
            fg="#1f6f50",
            activebackground="#ddeee4",
            activeforeground="#1f6f50",
            relief=tk.FLAT,
            padx=10,
            pady=8,
            font=("Segoe UI", 9),
            cursor="hand2",
        )
        self.paste_attachment_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.send_btn = tk.Button(
            input_frame,
            text="Send",
            command=self.handle_text_send,
            bg="#0f5bb5",
            fg="#ffffff",
            activebackground="#0d4f99",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=14,
            pady=8,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
        )
        self.send_btn.pack(side=tk.LEFT)

        attachment_row = tk.Frame(self.root, bg="#f2f4f8")
        attachment_row.pack(padx=16, pady=(0, 8), fill=tk.X)

        self.attachment_label = tk.Label(
            attachment_row,
            text="Attachments: none",
            font=("Segoe UI", 9),
            bg="#f2f4f8",
            fg="#5d6875",
            anchor="w",
        )
        self.attachment_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.clear_attachments_btn = tk.Button(
            attachment_row,
            text="Clear",
            command=self.clear_attachments,
            bg="#fceeed",
            fg="#7a2b23",
            activebackground="#f8ddd9",
            activeforeground="#7a2b23",
            relief=tk.FLAT,
            padx=8,
            pady=4,
            font=("Segoe UI", 8),
            cursor="hand2",
        )
        self.clear_attachments_btn.pack(side=tk.RIGHT)

        terminal_frame = tk.Frame(self.root, bg="#f2f4f8")
        terminal_frame.pack(padx=16, pady=(0, 10), fill=tk.X)

        tk.Label(
            terminal_frame,
            text="Terminal",
            font=("Segoe UI", 10),
            bg="#f2f4f8",
            fg="#37414e",
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.command_entry = tk.Entry(
            terminal_frame,
            font=("Consolas", 10),
            relief=tk.FLAT,
            bg="#ffffff",
            fg="#1f2a36",
            insertbackground="#1f2a36",
            highlightthickness=1,
            highlightbackground="#ccd6e3",
            highlightcolor="#8fb3d9",
        )
        self.command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=6)
        self.command_entry.bind("<Return>", lambda event: self.handle_manual_command_run())

        self.run_command_btn = tk.Button(
            terminal_frame,
            text="Run",
            command=self.handle_manual_command_run,
            bg="#36485c",
            fg="#ffffff",
            activebackground="#2e3d4f",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            font=("Segoe UI Semibold", 9),
            cursor="hand2",
        )
        self.run_command_btn.pack(side=tk.LEFT)

        # Controls Frame (Voice, TTS Toggle, Compact)
        control_frame = tk.Frame(self.root, bg="#f2f4f8")
        control_frame.pack(padx=16, pady=(0, 16), fill=tk.X)

        self.listen_btn = tk.Button(
            control_frame,
            text="Voice Input",
            command=self.start_listening_thread,
            bg="#e7f1ff",
            fg="#17467a",
            activebackground="#d8e8ff",
            activeforeground="#17467a",
            relief=tk.FLAT,
            padx=12,
            pady=8,
            font=("Segoe UI", 10),
            cursor="hand2",
        )
        self.listen_btn.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(
            control_frame,
            text="Voice quality",
            bg="#f2f4f8",
            fg="#37414e",
            font=("Segoe UI", 10),
        ).pack(side=tk.LEFT, padx=(0, 6))

        self.voice_quality_menu = tk.OptionMenu(
            control_frame,
            self.voice_quality_var,
            "Fast",
            "Balanced",
            "Accurate",
            command=self.on_voice_quality_change,
        )
        self.voice_quality_menu.config(
            bg="#ffffff",
            fg="#1f2a36",
            activebackground="#e7f1ff",
            activeforeground="#1f2a36",
            highlightthickness=1,
            highlightbackground="#ccd6e3",
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=6,
        )
        self.voice_quality_menu["menu"].config(
            bg="#ffffff",
            fg="#1f2a36",
            activebackground="#e7f1ff",
            activeforeground="#1f2a36",
            font=("Segoe UI", 9),
        )
        self.voice_quality_menu.pack(side=tk.LEFT, padx=(0, 10))

        self.tts_checkbox = tk.Checkbutton(
            control_frame,
            text="Read output aloud",
            variable=self.read_output_var,
            command=self.on_read_output_toggle,
            bg="#f2f4f8",
            fg="#37414e",
            activebackground="#f2f4f8",
            activeforeground="#37414e",
            selectcolor="#f2f4f8",
            font=("Segoe UI", 10),
        )
        self.tts_checkbox.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_speaking_btn = tk.Button(
            control_frame,
            text="Stop Speaking (Esc)",
            command=self.on_stop_speaking,
            bg="#ffeceb",
            fg="#8a2d2b",
            activebackground="#ffd9d7",
            activeforeground="#8a2d2b",
            relief=tk.FLAT,
            padx=10,
            pady=8,
            font=("Segoe UI", 10),
            cursor="hand2",
        )
        self.stop_speaking_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.save_settings_btn = tk.Button(
            control_frame,
            text="Save Settings",
            command=self.save_settings,
            bg="#e8f8ef",
            fg="#1f6f50",
            activebackground="#d4f2e2",
            activeforeground="#1f6f50",
            relief=tk.FLAT,
            padx=10,
            pady=8,
            font=("Segoe UI", 10),
            cursor="hand2",
        )
        self.save_settings_btn.pack(side=tk.RIGHT, padx=(0, 8))

        self.audio_settings_btn = tk.Button(
            control_frame,
            text="Audio",
            command=self.open_audio_settings_dialog,
            bg="#eaf6ff",
            fg="#17467a",
            activebackground="#d9ecfb",
            activeforeground="#17467a",
            relief=tk.FLAT,
            padx=10,
            pady=8,
            font=("Segoe UI", 10),
            cursor="hand2",
        )
        self.audio_settings_btn.pack(side=tk.RIGHT, padx=(0, 8))

        self.settings_btn = tk.Button(
            control_frame,
            text="Settings",
            command=self.open_settings_dialog,
            bg="#eceef8",
            fg="#2d3a62",
            activebackground="#dde2f4",
            activeforeground="#2d3a62",
            relief=tk.FLAT,
            padx=10,
            pady=8,
            font=("Segoe UI", 10),
            cursor="hand2",
        )
        self.settings_btn.pack(side=tk.RIGHT, padx=(0, 8))

        self.compact_btn = tk.Button(
            control_frame,
            text="Compact Session",
            command=self.start_compaction_thread,
            bg="#fff3dc",
            fg="#7b5510",
            activebackground="#ffe7bc",
            activeforeground="#7b5510",
            relief=tk.FLAT,
            padx=12,
            pady=8,
            font=("Segoe UI", 10),
            cursor="hand2",
        )
        self.compact_btn.pack(side=tk.RIGHT)

        self.update_chat(
            "System",
            (
                "Online and ready. Type a message or click 'Voice Input'. "
                "Voice shortcuts: Ctrl+Shift+V or F8 to listen, Esc to stop speaking. "
                "Use Add File/Paste to attach files. "
                "Terminal commands are always shown and require approval before execution."
            ),
        )

        self.update_config_hint()

        # Keyboard shortcuts for voice controls.
        self.root.bind_all("<Control-Shift-V>", self.on_voice_shortcut)
        self.root.bind_all("<F8>", self.on_voice_shortcut)
        self.root.bind_all("<Escape>", self.on_stop_speaking_shortcut)
        self.root.bind_all("<Control-comma>", self.on_audio_shortcut)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_context_meter(0)

    def build_menu_bar(self):
        menu_bar = tk.Menu(self.root)

        settings_menu = tk.Menu(menu_bar, tearoff=0)
        settings_menu.add_command(label="Audio Settings...", command=self.open_audio_settings_dialog)
        settings_menu.add_command(label="General Settings...", command=self.open_settings_dialog)
        settings_menu.add_separator()
        settings_menu.add_command(label="Save Settings", command=self.save_settings)
        settings_menu.add_separator()
        settings_menu.add_command(label="Exit", command=self.on_close)

        menu_bar.add_cascade(label="Settings", menu=settings_menu)
        self.root.config(menu=menu_bar)

    def update_config_hint(self):
        self.set_status(f"Ready | Config: {self.config_path}")

    def open_settings_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Genare Settings")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg="#f2f4f8")
        dialog.geometry("620x430")

        fields = [
            ("Whisper Language", "whisper_language", self.whisper_language),
            ("Speech Hints", "speech_hints", self.speech_hints),
            ("Terminal Working Dir", "terminal_workdir", self.terminal_workdir),
            ("Terminal Timeout (sec)", "terminal_timeout_seconds", str(self.terminal_timeout_seconds)),
            ("Work Check Reminder (minutes, 0=off)", "work_check_interval_minutes", str(self.work_check_interval_minutes)),
            ("Max Context Messages", "max_context_messages", str(self.max_context_messages)),
            ("Max Context Tokens", "max_context_tokens", str(self.max_context_tokens)),
            ("Silence Stop Seconds", "silence_stop_seconds", str(self.silence_stop_seconds)),
            ("Max Attachment Text Bytes", "max_attachment_text_bytes", str(self.max_attachment_text_bytes)),
            ("Max Path Preview Lines", "max_path_preview_lines", str(self.max_path_preview_lines)),
            ("Max Image Attachment Bytes", "max_image_attachment_bytes", str(self.max_image_attachment_bytes)),
        ]

        entries: dict[str, tk.Entry] = {}
        for idx, (label, key, value) in enumerate(fields):
            tk.Label(
                dialog,
                text=label,
                bg="#f2f4f8",
                fg="#37414e",
                font=("Segoe UI", 10),
                anchor="w",
            ).grid(row=idx, column=0, sticky="w", padx=14, pady=(10 if idx == 0 else 6, 0))
            entry = tk.Entry(dialog, font=("Segoe UI", 10), width=55)
            entry.grid(row=idx, column=1, padx=8, pady=(10 if idx == 0 else 6, 0), sticky="ew")
            entry.insert(0, value)
            entries[key] = entry

        dialog.columnconfigure(1, weight=1)

        def save_from_dialog():
            try:
                self.whisper_language = entries["whisper_language"].get().strip() or "en"
                self.speech_hints = entries["speech_hints"].get().strip() or self.speech_hints
                self.terminal_workdir = entries["terminal_workdir"].get().strip() or os.getcwd()
                self.terminal_timeout_seconds = max(5, int(entries["terminal_timeout_seconds"].get().strip() or "120"))
                work_check_interval_minutes = max(0, int(entries["work_check_interval_minutes"].get().strip() or "0"))
                self.max_context_messages = max(4, int(entries["max_context_messages"].get().strip() or "18"))
                self.max_context_tokens = max(1000, int(entries["max_context_tokens"].get().strip() or "12000"))
                self.silence_stop_seconds = max(0.3, float(entries["silence_stop_seconds"].get().strip() or "0.9"))
                self.max_attachment_text_bytes = max(2000, int(entries["max_attachment_text_bytes"].get().strip() or "120000"))
                self.max_path_preview_lines = max(20, int(entries["max_path_preview_lines"].get().strip() or "200"))
                self.max_image_attachment_bytes = max(100000, int(entries["max_image_attachment_bytes"].get().strip() or "8000000"))
                self.set_work_check_interval_minutes(work_check_interval_minutes, announce=True)
                self.recognizer.pause_threshold = self.silence_stop_seconds
                self.save_settings()
                self.update_context_meter(self.last_context_tokens)
                self.update_chat("System", "Settings updated from dialog.")
                dialog.destroy()
            except ValueError as e:
                messagebox.showerror("Invalid Settings", f"Please fix invalid values.\n{e}", parent=dialog)

        action_row = tk.Frame(dialog, bg="#f2f4f8")
        action_row.grid(row=len(fields), column=0, columnspan=2, sticky="e", padx=14, pady=14)
        tk.Button(
            action_row,
            text="Cancel",
            command=dialog.destroy,
            bg="#f4f4f4",
            fg="#333333",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            font=("Segoe UI", 10),
        ).pack(side=tk.RIGHT, padx=(8, 0))
        tk.Button(
            action_row,
            text="Save",
            command=save_from_dialog,
            bg="#0f5bb5",
            fg="#ffffff",
            activebackground="#0d4f99",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            font=("Segoe UI Semibold", 10),
        ).pack(side=tk.RIGHT)

    def open_audio_settings_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Audio Settings")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg="#f2f4f8")
        dialog.geometry("460x250")

        read_aloud_var = tk.BooleanVar(value=bool(self.read_output_var.get()))
        voice_quality_var = tk.StringVar(value=self.voice_quality_var.get())
        tts_rate_var = tk.StringVar(value=str(self.tts_rate))
        tts_voice_var = tk.StringVar(value=str(getattr(self, "tts_voice", "female-natural")))
        tts_backend_var = tk.StringVar(value=self.tts_backend)

        tk.Label(
            dialog,
            text="Audio Settings",
            bg="#f2f4f8",
            fg="#1d2733",
            font=("Segoe UI Semibold", 14),
        ).pack(anchor="w", padx=14, pady=(14, 8))

        tk.Checkbutton(
            dialog,
            text="Read AI replies aloud",
            variable=read_aloud_var,
            bg="#f2f4f8",
            fg="#37414e",
            activebackground="#f2f4f8",
            activeforeground="#37414e",
            selectcolor="#f2f4f8",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=14, pady=(2, 8))

        quality_row = tk.Frame(dialog, bg="#f2f4f8")
        quality_row.pack(fill=tk.X, padx=14, pady=(2, 8))
        tk.Label(quality_row, text="Voice quality", bg="#f2f4f8", fg="#37414e", font=("Segoe UI", 10)).pack(side=tk.LEFT)
        tk.OptionMenu(quality_row, voice_quality_var, "Fast", "Balanced", "Accurate").pack(side=tk.LEFT, padx=(8, 0))

        rate_row = tk.Frame(dialog, bg="#f2f4f8")
        rate_row.pack(fill=tk.X, padx=14, pady=(2, 8))
        tk.Label(rate_row, text="TTS rate", bg="#f2f4f8", fg="#37414e", font=("Segoe UI", 10)).pack(side=tk.LEFT)
        tk.Entry(rate_row, textvariable=tts_rate_var, width=8, font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(8, 0))

        voice_row = tk.Frame(dialog, bg="#f2f4f8")
        voice_row.pack(fill=tk.X, padx=14, pady=(2, 8))
        tk.Label(voice_row, text="TTS voice", bg="#f2f4f8", fg="#37414e", font=("Segoe UI", 10)).pack(side=tk.LEFT)
        tk.OptionMenu(voice_row, tts_voice_var, "female-natural", "female", "male").pack(side=tk.LEFT, padx=(8, 0))

        backend_row = tk.Frame(dialog, bg="#f2f4f8")
        backend_row.pack(fill=tk.X, padx=14, pady=(2, 8))
        tk.Label(backend_row, text="TTS backend", bg="#f2f4f8", fg="#37414e", font=("Segoe UI", 10)).pack(side=tk.LEFT)
        tk.OptionMenu(backend_row, tts_backend_var, "windows-sapi", "pyttsx3").pack(side=tk.LEFT, padx=(8, 0))

        action_row = tk.Frame(dialog, bg="#f2f4f8")
        action_row.pack(fill=tk.X, padx=14, pady=(12, 10))

        def save_audio():
            try:
                self.read_output_var.set(bool(read_aloud_var.get()))
                new_quality = voice_quality_var.get().strip() or "Balanced"
                if new_quality != self.voice_quality_var.get():
                    self.voice_quality_var.set(new_quality)
                    self.apply_voice_profile(new_quality, announce=False)
                self.tts_rate = max(80, min(320, int(tts_rate_var.get().strip() or "170")))
                self.tts_voice = tts_voice_var.get().strip().lower() or "female-natural"
                self.tts_backend = (tts_backend_var.get().strip() or self.tts_backend).lower()
                self.save_settings()
                self.update_chat("System", "Audio settings updated.")
                dialog.destroy()
            except ValueError as e:
                messagebox.showerror("Invalid Audio Settings", f"Please check values.\n{e}", parent=dialog)

        tk.Button(
            action_row,
            text="Cancel",
            command=dialog.destroy,
            bg="#f4f4f4",
            fg="#333333",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            font=("Segoe UI", 10),
        ).pack(side=tk.RIGHT, padx=(8, 0))
        tk.Button(
            action_row,
            text="Save",
            command=save_audio,
            bg="#0f5bb5",
            fg="#ffffff",
            activebackground="#0d4f99",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            font=("Segoe UI Semibold", 10),
        ).pack(side=tk.RIGHT)

    def on_close(self):
        self.cancel_work_check_notifications()
        self.stop_tts_playback(shutdown=True)
        if hasattr(self, "tts_worker") and self.tts_worker.is_alive():
            self.tts_worker.join(timeout=1.0)
        self.save_settings()
        self.root.destroy()

    def apply_voice_profile(self, profile_name, announce=True):
        profile = self.voice_profiles.get(profile_name, self.voice_profiles["Balanced"])
        self.whisper_model = profile["model"]
        self.whisper_fallback_model = profile["fallback"]
        self.ambient_duration = profile["ambient"]
        self.listen_timeout = profile["timeout"]
        self.silence_stop_seconds = profile["silence"]
        self.recognizer.pause_threshold = self.silence_stop_seconds
        if announce:
            self.update_chat(
                "System",
                (
                    f"Voice quality set to {profile_name} "
                    f"(model: {self.whisper_model}, fallback: {self.whisper_fallback_model}, "
                    f"stop on silence: {self.silence_stop_seconds:.2f}s)."
                ),
            )
            self.save_settings()

    def on_voice_quality_change(self, selected):
        self.apply_voice_profile(selected, announce=True)

    def on_read_output_toggle(self):
        self.save_settings()

    def on_stop_speaking(self):
        self.stop_tts_playback(shutdown=False)
        self.update_chat("System", "Speech stopped.")

    def on_stop_speaking_shortcut(self, event):
        self.on_stop_speaking()
        return "break"

    def on_voice_shortcut(self, event):
        self.start_listening_thread()
        return "break"

    def on_audio_shortcut(self, event):
        self.open_audio_settings_dialog()
        return "break"

    def update_chat(self, sender, message):
        """Safely updates the chat window from any thread."""

        def update():
            self.chat_display.config(state='normal')
            timestamp = datetime.now().strftime("%H:%M")
            sender_tag = "sender_ai"
            if sender.lower().startswith("you"):
                sender_tag = "sender_you"
            elif sender.lower().startswith("system"):
                sender_tag = "sender_system"
            self.chat_display.insert(tk.END, f"[{timestamp}] {sender}: ", sender_tag)
            self.chat_display.insert(tk.END, f"{message}\n\n", "message")
            self.chat_display.config(state='disabled')
            self.chat_display.yview(tk.END)

        self.safe_after(update)

    def set_status(self, text):
        self.safe_after(lambda t=text: self.status_var.set(t))

    def estimate_content_tokens(self, content):
        if isinstance(content, str):
            return max(1, len(content) // 4)
        if isinstance(content, list):
            total = 0
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    total += max(1, len(str(part.get("text", ""))) // 4)
                elif part.get("type") == "image_url":
                    total += 350
            return max(1, total)
        return 1

    def estimate_message_tokens(self, message):
        return 4 + self.estimate_content_tokens(message.get("content", ""))

    def update_context_meter(self, used_tokens):
        max_tokens = max(1, self.max_context_tokens)
        ratio = max(0.0, min(1.0, used_tokens / max_tokens))
        width = int(250 * ratio)

        def apply():
            self.context_canvas.coords(self.context_fill, 0, 0, width, 12)
            fill_color = "#4a90e2"
            if ratio >= 0.85:
                fill_color = "#c73a31"
            elif ratio >= 0.65:
                fill_color = "#d28a1d"
            self.context_canvas.itemconfig(self.context_fill, fill=fill_color)
            self.context_label_var.set(f"{used_tokens} / {max_tokens} tokens")

        self.safe_after(apply)

    def set_processing_state(self, processing):
        self.is_processing = processing

        def apply_state():
            entry_state = 'disabled' if processing else 'normal'
            button_state = 'disabled' if processing else 'normal'
            self.msg_entry.config(state=entry_state)
            self.send_btn.config(state=button_state)
            self.add_file_btn.config(state=button_state)
            self.paste_attachment_btn.config(state=button_state)
            self.command_entry.config(state=entry_state)
            self.run_command_btn.config(state=button_state)
            self.clear_attachments_btn.config(state=button_state)
            self.audio_settings_btn.config(state=button_state)
            if not self.is_listening:
                self.listen_btn.config(state=button_state)
            if not processing:
                self.msg_entry.focus_set()

        self.safe_after(apply_state)

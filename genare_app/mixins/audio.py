import os
import queue
import re
import subprocess
import threading


class AudioMixin:
    def ensure_tts_runtime_state(self):
        if not hasattr(self, "tts_state_lock"):
            self.tts_state_lock = threading.Lock()
        if not hasattr(self, "tts_process"):
            self.tts_process = None
        if not hasattr(self, "tts_engine"):
            self.tts_engine = None

    def stop_tts_playback(self, shutdown=False):
        self.ensure_tts_runtime_state()
        if shutdown:
            self.tts_shutdown.set()

        try:
            while True:
                self.tts_queue.get_nowait()
        except queue.Empty:
            pass

        # Unblock worker loop if it is waiting on the queue.
        if shutdown:
            self.tts_queue.put(None)

        with self.tts_state_lock:
            process = self.tts_process
            engine = self.tts_engine

        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=0.5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass

    def resolve_tts_voice_preference(self):
        return str(getattr(self, "tts_voice", "female-natural") or "female-natural").strip().lower()

    def choose_pyttsx3_voice_id(self, engine):
        preference = self.resolve_tts_voice_preference()
        voices = list(engine.getProperty("voices") or [])
        if not voices:
            return None

        # Honor explicit voice names before applying profile matching.
        if preference not in ("female", "female-natural", "male"):
            for voice in voices:
                name = str(getattr(voice, "name", "")).lower()
                if preference in name:
                    return getattr(voice, "id", None)

        female_hints = ("zira", "aria", "jenny", "susan", "hazel", "sara", "female", "woman", "girl")
        male_hints = ("david", "mark", "guy", "male", "man", "boy")

        if preference in ("female", "female-natural"):
            for voice in voices:
                name = str(getattr(voice, "name", "")).lower()
                if any(hint in name for hint in female_hints):
                    return getattr(voice, "id", None)

        if preference == "male":
            for voice in voices:
                name = str(getattr(voice, "name", "")).lower()
                if any(hint in name for hint in male_hints):
                    return getattr(voice, "id", None)

        return getattr(voices[0], "id", None)

    def speak_async(self, text):
        text = (text or "").strip()
        if not text or self.tts_shutdown.is_set():
            return
        self.tts_queue.put(text)

    def tts_worker_loop(self):
        while not self.tts_shutdown.is_set():
            item = self.tts_queue.get()
            if item is None or self.tts_shutdown.is_set():
                break
            try:
                self.speak_with_backend(str(item))
            except Exception as e:
                if not self.tts_shutdown.is_set():
                    self.update_chat("System", f"TTS error: {e}")

    def speak_with_backend(self, text):
        if self.tts_backend == "windows-sapi" and os.name == "nt":
            self.speak_with_windows_sapi(text)
            return
        self.speak_with_pyttsx3(text)

    def speak_with_pyttsx3(self, text):
        if self.tts_shutdown.is_set():
            return
        self.ensure_tts_runtime_state()
        engine = self.pyttsx3.init()
        try:
            with self.tts_state_lock:
                self.tts_engine = engine
            voice_id = self.choose_pyttsx3_voice_id(engine)
            if voice_id:
                engine.setProperty("voice", voice_id)
            engine.setProperty('rate', self.tts_rate)
            engine.say(text)
            engine.runAndWait()
        finally:
            with self.tts_state_lock:
                if self.tts_engine is engine:
                    self.tts_engine = None
            try:
                engine.stop()
            except Exception:
                pass

    def speak_with_windows_sapi(self, text):
        if self.tts_shutdown.is_set():
            return
        self.ensure_tts_runtime_state()
        escaped = text.replace("'", "''")
        voice_preference = self.resolve_tts_voice_preference().replace("'", "''")
        # Map app rate roughly from 80-320 to SAPI -10..10
        sapi_rate = int(round((self.tts_rate - 170) / 12))
        sapi_rate = max(-10, min(10, sapi_rate))
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$voices = @($s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }); "
            f"$pref = '{voice_preference}'; "
            "$selected = $null; "
            "if ($pref -and $pref -notin @('female', 'female-natural', 'male')) { "
            "  $selected = $voices | Where-Object { $_ -match [Regex]::Escape($pref) } | Select-Object -First 1; "
            "} "
            "if (-not $selected -and $pref -in @('female', 'female-natural')) { "
            "  $selected = $voices | Where-Object { $_ -match '(?i)zira|aria|jenny|susan|hazel|sara|female|woman|girl' } | Select-Object -First 1; "
            "} "
            "if (-not $selected -and $pref -eq 'male') { "
            "  $selected = $voices | Where-Object { $_ -match '(?i)david|mark|male|man|boy' } | Select-Object -First 1; "
            "} "
            "if (-not $selected) { $selected = $voices | Select-Object -First 1; } "
            "if ($selected) { $s.SelectVoice($selected); } "
            f"$s.Rate = {sapi_rate}; "
            f"$s.Speak('{escaped}');"
        )
        process = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        with self.tts_state_lock:
            self.tts_process = process

        try:
            process.communicate(timeout=max(30, self.terminal_timeout_seconds))
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except Exception:
                pass
            process.communicate()
        finally:
            with self.tts_state_lock:
                if self.tts_process is process:
                    self.tts_process = None

        if self.tts_shutdown.is_set():
            return

        if process.returncode != 0:
            # Fallback to pyttsx3 if SAPI invocation fails.
            self.speak_with_pyttsx3(text)

    def should_read_aloud(self, text):
        stripped = text.strip()
        if not stripped:
            return False
        blocked_prefixes = (
            "TERMINAL_COMMAND|",
            "TERMINAL_RUN|",
            "FILE_READ|",
            "FILE_LIST|",
            "FILE_SEARCH|",
            "FILE TOOL RESULTS:",
        )
        return not any(stripped.startswith(prefix) for prefix in blocked_prefixes)

    def clean_transcription(self, text):
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        cleaned = cleaned.replace(" ,", ",").replace(" .", ".")
        return cleaned

    def transcribe_with_whisper(self, audio, model_name):
        recognize_whisper = getattr(self.recognizer, "recognize_whisper", None)
        if not callable(recognize_whisper):
            raise RuntimeError(
                "Local Whisper transcription is unavailable. Install openai-whisper and ffmpeg."
            )
        kwargs = {
            "model": model_name,
            "language": self.whisper_language,
            "initial_prompt": self.speech_hints,
            "condition_on_previous_text": False,
            "temperature": 0.0,
        }
        try:
            result = recognize_whisper(audio, **kwargs)
        except TypeError:
            # Older SpeechRecognition wrappers support fewer kwargs.
            result = recognize_whisper(audio, model=model_name)
        return result if isinstance(result, str) else str(result or "")

    def transcribe_audio(self, audio):
        whisper_error = None
        for model_name in (self.whisper_model, self.whisper_fallback_model):
            if not model_name:
                continue
            try:
                transcript = self.clean_transcription(self.transcribe_with_whisper(audio, model_name))
                if transcript:
                    return transcript
            except Exception as exc:
                whisper_error = exc

        # Last-resort cloud fallback can recover in noisy cases where local transcription fails.
        try:
            recognize_google = getattr(self.recognizer, "recognize_google", None)
            if callable(recognize_google):
                transcript = self.clean_transcription(recognize_google(audio))
                if transcript:
                    return transcript
        except Exception:
            pass

        if whisper_error is not None:
            raise whisper_error
        raise RuntimeError("No speech detected. Try speaking closer to the microphone.")

    def start_listening_thread(self):
        if self.is_listening or self.is_processing:
            return
        self.is_listening = True
        self.set_status("Listening...")
        self.listen_btn.config(text="Listening...", bg="#ffe7d6", fg="#8a3d00", state='disabled')
        threading.Thread(target=self.listen_and_process, daemon=True).start()

    def listen_and_process(self):
        with self.sr.Microphone() as source:
            self.update_chat("System", "Adjusting for noise... speak now.")
            self.recognizer.adjust_for_ambient_noise(source, duration=self.ambient_duration)
            try:
                audio = self.recognizer.listen(
                    source,
                    timeout=self.listen_timeout,
                )
                self.update_chat("System", "Processing audio locally...")
                transcription = self.transcribe_audio(audio)

                if transcription.strip():
                    self.update_chat("System", f"Heard: {transcription}")
                    # Send recognized text to the chat pipeline
                    self.safe_after(lambda t=transcription: self.process_user_input(t))
                else:
                    self.update_chat("System", "I could not understand that. Please try again.")
            except Exception as e:
                self.update_chat("System", f"Listening stopped or failed: {e}")
            finally:
                self.is_listening = False
                self.set_status("Ready")
                self.safe_after(
                    lambda: self.listen_btn.config(
                        text="Voice Input",
                        bg="#e7f1ff",
                        fg="#17467a",
                        state='normal'
                    )
                )

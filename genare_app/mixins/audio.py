import os
import re
import subprocess
import threading


class AudioMixin:
    def speak_async(self, text):
        text = (text or "").strip()
        if not text:
            return
        self.tts_queue.put(text)

    def tts_worker_loop(self):
        while not self.tts_shutdown.is_set():
            item = self.tts_queue.get()
            if item is None:
                break
            try:
                self.speak_with_backend(str(item))
            except Exception as e:
                self.update_chat("System", f"TTS error: {e}")

    def speak_with_backend(self, text):
        if self.tts_backend == "windows-sapi" and os.name == "nt":
            self.speak_with_windows_sapi(text)
            return
        self.speak_with_pyttsx3(text)

    def speak_with_pyttsx3(self, text):
        engine = self.pyttsx3.init()
        try:
            engine.setProperty('rate', self.tts_rate)
            engine.say(text)
            engine.runAndWait()
        finally:
            try:
                engine.stop()
            except Exception:
                pass

    def speak_with_windows_sapi(self, text):
        escaped = text.replace("'", "''")
        # Map app rate roughly from 80-320 to SAPI -10..10
        sapi_rate = int(round((self.tts_rate - 170) / 12))
        sapi_rate = max(-10, min(10, sapi_rate))
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate = {sapi_rate}; "
            f"$s.Speak('{escaped}');"
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=max(30, self.terminal_timeout_seconds),
        )
        if completed.returncode != 0:
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

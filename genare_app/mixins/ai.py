import threading
from typing import Any, cast


class AIMixin:
    def fetch_ai_response(self):
        """Communicates with the AI in a background thread."""
        try:
            request_messages = self.build_context_window()
            try:
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=cast(Any, request_messages),
                    temperature=0.7,
                    stream=True,
                )
            except Exception as e:
                if self.has_inline_images():
                    fallback_messages = self.strip_images_from_messages(request_messages)
                    self.update_chat(
                        "System",
                        "Current model/backend rejected image inputs. Retrying with text-only fallback.",
                    )
                    stream = self.client.chat.completions.create(
                        model=self.model,
                        messages=cast(Any, fallback_messages),
                        temperature=0.7,
                        stream=True,
                    )
                else:
                    raise e

            chunks = []
            for chunk in stream:
                delta = ""
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta.content or ""
                if delta:
                    chunks.append(delta)

            ai_reply = "".join(chunks).strip()
            if not ai_reply:
                raise RuntimeError("Model returned an empty response.")

            file_actions = self.extract_file_actions(ai_reply)
            ai_reply_for_user = self.remove_file_action_lines(ai_reply)

            self.messages.append({"role": "assistant", "content": ai_reply_for_user or ai_reply})

            if file_actions:
                outputs = []
                for action, value in file_actions[:4]:
                    outputs.append(self.run_file_action(action, value))
                tool_result = "FILE TOOL RESULTS:\n" + "\n\n".join(outputs)
                self.messages.append({"role": "system", "content": tool_result})
                self.update_chat("System", "Executed file tools requested by AI. Generating refined answer...")
                followup_stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=cast(Any, self.build_context_window()),
                    temperature=0.4,
                    stream=True,
                )
                followup_chunks = []
                for chunk in followup_stream:
                    delta = ""
                    if chunk.choices and chunk.choices[0].delta:
                        delta = chunk.choices[0].delta.content or ""
                    if delta:
                        followup_chunks.append(delta)
                refined = "".join(followup_chunks).strip()
                if refined:
                    ai_reply_for_user = self.remove_file_action_lines(refined)
                    self.messages.append({"role": "assistant", "content": ai_reply_for_user})

            terminal_command = self.extract_terminal_command(ai_reply_for_user or ai_reply)
            display_reply = self.remove_terminal_command_lines(ai_reply_for_user or ai_reply)

            # Check for Windsurf trigger
            if "WINDSURF_LAUNCH|" in ai_reply:
                self.handle_windsurf_trigger(ai_reply)
            else:
                if display_reply:
                    self.update_chat("AI", display_reply)
                if self.read_output_var.get() and display_reply and self.should_read_aloud(display_reply):
                    self.speak_async(display_reply or ai_reply)

            if terminal_command:
                self.safe_after(lambda cmd=terminal_command: self.confirm_and_run_command(cmd, source="AI"))

        except Exception as e:
            self.update_chat("System Error", str(e))
        finally:
            self.set_processing_state(False)
            self.set_status("Ready")

    def handle_windsurf_trigger(self, ai_reply):
        try:
            trigger_line = [line for line in ai_reply.split('\n') if "WINDSURF_LAUNCH|" in line][0]
            parts = trigger_line.split('|', 2)
            if len(parts) < 3:
                raise ValueError("Launch command must be: WINDSURF_LAUNCH|/path|task")
            target_directory = parts[1].strip()
            task_description = parts[2].strip()

            self.update_chat("System", f"Triggered Windsurf:\nDir: {target_directory}\nTask: {task_description}")

            # TODO: Insert launch_windsurf_with_task(target_directory, task_description) here.
        except Exception as e:
            self.update_chat("System Error", f"Failed to parse launch command: {e}")

    def start_compaction_thread(self):
        if self.is_processing:
            return
        self.compact_btn.config(state='disabled')
        self.set_status("Compacting conversation...")
        self.update_chat("System", "Compacting session... please wait.")
        threading.Thread(target=self.compact_session, daemon=True).start()

    def compact_session(self):
        """Asks the AI to summarize the history, then truncates self.messages."""
        if len(self.messages) <= 3:
            self.update_chat("System", "Session is already short. No compaction needed.")
            self.set_status("Ready")
            self.safe_after(lambda: self.compact_btn.config(state='normal'))
            return

        compaction_prompt = {
            "role": "user",
            "content": "Please summarize our entire conversation history above into a single, concise paragraph. Focus on the tools we are discussing, the tasks we have completed, and any outstanding goals. This will serve as our new memory context.",
        }

        temp_messages = self.messages.copy()
        temp_messages.append(compaction_prompt)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=cast(Any, temp_messages),
                temperature=0.3,
            )
            summary = response.choices[0].message.content or ""

            # Rebuild the messages array with just the system prompt and the summary.
            self.messages = [
                self.system_prompt,
                {"role": "assistant", "content": f"Previous session context: {summary}"},
            ]

            self.update_chat("System", f"Session Compacted! New Context: {summary}")
        except Exception as e:
            self.update_chat("System Error", f"Compaction failed: {e}")
        finally:
            self.set_status("Ready")
            self.safe_after(lambda: self.compact_btn.config(state='normal'))

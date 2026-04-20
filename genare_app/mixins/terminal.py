import subprocess
import threading
from tkinter import messagebox


class TerminalMixin:
    def extract_terminal_command(self, text):
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("TERMINAL_COMMAND|"):
                return line.split("|", 1)[1].strip()
            if line.startswith("TERMINAL_RUN|"):
                return line.split("|", 1)[1].strip()
        return ""

    def remove_terminal_command_lines(self, text):
        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("TERMINAL_COMMAND|") or stripped.startswith("TERMINAL_RUN|"):
                continue
            lines.append(line)
        return "\n".join(lines).strip()

    def handle_manual_command_run(self):
        command = self.command_entry.get().strip()
        if not command or self.is_processing:
            return
        self.confirm_and_run_command(command, source="Manual")

    def confirm_and_run_command(self, command, source="AI"):
        command = command.strip().strip("`")
        if not command:
            return

        blocked_reason = self.get_blocked_command_reason(command)
        if blocked_reason:
            self.update_chat(
                "System",
                f"Blocked terminal command from {source}: {command}\nReason: {blocked_reason}",
            )
            return

        self.update_chat("System", f"{source} requested terminal command:\n{command}")
        approved = messagebox.askyesno(
            "Confirm Command Execution",
            f"{source} wants to run this command:\n\n{command}\n\nRun it?",
            parent=self.root,
        )
        if not approved:
            self.update_chat("System", "Command canceled by user.")
            return

        if source.lower() == "manual":
            self.command_entry.delete(0, "end")

        threading.Thread(
            target=self.run_terminal_command,
            args=(command,),
            daemon=True,
        ).start()

    def get_blocked_command_reason(self, command):
        lowered = command.strip().lower()
        if any(token in lowered for token in ("&&", "||", ";")):
            return "Command chaining is blocked. Run one command at a time."
        for pattern, reason in self.blocked_command_patterns:
            if pattern.search(command):
                return reason
        return ""

    def run_terminal_command(self, command):
        self.set_status("Running terminal command...")
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=self.terminal_workdir,
                capture_output=True,
                text=True,
                timeout=self.terminal_timeout_seconds,
            )
            stdout = (completed.stdout or "").strip()
            stderr = (completed.stderr or "").strip()
            combined_output = "\n".join(part for part in (stdout, stderr) if part)
            if not combined_output:
                combined_output = "[no output]"
            self.update_chat(
                "Terminal",
                f"$ {command}\nExit code: {completed.returncode}\n{combined_output}",
            )
        except subprocess.TimeoutExpired:
            self.update_chat(
                "Terminal",
                f"$ {command}\nTimed out after {self.terminal_timeout_seconds} seconds.",
            )
        except Exception as e:
            self.update_chat("System Error", f"Terminal command failed to start: {e}")
        finally:
            self.set_status("Ready")

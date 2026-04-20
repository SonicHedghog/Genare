import base64
import mimetypes
import re
import threading
from pathlib import Path
from typing import Any
from tkinter import filedialog


class ConversationMixin:
    def build_context_window(self):
        if not self.messages:
            self.last_context_tokens = 0
            self.update_context_meter(0)
            return []

        base = [self.messages[0], *self.messages[-(self.max_context_messages - 1):]]
        sys_msg = base[0]
        selected = []
        running = self.estimate_message_tokens(sys_msg)

        for message in reversed(base[1:]):
            msg_tokens = self.estimate_message_tokens(message)
            if selected and running + msg_tokens > self.max_context_tokens:
                continue
            selected.append(message)
            running += msg_tokens

        window = [sys_msg, *reversed(selected)]
        self.last_context_tokens = running
        self.update_context_meter(running)
        return window

    def handle_text_send(self):
        if self.is_processing:
            return
        user_text = self.msg_entry.get().strip()
        if not user_text:
            return
        self.msg_entry.delete(0, "end")
        self.process_user_input(user_text)

    def process_user_input(self, text):
        """Handles the user text, updates UI, and triggers the AI thread."""
        enriched_content = self.augment_message_with_context(text)
        self.update_chat("You", text)
        self.messages.append({"role": "user", "content": enriched_content})

        self.set_processing_state(True)
        self.set_status("Thinking...")
        threading.Thread(target=self.fetch_ai_response, daemon=True).start()

    def refresh_attachment_label(self):
        if not self.pending_attachments:
            self.attachment_label.config(text="Attachments: none")
            return
        names = [a["name"] for a in self.pending_attachments[:3]]
        suffix = "" if len(self.pending_attachments) <= 3 else f" +{len(self.pending_attachments) - 3} more"
        self.attachment_label.config(text=f"Attachments: {', '.join(names)}{suffix}")

    def clear_attachments(self):
        self.pending_attachments.clear()
        self.refresh_attachment_label()

    def read_text_file_safe(self, path: Path):
        if path.stat().st_size > self.max_attachment_text_bytes:
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                return path.read_text(encoding="latin-1")
            except Exception:
                return ""

    def add_attachment_path(self, file_path):
        path = Path(file_path).expanduser()
        if not path.exists() or not path.is_file():
            self.update_chat("System", f"Attachment skipped (not a file): {file_path}")
            return

        suffix = path.suffix.lower()
        image_mime, _ = mimetypes.guess_type(str(path))
        is_image = suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"} or (image_mime or "").startswith("image/")

        if is_image:
            size = path.stat().st_size
            if size > self.max_image_attachment_bytes:
                self.pending_attachments.append(
                    {
                        "kind": "image_ref",
                        "name": path.name,
                        "path": str(path),
                        "content": (
                            f"Image file is too large to inline ({size} bytes). "
                            "Increase max image bytes in Settings to include this image."
                        ),
                        "data_url": "",
                    }
                )
                self.refresh_attachment_label()
                return

            try:
                mime = image_mime or "image/png"
                raw = path.read_bytes()
                encoded = base64.b64encode(raw).decode("ascii")
                data_url = f"data:{mime};base64,{encoded}"
                self.pending_attachments.append(
                    {
                        "kind": "image",
                        "name": path.name,
                        "path": str(path),
                        "content": f"Image attached: {path.name}",
                        "data_url": data_url,
                    }
                )
                self.refresh_attachment_label()
                return
            except Exception as e:
                self.update_chat("System", f"Failed to attach image {path.name}: {e}")
                return

        text_content = self.read_text_file_safe(path)
        if text_content:
            content = text_content[: self.max_attachment_text_bytes]
            kind = "text"
        else:
            kind = "binary"
            content = f"Binary file attached. Path: {path} Size: {path.stat().st_size} bytes"

        self.pending_attachments.append(
            {
                "kind": kind,
                "name": path.name,
                "path": str(path),
                "content": content,
                "data_url": "",
            }
        )
        self.refresh_attachment_label()

    def handle_add_file(self):
        if self.is_processing:
            return
        selected = filedialog.askopenfilenames(title="Attach files")
        for file_path in selected:
            self.add_attachment_path(file_path)

    def handle_paste_attachment(self):
        if self.is_processing:
            return
        pasted = ""
        try:
            pasted = self.root.clipboard_get()
        except Exception:
            pasted = ""

        candidate_paths = []
        if pasted:
            for line in pasted.splitlines():
                maybe = line.strip().strip('"')
                if maybe and Path(maybe).exists() and Path(maybe).is_file():
                    candidate_paths.append(maybe)

        if candidate_paths:
            for candidate in candidate_paths:
                self.add_attachment_path(candidate)
            return

        if pasted.strip():
            self.pending_attachments.append(
                {
                    "kind": "clipboard_text",
                    "name": "clipboard.txt",
                    "path": "clipboard",
                    "content": pasted.strip()[: self.max_attachment_text_bytes],
                    "data_url": "",
                }
            )
            self.refresh_attachment_label()
            self.update_chat("System", "Clipboard text attached.")
        else:
            self.update_chat(
                "System",
                "Clipboard paste did not contain file paths or text. Copy file paths/text then try Paste.",
            )

    def build_attachment_context(self):
        if not self.pending_attachments:
            return ""
        blocks = ["ATTACHMENTS:"]
        for attachment in self.pending_attachments:
            blocks.append(
                f"- Name: {attachment['name']} | Type: {attachment['kind']} | Path: {attachment['path']}"
            )
            blocks.append("Content:")
            blocks.append(attachment["content"])
            blocks.append("---")
        return "\n".join(blocks)

    def build_user_content_parts(self, text, attachment_context, path_context):
        text_parts = [text]
        if attachment_context:
            text_parts.append(attachment_context)
        if path_context:
            text_parts.append(path_context)
        final_text = "\n\n".join(part for part in text_parts if part).strip()

        image_attachments = [a for a in self.pending_attachments if a.get("kind") == "image" and a.get("data_url")]
        if not image_attachments:
            return final_text

        content_parts: list[dict[str, Any]] = [{"type": "text", "text": final_text or "Please analyze the attached image(s)."}]
        for attachment in image_attachments:
            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": attachment["data_url"]},
                }
            )
        return content_parts

    def extract_requested_paths(self, text):
        candidates = []
        for raw in re.findall(r'"([^"]+)"', text):
            candidates.append(raw)
        for raw in re.findall(r"'([^']+)'", text):
            candidates.append(raw)
        for raw in re.findall(r"(?:[A-Za-z]:\\[^\s]+|\.[/\\][^\s]+)", text):
            candidates.append(raw)
        words = text.replace("\n", " ").split()
        for size in range(2, min(9, len(words) + 1)):
            for idx in range(0, len(words) - size + 1):
                chunk = " ".join(words[idx: idx + size]).strip().strip('"').strip("'").rstrip(".,!?:;")
                if not chunk:
                    continue
                candidate_path = Path(chunk).expanduser()
                if not candidate_path.is_absolute():
                    candidate_path = self.workspace_root / candidate_path
                if candidate_path.exists():
                    candidates.append(str(candidate_path))
        cleaned = []
        for candidate in candidates:
            candidate = candidate.strip().strip('"').strip("'")
            if candidate and candidate not in cleaned:
                cleaned.append(candidate)
        return cleaned

    def build_path_context_for(self, raw_path):
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = self.workspace_root / path
        try:
            path.relative_to(self.workspace_root)
        except Exception:
            return f"Path is outside workspace and was skipped for safety: {path}"
        if not path.exists():
            return f"Path not found: {path}"
        if path.is_dir():
            entries = []
            for idx, child in enumerate(sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))):
                if idx >= 120:
                    entries.append("... (truncated)")
                    break
                marker = "[DIR]" if child.is_dir() else "[FILE]"
                entries.append(f"{marker} {child.name}")
            return f"Directory listing for {path}:\n" + "\n".join(entries)

        size = path.stat().st_size
        text_content = self.read_text_file_safe(path)
        if text_content:
            lines = text_content.splitlines()
            preview = "\n".join(lines[: self.max_path_preview_lines])
            if len(lines) > self.max_path_preview_lines:
                preview += "\n... (truncated)"
            return f"File preview for {path} (size {size} bytes):\n{preview}"
        return f"Binary file info for {path}: size {size} bytes"

    def build_path_context_from_text(self, text):
        if not re.search(r"\b(look|read|open|inspect|analyze|check|review)\b", text, re.IGNORECASE):
            return ""
        requested_paths = self.extract_requested_paths(text)
        if not requested_paths:
            return ""
        blocks = ["REQUESTED PATH CONTEXT:"]
        for raw in requested_paths[:8]:
            blocks.append(self.build_path_context_for(raw))
            blocks.append("---")
        return "\n".join(blocks)

    def augment_message_with_context(self, text):
        attachment_context = self.build_attachment_context()
        path_context = self.build_path_context_from_text(text)
        enriched_content = self.build_user_content_parts(text, attachment_context, path_context)
        # Attachments are one-shot context for the next user send.
        if attachment_context:
            self.pending_attachments.clear()
            self.safe_after(self.refresh_attachment_label)
        return enriched_content

    def extract_file_actions(self, text):
        actions = []
        for line in text.splitlines():
            stripped = line.strip()
            for prefix in ("FILE_READ|", "FILE_LIST|", "FILE_SEARCH|"):
                if stripped.startswith(prefix):
                    actions.append((prefix[:-1], stripped.split("|", 1)[1].strip()))
        return actions

    def remove_file_action_lines(self, text):
        kept = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("FILE_READ|") or stripped.startswith("FILE_LIST|") or stripped.startswith("FILE_SEARCH|"):
                continue
            kept.append(line)
        return "\n".join(kept).strip()

    def resolve_workspace_path(self, raw_path):
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = self.workspace_root / path
        path = path.resolve()
        try:
            path.relative_to(self.workspace_root)
            return path
        except Exception:
            return None

    def run_file_action(self, action, value):
        if action == "FILE_SEARCH":
            return self.search_workspace(value)

        resolved = self.resolve_workspace_path(value)
        if resolved is None:
            return f"{action}: blocked path outside workspace -> {value}"
        if not resolved.exists():
            return f"{action}: path not found -> {resolved}"

        if action == "FILE_LIST":
            if not resolved.is_dir():
                return f"FILE_LIST: not a directory -> {resolved}"
            entries = []
            for idx, child in enumerate(sorted(resolved.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))):
                if idx >= 120:
                    entries.append("... (truncated)")
                    break
                entries.append(("[DIR] " if child.is_dir() else "[FILE] ") + child.name)
            return f"FILE_LIST result for {resolved}:\n" + "\n".join(entries)

        if action == "FILE_READ":
            if not resolved.is_file():
                return f"FILE_READ: not a file -> {resolved}"
            text = self.read_text_file_safe(resolved)
            if not text:
                return f"FILE_READ: file is binary or unreadable -> {resolved}"
            lines = text.splitlines()
            preview = "\n".join(lines[: self.max_path_preview_lines])
            if len(lines) > self.max_path_preview_lines:
                preview += "\n... (truncated)"
            return f"FILE_READ result for {resolved}:\n{preview}"

        return f"Unsupported action: {action}"

    def search_workspace(self, query):
        query = query.strip()
        if not query:
            return "FILE_SEARCH: empty query"
        hits = []
        lowered = query.lower()
        for path in self.workspace_root.rglob("*"):
            if ".git" in path.parts or ".venv" in path.parts:
                continue
            rel = path.relative_to(self.workspace_root)
            if lowered in rel.as_posix().lower():
                hits.append(f"Path match: {rel.as_posix()}")
            if path.is_file() and len(hits) < 60:
                text = self.read_text_file_safe(path)
                if text and lowered in text.lower():
                    hits.append(f"Content match: {rel.as_posix()}")
            if len(hits) >= 60:
                break
        if not hits:
            return f"FILE_SEARCH: no matches for '{query}'"
        return "FILE_SEARCH results:\n" + "\n".join(hits)

    def has_inline_images(self):
        for message in self.messages:
            content = message.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        return True
        return False

    def strip_images_from_messages(self, messages):
        stripped = []
        for message in messages:
            content = message.get("content")
            if not isinstance(content, list):
                stripped.append(message)
                continue
            text_chunks = []
            had_image = False
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_chunks.append(part.get("text", ""))
                if isinstance(part, dict) and part.get("type") == "image_url":
                    had_image = True
            merged_text = "\n".join(chunk for chunk in text_chunks if chunk).strip()
            if had_image and merged_text:
                merged_text += "\n[Image attachment omitted because backend does not support image inputs.]"
            elif had_image and not merged_text:
                merged_text = "[Image attachment omitted because backend does not support image inputs.]"
            stripped.append({"role": message["role"], "content": merged_text})
        return stripped

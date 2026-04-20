import os

try:
    from plyer import notification as plyer_notification
except Exception:
    plyer_notification = None

try:
    from win10toast_click import ToastNotifier
except Exception:
    ToastNotifier = None


class NotificationMixin:
    def initialize_work_check_notifications(self):
        self._work_check_after_id = None
        self._work_check_notification_error_seen = False
        self._toast_notifier = None
        if os.name == "nt" and ToastNotifier is not None:
            try:
                self._toast_notifier = ToastNotifier()
            except Exception:
                self._toast_notifier = None
        self.work_check_interval_minutes = max(0, int(getattr(self, "work_check_interval_minutes", 0)))
        self.reschedule_work_check_notifications(announce=False)

    def set_work_check_interval_minutes(self, minutes, announce=False):
        previous = getattr(self, "work_check_interval_minutes", 0)
        self.work_check_interval_minutes = max(0, int(minutes))
        self.reschedule_work_check_notifications(announce=announce)

        if not announce:
            return
        if self.work_check_interval_minutes <= 0 and previous > 0:
            self.update_chat("System", "Work-check notifications disabled.")
            return
        if self.work_check_interval_minutes > 0:
            self.update_chat(
                "System",
                (
                    "Work-check notifications enabled every "
                    f"{self.work_check_interval_minutes} minute(s)."
                ),
            )

    def cancel_work_check_notifications(self):
        after_id = getattr(self, "_work_check_after_id", None)
        if not after_id:
            return
        try:
            self.root.after_cancel(after_id)
        except Exception:
            pass
        self._work_check_after_id = None

    def reschedule_work_check_notifications(self, announce=False):
        self.cancel_work_check_notifications()
        interval = max(0, int(getattr(self, "work_check_interval_minutes", 0)))
        if interval <= 0:
            return

        delay_ms = interval * 60 * 1000
        self._work_check_after_id = self.root.after(delay_ms, self._work_check_notification_tick)

    def _work_check_notification_tick(self):
        self._work_check_after_id = None
        self.send_work_check_notification()
        self.reschedule_work_check_notifications(announce=False)

    def send_work_check_notification(self):
        if os.name != "nt":
            return

        if self._toast_notifier is not None:
            try:
                self._toast_notifier.show_toast(
                    "Genare",
                    "Any work you would like me to do?",
                    duration=8,
                    threaded=True,
                    callback_on_click=self.on_work_check_notification_click,
                )
                return
            except Exception as e:
                if not self._work_check_notification_error_seen:
                    self._work_check_notification_error_seen = True
                    self.update_chat("System", f"Clickable Windows notification failed; falling back: {e}")

        if plyer_notification is None:
            if not self._work_check_notification_error_seen:
                self._work_check_notification_error_seen = True
                self.update_chat("System", "Windows notifications are unavailable (missing plyer dependency).")
            return

        try:
            plyer_notification.notify(
                title="Genare",
                message="Any work you would like me to do?",
                app_name="Genare",
                timeout=8,
            )
        except Exception as e:
            if not self._work_check_notification_error_seen:
                self._work_check_notification_error_seen = True
                self.update_chat("System", f"Failed to send Windows notification: {e}")

    def on_work_check_notification_click(self):
        self.safe_after(self.bring_window_to_front)

    def bring_window_to_front(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(250, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
            if hasattr(self, "msg_entry"):
                self.msg_entry.focus_set()
        except Exception:
            pass

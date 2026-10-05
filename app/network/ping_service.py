"""Companion Computer probing and ping service."""

import os
import re
import socket
import subprocess
import sys
import time
from typing import Optional, Tuple
from PySide6.QtCore import QObject, Signal, QTimer

from app.models import CompanionConfig


class PingWorker(QObject):
    probe_finished = Signal(bool, float, str)  # (reachable, rtt_ms, error)

    def __init__(self, host: str, timeout_s: float, ssh_port: int = 22):
        super().__init__()
        self.host = host
        self.timeout_s = timeout_s
        self.ssh_port = ssh_port

    def probe(self):
        reachable, rtt, err = self._probe_host(self.host, self.timeout_s, self.ssh_port)
        self.probe_finished.emit(reachable, rtt, err)

    @staticmethod
    def _probe_host(host: str, timeout_s: float, port: int = 22) -> Tuple[bool, float, str]:
        """Probes host via system ping with fallback to TCP socket connect."""
        t0 = time.time()
        timeout_ms = int(timeout_s * 1000)

        # 1. Try system ping
        try:
            if sys.platform == "darwin":
                cmd = ["ping", "-c", "1", "-W", str(timeout_ms), host]
            elif sys.platform == "win32":
                cmd = ["ping", "-n", "1", "-w", str(timeout_ms), host]
            else:  # Linux & other Unix
                cmd = ["ping", "-c", "1", "-W", str(max(1, int(timeout_s))), host]

            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_s + 0.5,
            )
            rtt_match = re.search(r"time[=<]([\d.]+)\s*ms", proc.stdout)
            if proc.returncode == 0:
                rtt = float(rtt_match.group(1)) if rtt_match else (time.time() - t0) * 1000.0
                return True, rtt, ""
        except Exception:
            pass

        # 2. Fallback to TCP socket connection probe (e.g. port 22 or 80)
        try:
            t_sock_start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_s)
            res = sock.connect_ex((host, port))
            sock.close()
            if res == 0:
                rtt = (time.time() - t_sock_start) * 1000.0
                return True, rtt, ""
        except Exception as e:
            return False, 0.0, str(e)

        return False, 0.0, "Host unreachable"


class PingService(QObject):
    """Monitors the companion computer host at configured intervals."""
    state_changed = Signal(str, object, str)  # (state, rtt_ms or None, error_msg)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.companion: Optional[CompanionConfig] = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.started_at: float = 0.0
        self.last_ok_at: Optional[float] = None
        self.last_rtt: Optional[float] = None
        self.last_error: str = ""
        self._probing: bool = False

    def set_companion(self, companion: Optional[CompanionConfig]):
        self.companion = companion
        self.reset()
        if companion and companion.host:
            self.start()
        else:
            self.stop()
            self._update_state()

    def reset(self):
        self.started_at = time.time()
        self.last_ok_at = None
        self.last_rtt = None
        self.last_error = ""

    def start(self):
        self.reset()
        if not self.companion or not self.companion.host:
            self._update_state()
            return
        self.timer.start(int(self.companion.interval_s * 1000))
        self._tick()

    def stop(self):
        self.timer.stop()
        self._probing = False

    def _tick(self):
        if not self.companion or not self.companion.host:
            self._update_state()
            return
        if self._probing:
            return

        self._probing = True
        host = self.companion.host
        timeout_s = min(5.0, max(1.0, float(self.companion.interval_s)))

        # Run ping asynchronously
        import threading
        def worker_thread():
            reachable, rtt, err = PingWorker._probe_host(host, timeout_s)
            self._on_probe_result(reachable, rtt, err)

        threading.Thread(target=worker_thread, daemon=True).start()

    def _on_probe_result(self, reachable: bool, rtt_ms: float, error: str):
        self._probing = False
        now = time.time()
        if reachable:
            self.last_ok_at = now
            self.last_rtt = rtt_ms
            self.last_error = ""
        else:
            self.last_error = error or "Ping failed"

        self._update_state()

    def _compute_state(self) -> str:
        if not self.companion or not self.companion.host:
            return "unset"
        now = time.time()
        timeout_s = self.companion.timeout_s

        if self.last_ok_at is not None and (now - self.last_ok_at) <= timeout_s:
            return "online"
        if self.last_ok_at is None and (now - self.started_at) < timeout_s:
            return "checking"
        if self.last_error and (self.last_ok_at is None or (now - self.last_ok_at) > timeout_s):
            return "offline" if "unreachable" in self.last_error.lower() else "error"
        return "offline"

    def _update_state(self):
        state = self._compute_state()
        self.state_changed.emit(state, self.last_rtt if state == "online" else None, self.last_error)

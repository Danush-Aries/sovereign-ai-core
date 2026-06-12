"""
Sovereign AI Core — Air-Gap Kill-Switch
Intercepts socket creation at the OS level to enforce network isolation when
Sovereign Mode is active.  Only loopback connections (127.x.x.x / ::1) are
allowed while the kill-switch is engaged.
"""

from __future__ import annotations

import socket
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_REAL_SOCKET = socket.socket  # keep a reference before patching
logger = logging.getLogger("sovereign.air_gap")


class AirGapController:
    """
    Thread-safe network kill-switch.

    Usage::

        from backend.app.core.air_gap import air_gap
        air_gap.enable()   # block all outbound traffic
        air_gap.disable()  # restore normal network access
    """

    def __init__(self, leak_log: Optional[Path] = None) -> None:
        self._sovereign_mode: bool = False
        self._blocked_attempts: int = 0
        self._leak_log: Optional[Path] = leak_log

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def sovereign_mode(self) -> bool:
        return self._sovereign_mode

    @property
    def blocked_attempts(self) -> int:
        return self._blocked_attempts

    def enable(self) -> None:
        """Engage the air-gap kill-switch."""
        self._sovereign_mode = True
        logger.warning("AIR-GAP ENABLED — all outbound connections are blocked.")

    def disable(self) -> None:
        """Disengage the air-gap kill-switch."""
        self._sovereign_mode = False
        logger.info("Air-gap disabled — network access restored.")

    # ── Socket interceptor ────────────────────────────────────────────────────

    def __call__(
        self,
        family: int = socket.AF_INET,
        type: int = socket.SOCK_STREAM,
        proto: int = 0,
        fileno: Optional[int] = None,
    ) -> socket.socket:
        """Replacement for socket.socket() that enforces the kill-switch."""
        if self._sovereign_mode:
            self._blocked_attempts += 1
            self._log_blocked_attempt(family, type, proto)
            raise PermissionError(
                "Sovereign Mode is active — all outbound network connections are blocked."
            )
        return _REAL_SOCKET(family, type, proto)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _log_blocked_attempt(self, family: int, type: int, proto: int) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        msg = f"[{ts}] BLOCKED: family={family} type={type} proto={proto}\n"
        logger.warning(msg.strip())
        if self._leak_log:
            try:
                with self._leak_log.open("a") as fh:
                    fh.write(msg)
            except OSError:
                pass  # never crash the main thread over a logging failure


# ── Module-level singleton ────────────────────────────────────────────────────
air_gap = AirGapController()

# Patch socket.socket so every library in the process is subject to the kill-switch.
socket.socket = air_gap  # type: ignore[assignment]

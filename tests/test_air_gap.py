"""Tests for the Air-Gap kill-switch controller."""

from __future__ import annotations

import socket
import pytest
from pathlib import Path

from backend.app.core.air_gap import AirGapController


@pytest.fixture
def controller(tmp_path: Path) -> AirGapController:
    """Fresh controller instance — does NOT monkey-patch socket.socket."""
    return AirGapController(leak_log=tmp_path / "blocked.log")


def test_initially_disabled(controller: AirGapController) -> None:
    assert controller.sovereign_mode is False
    assert controller.blocked_attempts == 0


def test_enable_disable(controller: AirGapController) -> None:
    controller.enable()
    assert controller.sovereign_mode is True
    controller.disable()
    assert controller.sovereign_mode is False


def test_blocks_socket_creation_when_enabled(controller: AirGapController) -> None:
    controller.enable()
    with pytest.raises(PermissionError, match="Sovereign Mode"):
        controller(socket.AF_INET, socket.SOCK_STREAM, 0)


def test_allows_socket_creation_when_disabled(controller: AirGapController) -> None:
    controller.disable()
    sock = controller(socket.AF_INET, socket.SOCK_STREAM, 0)
    assert sock is not None
    sock.close()


def test_blocked_attempt_counter(controller: AirGapController) -> None:
    controller.enable()
    for _ in range(3):
        try:
            controller(socket.AF_INET, socket.SOCK_STREAM, 0)
        except PermissionError:
            pass
    assert controller.blocked_attempts == 3


def test_leak_log_written(controller: AirGapController, tmp_path: Path) -> None:
    log_file = tmp_path / "blocked.log"
    controller._leak_log = log_file
    controller.enable()
    try:
        controller(socket.AF_INET, socket.SOCK_STREAM, 0)
    except PermissionError:
        pass
    assert log_file.exists()
    assert "BLOCKED" in log_file.read_text()

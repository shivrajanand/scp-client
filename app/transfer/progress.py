"""
Transfer progress tracking.

A small, dependency-free helper that turns raw (bytes_transferred, total)
callbacks into the richer information the GUI wants to display: percent,
speed, and ETA (spec section 21).
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class ProgressSnapshot:
    filename: str
    bytes_transferred: int
    total_bytes: int
    percent: float
    speed_bytes_per_sec: float
    eta_seconds: float


class ProgressTracker:
    """Accumulates raw progress callbacks into smoothed speed/ETA figures."""

    def __init__(self, filename: str, smoothing: float = 0.3):
        self.filename = filename
        self._start_time = time.monotonic()
        self._last_time = self._start_time
        self._last_bytes = 0
        self._smoothed_speed = 0.0
        self._smoothing = smoothing

    def update(self, bytes_transferred: int, total_bytes: int) -> ProgressSnapshot:
        now = time.monotonic()
        elapsed = max(now - self._last_time, 1e-6)
        delta_bytes = max(bytes_transferred - self._last_bytes, 0)
        instantaneous_speed = delta_bytes / elapsed

        if self._smoothed_speed == 0.0:
            self._smoothed_speed = instantaneous_speed
        else:
            self._smoothed_speed = (
                self._smoothing * instantaneous_speed
                + (1 - self._smoothing) * self._smoothed_speed
            )

        self._last_time = now
        self._last_bytes = bytes_transferred

        percent = (bytes_transferred / total_bytes * 100.0) if total_bytes else 0.0
        remaining = max(total_bytes - bytes_transferred, 0)
        eta = (remaining / self._smoothed_speed) if self._smoothed_speed > 0 else float("inf")

        return ProgressSnapshot(
            filename=self.filename,
            bytes_transferred=bytes_transferred,
            total_bytes=total_bytes,
            percent=percent,
            speed_bytes_per_sec=self._smoothed_speed,
            eta_seconds=eta,
        )


def format_bytes(num_bytes: float) -> str:
    """Human-readable byte count, e.g. '72.4 MB'."""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"


def format_speed(bytes_per_sec: float) -> str:
    return f"{format_bytes(bytes_per_sec)}/s"


def format_eta(seconds: float) -> str:
    if seconds == float("inf") or seconds != seconds:  # inf or NaN
        return "--:--"
    seconds = max(int(seconds), 0)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

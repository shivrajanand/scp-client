"""
Configuration persistence.

Handles loading/saving of the manual server list and application
preferences to JSON files under %APPDATA%\\SCPTransferClient on Windows
(or an equivalent app-data directory elsewhere, for cross-platform
development).

SECURITY: This module must never write password fields anywhere. The
Server / AppPreferences models simply have no password attribute, so
there is nothing to accidentally serialize.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from app.config.models import AppPreferences, Server, ServerSource

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration data is invalid or cannot be read/written."""


def get_app_data_dir() -> Path:
    """Return the directory used for storing application configuration.

    On Windows this resolves to %APPDATA%\\SCPTransferClient.
    On other platforms (used for development/testing) it falls back to
    ~/.config/SCPTransferClient so the app remains runnable off-Windows.
    """
    import os

    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata)
    else:
        base = Path.home() / ".config"
    directory = base / "SCPTransferClient"
    return directory


class ConfigManager:
    """Loads and saves servers.json and config.json."""

    def __init__(self, app_data_dir: Path = None):
        self.app_data_dir = app_data_dir or get_app_data_dir()
        self.servers_path = self.app_data_dir / "servers.json"
        self.config_path = self.app_data_dir / "config.json"

    # ------------------------------------------------------------------
    # Servers
    # ------------------------------------------------------------------
    def load_servers(self) -> List[Server]:
        """Load manually configured servers. Returns [] if the file is absent."""
        if not self.servers_path.exists():
            return []

        try:
            raw = json.loads(self.servers_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"servers.json is not valid JSON: {exc}") from exc
        except OSError as exc:
            raise ConfigError(f"Unable to read servers.json: {exc}") from exc

        entries = raw.get("servers", []) if isinstance(raw, dict) else []
        servers: List[Server] = []
        for entry in entries:
            try:
                servers.append(Server.from_dict(entry, source=ServerSource.MANUAL))
            except ValueError as exc:
                logger.warning("Skipping invalid server entry in servers.json: %s", exc)
        return servers

    def save_servers(self, servers: List[Server]) -> None:
        """Persist manually configured servers. SSH-config servers are never saved here."""
        manual_servers = [s for s in servers if s.source == ServerSource.MANUAL]
        payload = {"servers": [s.to_dict() for s in manual_servers]}

        self._ensure_dir()
        try:
            self.servers_path.write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            raise ConfigError(f"Unable to write servers.json: {exc}") from exc

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------
    def load_preferences(self) -> AppPreferences:
        if not self.config_path.exists():
            return AppPreferences()
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read config.json (%s); using defaults", exc)
            return AppPreferences()
        return AppPreferences.from_dict(raw if isinstance(raw, dict) else {})

    def save_preferences(self, prefs: AppPreferences) -> None:
        self._ensure_dir()
        try:
            self.config_path.write_text(
                json.dumps(prefs.to_dict(), indent=2), encoding="utf-8"
            )
        except OSError as exc:
            raise ConfigError(f"Unable to write config.json: {exc}") from exc

    def _ensure_dir(self) -> None:
        self.app_data_dir.mkdir(parents=True, exist_ok=True)

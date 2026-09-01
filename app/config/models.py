"""
Data models used throughout the application.

These are deliberately simple dataclasses with no dependency on Qt or
Paramiko so they can be freely imported and unit tested.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ServerSource(str, Enum):
    """Where a server definition came from."""

    SSH_CONFIG = "ssh_config"
    MANUAL = "manual"


@dataclass
class Server:
    """
    A connectable server definition.

    Passwords are intentionally NOT part of this model -- they must never
    be persisted alongside server definitions. See project spec section 15.
    """

    name: str
    hostname: str
    username: str
    port: int = 22
    source: ServerSource = ServerSource.MANUAL
    enabled: bool = True
    identity_file: Optional[str] = None  # optional SSH key path (from ssh config), never a secret itself

    def display_label(self) -> str:
        """Human readable label used in the server dropdown / manager."""
        return f"{self.name} ({self.username}@{self.hostname}:{self.port})"

    def to_dict(self) -> dict:
        """Serialize to a plain dict suitable for JSON storage.

        Only used for MANUAL servers; SSH_CONFIG servers are never
        persisted by the application (they live in the user's ssh config).
        """
        return {
            "name": self.name,
            "hostname": self.hostname,
            "username": self.username,
            "port": self.port,
            "enabled": self.enabled,
        }

    @staticmethod
    def from_dict(data: dict, source: ServerSource = ServerSource.MANUAL) -> "Server":
        """Deserialize from a plain dict. Raises ValueError on missing fields."""
        required = ("name", "hostname", "username")
        missing = [key for key in required if not data.get(key)]
        if missing:
            raise ValueError(f"Server definition missing required field(s): {', '.join(missing)}")

        port_raw = data.get("port", 22)
        try:
            port = int(port_raw)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid port value: {port_raw!r}")
        if not (0 < port <= 65535):
            raise ValueError(f"Port out of range: {port}")

        return Server(
            name=str(data["name"]),
            hostname=str(data["hostname"]),
            username=str(data["username"]),
            port=port,
            source=source,
            enabled=bool(data.get("enabled", True)),
        )


class TransferDirection(str, Enum):
    UPLOAD = "UPLOAD"
    DOWNLOAD = "DOWNLOAD"


@dataclass
class TransferRequest:
    """A single-file transfer request handed to the transfer worker."""

    direction: TransferDirection
    server: Server
    source_path: str
    destination_path: str
    overwrite: bool = False

    def describe(self) -> str:
        arrow = "->" if self.direction == TransferDirection.UPLOAD else "<-"
        return f"[{self.direction.value}] {self.source_path} {arrow} {self.destination_path} ({self.server.name})"


@dataclass
class RemoteEntry:
    """A single entry (file or directory) in a remote directory listing."""

    name: str
    path: str
    is_dir: bool
    size: Optional[int] = None
    modified: Optional[float] = None


@dataclass
class AppPreferences:
    """Non-sensitive GUI/user preferences persisted between sessions."""

    theme: str = "dark"
    last_server_name: Optional[str] = None
    last_local_directory: Optional[str] = None
    last_remote_directory: Optional[str] = None
    use_ssh_config: bool = True

    def to_dict(self) -> dict:
        return {
            "theme": self.theme,
            "last_server_name": self.last_server_name,
            "last_local_directory": self.last_local_directory,
            "last_remote_directory": self.last_remote_directory,
            "use_ssh_config": self.use_ssh_config,
        }

    @staticmethod
    def from_dict(data: dict) -> "AppPreferences":
        return AppPreferences(
            theme=data.get("theme", "dark"),
            last_server_name=data.get("last_server_name"),
            last_local_directory=data.get("last_local_directory"),
            last_remote_directory=data.get("last_remote_directory"),
            use_ssh_config=bool(data.get("use_ssh_config", True)),
        )

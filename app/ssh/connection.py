"""
SSH connection management.

Wraps a single Paramiko SSHClient connection: establishing it,
authenticating with a password held only in memory, exposing SFTP
operations for the remote browser and transfer layer, and tearing the
connection down cleanly (discarding the password immediately after use).
"""

from __future__ import annotations

import logging
import socket
from pathlib import Path
from typing import Callable, List, Optional

import paramiko

from app.config.models import RemoteEntry, Server
from app.ssh.host_keys import (
    HostKeyMismatchError,
    UnknownHostKeyError,
    check_known_host,
    load_host_keys,
)

logger = logging.getLogger(__name__)


class ConnectionError_(Exception):
    """Generic, user-facing connection failure (see spec section 25)."""


class AuthenticationFailedError(Exception):
    """The server rejected the supplied username/password."""


class HostKeyVerificationRequired(Exception):
    """Raised to hand control back to the GUI for a host-key trust decision."""

    def __init__(self, hostname: str, key_type: str, fingerprint: str, changed: bool):
        self.hostname = hostname
        self.key_type = key_type
        self.fingerprint = fingerprint
        self.changed = changed
        super().__init__(f"Host key verification required for {hostname}")


class SSHConnection:
    """A single managed SSH connection with SFTP access.

    Usage:
        conn = SSHConnection(server)
        conn.connect(password="...", host_key_check=my_callback)
        sftp = conn.sftp
        ...
        conn.close()

    The password is only ever held as a local variable during connect()
    and is never stored as an attribute on this object.
    """

    def __init__(self, server: Server, known_hosts_path: Optional[Path] = None):
        self.server = server
        self.known_hosts_path = known_hosts_path
        self._client: Optional[paramiko.SSHClient] = None
        self._sftp: Optional[paramiko.SFTPClient] = None
        self.connected: bool = False

    @property
    def sftp(self) -> paramiko.SFTPClient:
        if not self._sftp:
            raise ConnectionError_("Not connected.")
        return self._sftp

    def connect(
        self,
        password: Optional[str] = None,
        timeout: float = 10.0,
        allow_new_host_key: Optional[Callable[[str, str, str, bool], bool]] = None,
    ) -> None:
        """Establish the SSH connection and open an SFTP session.

        `allow_new_host_key(hostname, key_type, fingerprint, changed) -> bool`
        is an optional synchronous callback (typically backed by a GUI
        dialog) used to decide whether to trust a new/changed host key.
        If it returns True the key is trusted for this session only.
        If omitted, unknown/changed host keys cause a hard failure.
        """
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        known_hosts = load_host_keys(self.known_hosts_path)
        client._host_keys = known_hosts  # noqa: SLF001 - Paramiko has no public setter for this

        # We use RejectPolicy plus our own pre-check via check_known_host()
        # (invoked indirectly through connect()'s key exchange) so that we
        # keep full control over the trust decision instead of Paramiko's
        # built-in auto-add behavior.
        client.set_missing_host_key_policy(paramiko.RejectPolicy())

        connect_kwargs = dict(
            hostname=self.server.hostname,
            port=self.server.port,
            username=self.server.username,
            timeout=timeout,
            allow_agent=False,
            look_for_keys=False,
        )
        if password is not None:
            connect_kwargs["password"] = password
        if self.server.identity_file:
            connect_kwargs["key_filename"] = self.server.identity_file
            connect_kwargs["look_for_keys"] = True

        try:
            client.connect(**connect_kwargs)
        except paramiko.AuthenticationException as exc:
            raise AuthenticationFailedError(
                "The server rejected the supplied username/password."
            ) from exc
        except paramiko.SSHException as exc:
            message = str(exc)
            if "not found in known_hosts" in message or "Server" in message and "not found" in message:
                # Fall through to explicit host-key handling below.
                pass
            self._handle_host_key_rejection(client, connect_kwargs, allow_new_host_key, exc)
        except (socket.timeout, socket.error, OSError) as exc:
            raise ConnectionError_(
                f"Unable to connect to {self.server.hostname}:{self.server.port}. "
                "Check network connectivity and SSH availability."
            ) from exc
        else:
            self._finalize_connection(client)
            return

        # If we reach here, host-key handling above resolved the trust
        # decision and we should retry the connection once.
        try:
            client.connect(**connect_kwargs)
        except paramiko.AuthenticationException as exc:
            raise AuthenticationFailedError(
                "The server rejected the supplied username/password."
            ) from exc
        except (socket.timeout, socket.error, OSError) as exc:
            raise ConnectionError_(
                f"Unable to connect to {self.server.hostname}:{self.server.port}. "
                "Check network connectivity and SSH availability."
            ) from exc

        self._finalize_connection(client)

    def _handle_host_key_rejection(self, client, connect_kwargs, allow_new_host_key, original_exc):
        """Attempt to resolve a host-key rejection via the provided callback."""
        # Retrieve the offered key by doing a lightweight transport-level
        # connection without host-key checking, purely to read the key
        # for fingerprint display. This does not authenticate.
        transport = None
        try:
            sock = socket.create_connection((self.server.hostname, self.server.port), timeout=10)
            transport = paramiko.Transport(sock)
            transport.start_client(timeout=10)
            key = transport.get_remote_server_key()
        except Exception as exc:
            raise ConnectionError_(
                f"Unable to connect to {self.server.hostname}:{self.server.port}. "
                "Check network connectivity and SSH availability."
            ) from exc
        finally:
            if transport is not None:
                transport.close()

        from app.ssh.host_keys import fingerprint_of

        changed = False
        try:
            check_known_host(self.server.hostname, key, self.known_hosts_path)
        except HostKeyMismatchError:
            changed = True
        except UnknownHostKeyError:
            changed = False

        fingerprint = fingerprint_of(key)

        if allow_new_host_key is None:
            kind = "changed" if changed else "unknown"
            raise HostKeyVerificationRequired(
                self.server.hostname, key.get_name(), fingerprint, changed
            )

        trusted = allow_new_host_key(self.server.hostname, key.get_name(), fingerprint, changed)
        if not trusted:
            raise ConnectionError_("Connection cancelled: host key was not trusted.")

        # Trust for this connection: add to the client's in-memory host keys
        # so the upcoming retry succeeds. Persistence to disk (if the user
        # chose "Trust" rather than "Trust Once") is handled by the caller
        # via app.ssh.host_keys.trust_host_key().
        client.get_host_keys().add(self.server.hostname, key.get_name(), key)

    def _finalize_connection(self, client: paramiko.SSHClient) -> None:
        try:
            sftp = client.open_sftp()
        except paramiko.SSHException as exc:
            client.close()
            raise ConnectionError_(f"Connected, but could not open an SFTP session: {exc}") from exc

        self._client = client
        self._sftp = sftp
        self.connected = True

    # ------------------------------------------------------------------
    # Remote filesystem helpers (read-only, per spec section 18)
    # ------------------------------------------------------------------

    def resolve_home_directory(self) -> str:
        """Resolve the actual remote home directory after authentication."""
        try:
            path = self.sftp.normalize(".")
        except Exception:
            return f"/home/{self.server.username}/"
        if not path.endswith("/"):
            path += "/"
        return path

    def list_directory(self, remote_path: str) -> List[RemoteEntry]:
        """List the contents of a remote directory."""
        entries: List[RemoteEntry] = []
        try:
            for attr in self.sftp.listdir_attr(remote_path):
                import stat as stat_module

                is_dir = stat_module.S_ISDIR(attr.st_mode) if attr.st_mode else False
                child_path = remote_path.rstrip("/") + "/" + attr.filename
                entries.append(
                    RemoteEntry(
                        name=attr.filename,
                        path=child_path,
                        is_dir=is_dir,
                        size=attr.st_size,
                        modified=attr.st_mtime,
                    )
                )
        except FileNotFoundError as exc:
            raise ConnectionError_("The selected remote path no longer exists.") from exc
        except PermissionError as exc:
            raise ConnectionError_(
                "Permission denied. The current user does not have permission to access this path."
            ) from exc
        except IOError as exc:
            raise ConnectionError_(f"Unable to list remote directory: {exc}") from exc

        entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
        return entries

    def remote_file_exists(self, remote_path: str) -> bool:
        try:
            self.sftp.stat(remote_path)
            return True
        except FileNotFoundError:
            return False
        except IOError:
            return False

    def close(self) -> None:
        """Close the SFTP session and SSH transport cleanly."""
        if self._sftp is not None:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        self.connected = False

    def __enter__(self) -> "SSHConnection":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

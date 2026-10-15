"""
SSH connection management.

Wraps a single Paramiko SSHClient connection: establishing it,
authenticating with a password held only in memory, exposing SFTP
operations for the remote browser and transfer layer, and tearing the
connection down cleanly (discarding the password immediately after use).

Supports:
  * ~/.ssh/config (re-read on every connect(), so edits are picked up
    without restarting the app): HostName, Port, User, IdentityFile,
    ProxyJump, ProxyCommand.
  * ProxyJump chains (multiple comma-separated hops), either from the
    Server object (`server.proxy_jump`, optional) or from ssh config.
"""

from __future__ import annotations

import logging
import os
import re
import socket
import stat as stat_module
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import paramiko

from app.config.models import RemoteEntry, Server, ServerSource
from app.ssh.host_keys import (
    HostKeyMismatchError,
    UnknownHostKeyError,
    check_known_host,
    fingerprint_of,
)

logger = logging.getLogger(__name__)

DEFAULT_SSH_CONFIG = Path.home() / ".ssh" / "config"


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


# ----------------------------------------------------------------------
# ssh_config helpers
# ----------------------------------------------------------------------


@dataclass
class _Target:
    """Fully resolved connection parameters for one host."""

    hostname: str
    port: int = 22
    username: Optional[str] = None
    key_files: List[str] = field(default_factory=list)
    proxy_command: Optional[str] = None
    proxy_jump: Optional[str] = None
    matched: bool = False  # True if an explicit ssh_config Host block matched


@dataclass
class JumpHop:
    """One resolved ProxyJump hop (used by the GUI to ask for its password)."""

    label: str  # alias as written in ProxyJump, e.g. "shivrajbatul"
    username: str
    hostname: str
    port: int
    has_key: bool  # an IdentityFile is configured for this hop


# (username, hostname, port) -> password, or None if the user cancelled.
JumpPasswordProvider = Callable[[str, str, int], Optional[str]]

_JUMP_RE = re.compile(
    r"^(?:(?P<user>[^@]+)@)?(?P<host>\[[^\]]+\]|[^:]+)(?::(?P<port>\d+))?$"
)


def _parse_jump_spec(spec: str) -> List[tuple]:
    """Parse 'user@host:port,host2' into [(user|None, host, port|None), ...]."""
    hops = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("ssh://"):
            part = part[len("ssh://"):]
        m = _JUMP_RE.match(part)
        if not m:
            raise ConnectionError_(f"Invalid ProxyJump entry: {part!r}")
        host = m.group("host").strip("[]")
        port = int(m.group("port")) if m.group("port") else None
        hops.append((m.group("user"), host, port))
    return hops


class _HostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """Decide trust for every host key (direct host and jump hosts alike).

    The client's own host-key store is left empty, so Paramiko calls this
    policy for every connection. We consult our known_hosts file and fall
    back to the GUI callback for unknown/changed keys. Doing this inside the
    handshake means it works unchanged through a jump host / proxy socket
    (no separate probe connection needed).
    """

    def __init__(
        self,
        known_hosts_path: Optional[Path],
        callback: Optional[Callable[[str, str, str, bool], bool]],
    ):
        self.known_hosts_path = known_hosts_path
        self.callback = callback

    def missing_host_key(self, client, hostname, key):
        changed = False
        try:
            check_known_host(hostname, key, self.known_hosts_path)
            return  # known and matching
        except HostKeyMismatchError:
            changed = True
        except UnknownHostKeyError:
            changed = False

        fingerprint = fingerprint_of(key)
        if self.callback is None:
            raise HostKeyVerificationRequired(hostname, key.get_name(), fingerprint, changed)
        if not self.callback(hostname, key.get_name(), fingerprint, changed):
            raise ConnectionError_("Connection cancelled: host key was not trusted.")
        # Trusted for this session. Persisting (if the user chose "Trust")
        # is done by the caller via app.ssh.host_keys.trust_host_key().


class SSHConnection:
    """A single managed SSH connection with SFTP access.

    Usage:
        conn = SSHConnection(server)
        conn.connect(password="...", allow_new_host_key=my_callback)
        sftp = conn.sftp
        ...
        conn.close()

    The password is only ever held as a local variable during connect()
    and is never stored as an attribute on this object.
    """

    # Optional process-wide fallback used when connect() isn't given its own
    # jump_password_provider (lets the GUI hook in without changing worker code).
    default_jump_password_provider: Optional[JumpPasswordProvider] = None

    def __init__(
        self,
        server: Server,
        known_hosts_path: Optional[Path] = None,
        ssh_config_path: Optional[Path] = None,
    ):
        self.server = server
        self.known_hosts_path = known_hosts_path
        self.ssh_config_path = ssh_config_path or DEFAULT_SSH_CONFIG
        self._client: Optional[paramiko.SSHClient] = None
        self._jump_clients: List[paramiko.SSHClient] = []
        self._jump_password_provider: Optional[JumpPasswordProvider] = None
        self._sftp: Optional[paramiko.SFTPClient] = None
        self.connected: bool = False

    @property
    def sftp(self) -> paramiko.SFTPClient:
        if not self._sftp:
            raise ConnectionError_("Not connected.")
        return self._sftp

    # ------------------------------------------------------------------
    # ssh config resolution (read fresh on every call -> picks up edits)
    # ------------------------------------------------------------------

    def _load_ssh_config(self) -> Optional[paramiko.SSHConfig]:
        try:
            if self.ssh_config_path.is_file():
                return paramiko.SSHConfig.from_path(str(self.ssh_config_path))
        except Exception as exc:  # unreadable / malformed config must not break connecting
            logger.warning("Could not read %s: %s", self.ssh_config_path, exc)
        return None

    @staticmethod
    def _lookup(cfg: Optional[paramiko.SSHConfig], alias: str) -> _Target:
        opts = cfg.lookup(alias) if cfg is not None else {}
        key_files = opts.get("identityfile") or []
        if isinstance(key_files, str):
            key_files = [key_files]

        def clean(value):
            if value is None or str(value).strip().lower() == "none":
                return None
            return str(value).strip()

        try:
            port = int(opts.get("port", 22))
        except (TypeError, ValueError):
            port = 22
        return _Target(
            hostname=opts.get("hostname", alias),
            port=port,
            username=opts.get("user"),
            key_files=[os.path.expanduser(k) for k in key_files],
            proxy_command=clean(opts.get("proxycommand")),
            proxy_jump=clean(opts.get("proxyjump")),
            # paramiko always returns at least {'hostname': alias}; anything
            # more means a Host block (or Host *) really matched.
            matched=bool(set(opts) - {"hostname"}),
        )

    @classmethod
    def _lookup_first_match(cls, cfg: Optional[paramiko.SSHConfig], aliases: List[str]) -> _Target:
        """Look up several candidate aliases; return the first that matches a Host block."""
        first: Optional[_Target] = None
        for alias in aliases:
            if not alias:
                continue
            target = cls._lookup(cfg, alias)
            if first is None:
                first = target
            if target.matched:
                return target
        return first or cls._lookup(cfg, "")

    def _resolve_target(self, cfg: Optional[paramiko.SSHConfig]) -> _Target:
        """Merge the app's Server settings with ~/.ssh/config (read fresh each connect).

        * SSH_CONFIG servers: the config file is the source of truth. It is
          looked up by the Host *alias* (server.name), which is what
          ProxyJump / IdentityFile / Port etc. are attached to. The stored
          Server values are only a fallback if the config can't be read.
        * MANUAL servers: values set on the Server win; the config fills in
          the rest (looked up by hostname). Port 22 counts as 'unset'.
        """
        server = self.server

        if server.source == ServerSource.SSH_CONFIG:
            c = self._lookup_first_match(cfg, [server.name, server.hostname])
            if c.matched:
                key_files = c.key_files or ([server.identity_file] if server.identity_file else [])
                proxy_jump = c.proxy_jump or server.proxy_jump
                proxy_command = c.proxy_command or getattr(server, "proxy_command", None)
                hostname, port = c.hostname, c.port
                username = c.username or server.username
            else:  # config file missing/unreadable/alias gone: use what we stored
                key_files = [server.identity_file] if server.identity_file else []
                proxy_jump = server.proxy_jump
                proxy_command = getattr(server, "proxy_command", None)
                hostname, port, username = server.hostname, server.port, server.username
        else:
            c = self._lookup_first_match(cfg, [server.hostname])
            port = server.port if server.port not in (None, 22) else c.port
            key_files = [server.identity_file] if server.identity_file else c.key_files
            proxy_jump = server.proxy_jump or c.proxy_jump
            proxy_command = getattr(server, "proxy_command", None) or c.proxy_command
            hostname = c.hostname
            username = server.username or c.username

        # OpenSSH: ProxyJump and ProxyCommand are mutually exclusive; jump wins here.
        if proxy_jump:
            proxy_command = None

        return _Target(
            hostname=hostname,
            port=port,
            username=username,
            key_files=[os.path.expanduser(k) for k in key_files],
            proxy_command=proxy_command,
            proxy_jump=proxy_jump,
            matched=c.matched,
        )

    def jump_hops(self) -> List[JumpHop]:
        """The resolved ProxyJump chain for this server (empty if direct)."""
        cfg = self._load_ssh_config()
        target = self._resolve_target(cfg)
        hops: List[JumpHop] = []
        if not target.proxy_jump:
            return hops
        for user, host, port in _parse_jump_spec(target.proxy_jump):
            hop = self._lookup(cfg, host)
            hops.append(
                JumpHop(
                    label=host,
                    username=user or hop.username or target.username or "",
                    hostname=hop.hostname,
                    port=port or hop.port,
                    has_key=bool(hop.key_files),
                )
            )
        return hops

    def describe_route(self) -> str:
        """Human-readable route (re-reads ssh config) for activity logging."""
        try:
            target = self._resolve_target(self._load_ssh_config())
        except Exception:
            return f"{self.server.hostname}:{self.server.port}"
        route = f"{target.hostname}:{target.port}"
        if target.proxy_jump:
            route += f" via ProxyJump {target.proxy_jump}"
        elif target.proxy_command:
            route += " via ProxyCommand"
        return route

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _new_client(
        self, callback: Optional[Callable[[str, str, str, bool], bool]]
    ) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        # Deliberately NOT loading any host keys into the client: our policy
        # checks known_hosts itself for every host (see _HostKeyPolicy).
        client.set_missing_host_key_policy(_HostKeyPolicy(self.known_hosts_path, callback))
        return client

    @staticmethod
    def _open_channel(
        via: paramiko.SSHClient, host: str, port: int, timeout: float, via_name: str
    ):
        transport = via.get_transport()
        if transport is None or not transport.is_active():
            raise ConnectionError_(f"Connection to jump host {via_name} was lost.")
        try:
            return transport.open_channel(
                "direct-tcpip", (host, port), ("127.0.0.1", 0), timeout=timeout
            )
        except (paramiko.ChannelException, paramiko.SSHException, EOFError) as exc:
            raise ConnectionError_(
                f"Jump host {via_name} could not forward to {host}:{port} "
                f"(AllowTcpForwarding disabled or target unreachable): {exc}"
            ) from exc

    def _build_socket(self, target: _Target, timeout: float, callback):
        """Return a socket-like object to tunnel through, or None for direct."""
        if target.proxy_command:
            try:
                return paramiko.ProxyCommand(target.proxy_command)
            except Exception as exc:
                raise ConnectionError_(f"ProxyCommand failed to start: {exc}") from exc

        if not target.proxy_jump:
            return None

        hops = _parse_jump_spec(target.proxy_jump)
        cfg = self._load_ssh_config()
        prev_client: Optional[paramiko.SSHClient] = None
        prev_name = ""

        for user, host, port in hops:
            hop = self._lookup(cfg, host)
            hop_user = user or hop.username or target.username
            hop_port = port or hop.port
            hop_name = f"{hop.hostname}:{hop_port}"

            client = self._connect_hop(
                prev_client, prev_name, hop, hop_user, hop_port, hop_name, timeout, callback
            )
            self._jump_clients.append(client)
            prev_client, prev_name = client, hop_name

        assert prev_client is not None
        return self._open_channel(prev_client, target.hostname, target.port, timeout, prev_name)

    def _connect_hop(
        self, prev_client, prev_name, hop: _Target, hop_user, hop_port, hop_name, timeout, callback
    ) -> paramiko.SSHClient:
        """Connect to one jump host.

        Like OpenSSH: try keys / ssh-agent first; if that isn't accepted, ask
        the password provider (GUI) for this hop's password and try again.
        The target's own password is never sent to an intermediate host.
        """
        provider = self._jump_password_provider
        password: Optional[str] = None

        for _attempt in (1, 2):
            sock = None
            if prev_client is not None:
                sock = self._open_channel(prev_client, hop.hostname, hop_port, timeout, prev_name)

            client = self._new_client(callback)
            try:
                client.connect(
                    hostname=hop.hostname,
                    port=hop_port,
                    username=hop_user,
                    password=password,
                    key_filename=hop.key_files or None,
                    allow_agent=True,
                    look_for_keys=True,
                    timeout=timeout,
                    banner_timeout=timeout,
                    auth_timeout=timeout,
                    sock=sock,
                )
                return client
            except paramiko.PasswordRequiredException as exc:
                client.close()
                raise ConnectionError_(
                    f"The key for jump host {hop_name} is passphrase-protected. "
                    "Load it into ssh-agent (or use an unencrypted key) for jump hosts."
                ) from exc
            except (HostKeyVerificationRequired, ConnectionError_):
                client.close()
                raise
            except paramiko.AuthenticationException:
                client.close()  # fall through to password handling below
            except paramiko.SSHException as exc:
                client.close()
                # Paramiko raises this (not AuthenticationException) when there
                # were no keys to try and no password was given.
                if "No authentication methods" not in str(exc):
                    raise ConnectionError_(f"SSH error on jump host {hop_name}: {exc}") from exc
            except OSError as exc:
                client.close()
                raise ConnectionError_(
                    f"Unable to connect to jump host {hop_name}. "
                    "Check network connectivity and SSH availability."
                ) from exc

            # Authentication was not accepted.
            if password is not None or provider is None:
                raise AuthenticationFailedError(
                    f"Authentication to jump host {hop_name} failed "
                    f"({'wrong password' if password is not None else 'no key accepted and no password available'})."
                )
            password = provider(hop_user, hop.hostname, hop_port)
            if password is None:
                raise ConnectionError_(f"Connection cancelled: no password given for jump host {hop_name}.")

        raise AuthenticationFailedError(f"Authentication to jump host {hop_name} failed.")

    def connect(
        self,
        password: Optional[str] = None,
        timeout: float = 10.0,
        allow_new_host_key: Optional[Callable[[str, str, str, bool], bool]] = None,
        jump_password_provider: Optional[JumpPasswordProvider] = None,
    ) -> None:
        """Establish the SSH connection and open an SFTP session.

        `allow_new_host_key(hostname, key_type, fingerprint, changed) -> bool`
        is an optional synchronous callback (typically backed by a GUI
        dialog) used to decide whether to trust a new/changed host key. It is
        also consulted for jump hosts. If omitted, unknown/changed host keys
        raise HostKeyVerificationRequired.
        """
        self.close()  # make sure no stale state from a previous attempt
        self._jump_password_provider = (
            jump_password_provider or SSHConnection.default_jump_password_provider
        )

        cfg = self._load_ssh_config()
        target = self._resolve_target(cfg)
        client = self._new_client(allow_new_host_key)

        connect_kwargs = dict(
            hostname=target.hostname,
            port=target.port,
            username=target.username,
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
            allow_agent=False,
            look_for_keys=False,
        )
        if password is not None:
            connect_kwargs["password"] = password
        if target.key_files:
            connect_kwargs["key_filename"] = target.key_files
            connect_kwargs["look_for_keys"] = True

        try:
            connect_kwargs["sock"] = self._build_socket(target, timeout, allow_new_host_key)
            client.connect(**connect_kwargs)
        except paramiko.AuthenticationException as exc:
            self._abort(client)
            raise AuthenticationFailedError(
                "The server rejected the supplied username/password."
            ) from exc
        except (HostKeyVerificationRequired, ConnectionError_, AuthenticationFailedError):
            self._abort(client)
            raise
        except paramiko.SSHException as exc:
            self._abort(client)
            raise ConnectionError_(f"SSH error: {exc}") from exc
        except OSError as exc:  # includes socket.timeout / NoValidConnectionsError
            self._abort(client)
            raise ConnectionError_(
                f"Unable to connect to {target.hostname}:{target.port}. "
                "Check network connectivity and SSH availability."
            ) from exc
        finally:
            connect_kwargs.pop("password", None)
            password = None  # drop our reference immediately

        self._finalize_connection(client)

    def _abort(self, client: paramiko.SSHClient) -> None:
        """Tear down a half-open connection (target + any jump hops)."""
        try:
            client.close()
        except Exception:
            pass
        self._close_jumps()

    def _close_jumps(self) -> None:
        for jc in reversed(self._jump_clients):
            try:
                jc.close()
            except Exception:
                pass
        self._jump_clients = []

    def _finalize_connection(self, client: paramiko.SSHClient) -> None:
        try:
            sftp = client.open_sftp()
        except paramiko.SSHException as exc:
            self._abort(client)
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
        """Close the SFTP session, SSH transport and any jump-host connections."""
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
        self._close_jumps()
        self.connected = False

    def __enter__(self) -> "SSHConnection":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
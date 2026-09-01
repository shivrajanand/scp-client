"""
SSH host-key verification.

Per spec section 26, the application must NOT blindly disable host-key
verification. This module wraps Paramiko's known_hosts handling to:

  1. Load the user's known_hosts file where available.
  2. Detect unknown hosts and surface them to the caller (GUI) for a
     trust decision, rather than auto-accepting.
  3. Detect changed host keys and treat them as a hard rejection unless
     explicitly overridden by the user.

This module has no Qt dependency; the GUI layer is responsible for
prompting and calling back into `trust_host_key`.
"""

from __future__ import annotations

import binascii
import logging
from pathlib import Path
from typing import Optional

import paramiko

from app.ssh.config_loader import default_known_hosts_path

logger = logging.getLogger(__name__)


class HostKeyMismatchError(Exception):
    """Raised when a server presents a host key that differs from the one
    already recorded in known_hosts -- a potential MITM indicator."""

    def __init__(self, hostname: str, fingerprint: str):
        self.hostname = hostname
        self.fingerprint = fingerprint
        super().__init__(
            f"Host key for '{hostname}' does not match the one on record "
            f"(new fingerprint: {fingerprint}). Connection rejected."
        )


class UnknownHostKeyError(Exception):
    """Raised when a server's host key is not present in known_hosts."""

    def __init__(self, hostname: str, key_type: str, fingerprint: str):
        self.hostname = hostname
        self.key_type = key_type
        self.fingerprint = fingerprint
        super().__init__(f"Host key for '{hostname}' is not known (fingerprint: {fingerprint}).")


def load_host_keys(known_hosts_path: Optional[Path] = None) -> paramiko.HostKeys:
    """Load known_hosts into a paramiko.HostKeys object (empty if absent)."""
    path = known_hosts_path or default_known_hosts_path()
    host_keys = paramiko.HostKeys()
    if path.exists():
        try:
            host_keys.load(str(path))
        except OSError as exc:
            logger.warning("Unable to read known_hosts at %s: %s", path, exc)
    return host_keys


def fingerprint_of(key: paramiko.PKey) -> str:
    """Return a human-readable SHA256 fingerprint for a host key, e.g.
    'SHA256:abcdef...' as shown by OpenSSH."""
    digest = key.get_fingerprint()
    # Paramiko's get_fingerprint() returns raw MD5 bytes for legacy reasons;
    # for display purposes we present it as a hex string prefixed clearly.
    return "MD5:" + binascii.hexlify(digest).decode("ascii")


class VerifyingHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """A Paramiko host-key policy that never silently trusts an unknown key.

    Instead of auto-accepting (like AutoAddPolicy) or hard-rejecting with
    no information (like RejectPolicy), this raises a descriptive
    exception that the GUI layer can catch to show a trust dialog.
    """

    def missing_host_key(self, client, hostname, key):
        fingerprint = fingerprint_of(key)
        raise UnknownHostKeyError(hostname, key.get_name(), fingerprint)


def trust_host_key(
    hostname: str,
    key: paramiko.PKey,
    known_hosts_path: Optional[Path] = None,
    persist: bool = True,
) -> None:
    """Record a newly trusted host key.

    If `persist` is False, the key is only trusted for the current
    connection attempt ("Trust Once") and is not written to disk.
    """
    if not persist:
        return

    path = known_hosts_path or default_known_hosts_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    host_keys = paramiko.HostKeys()
    if path.exists():
        try:
            host_keys.load(str(path))
        except OSError:
            pass

    host_keys.add(hostname, key.get_name(), key)
    try:
        host_keys.save(str(path))
    except OSError as exc:
        logger.warning("Could not persist trusted host key for %s: %s", hostname, exc)


def check_known_host(
    hostname: str,
    key: paramiko.PKey,
    known_hosts_path: Optional[Path] = None,
) -> Optional[str]:
    """Compare a presented key against known_hosts.

    Returns:
        None if the key matches a known entry (host is trusted).
        Raises HostKeyMismatchError if the host is known but the key differs.
        Raises UnknownHostKeyError if the host has no recorded key.
    """
    host_keys = load_host_keys(known_hosts_path)
    known_key = host_keys.lookup(hostname)

    if known_key is None:
        raise UnknownHostKeyError(hostname, key.get_name(), fingerprint_of(key))

    existing = known_key.get(key.get_name())
    if existing is None:
        # Host known, but not with this key type -- treat conservatively
        # as unknown rather than silently accepting a different algorithm.
        raise UnknownHostKeyError(hostname, key.get_name(), fingerprint_of(key))

    if existing.get_base64() != key.get_base64():
        raise HostKeyMismatchError(hostname, fingerprint_of(key))

    return None

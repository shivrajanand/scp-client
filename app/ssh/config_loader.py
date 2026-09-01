"""
SSH configuration parsing.

Reads the user's OpenSSH config (typically
`%USERPROFILE%\\.ssh\\config` on Windows) using Paramiko's SSHConfig
parser and exposes usable Server definitions.

Per spec section 13, at minimum Host / HostName / User / Port are
respected. The architecture leaves room to surface more options later
(e.g. IdentityFile) without changing the public interface.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional

import paramiko

from app.config.models import Server, ServerSource

logger = logging.getLogger(__name__)


def default_ssh_config_path() -> Path:
    """Return the expected location of the user's SSH config file."""
    userprofile = os.environ.get("USERPROFILE")
    home = Path(userprofile) if userprofile else Path.home()
    return home / ".ssh" / "config"


def default_known_hosts_path() -> Path:
    """Return the expected location of the user's known_hosts file."""
    userprofile = os.environ.get("USERPROFILE")
    home = Path(userprofile) if userprofile else Path.home()
    return home / ".ssh" / "known_hosts"


def load_ssh_config_servers(config_path: Optional[Path] = None) -> List[Server]:
    """Parse the SSH config file and return a list of Server objects.

    Returns an empty list (rather than raising) if the config file does
    not exist, since having no SSH config is a normal, expected state.
    """
    path = config_path or default_ssh_config_path()

    if not path.exists():
        logger.info("No SSH config file found at %s", path)
        return []

    ssh_config = paramiko.SSHConfig()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            ssh_config.parse(handle)
    except OSError as exc:
        logger.warning("Unable to read SSH config at %s: %s", path, exc)
        return []

    servers: List[Server] = []
    for host_alias in sorted(ssh_config.get_hostnames()):
        if host_alias == "*":
            # Wildcard blocks are applied to other hosts, not a server themselves.
            continue

        options = ssh_config.lookup(host_alias)

        hostname = options.get("hostname", host_alias)
        username = options.get("user")
        if not username:
            # A host with no configured user isn't usable without prompting
            # for one; skip it rather than guessing.
            logger.debug("Skipping SSH config host '%s': no User configured", host_alias)
            continue

        port_raw = options.get("port", "22")
        try:
            port = int(port_raw)
        except (TypeError, ValueError):
            port = 22

        identity_file = None
        identity_files = options.get("identityfile")
        if identity_files:
            # Paramiko returns a list; take the first as the primary key.
            identity_file = identity_files[0] if isinstance(identity_files, list) else identity_files

        servers.append(
            Server(
                name=host_alias,
                hostname=hostname,
                username=username,
                port=port,
                source=ServerSource.SSH_CONFIG,
                identity_file=identity_file,
            )
        )

    return servers

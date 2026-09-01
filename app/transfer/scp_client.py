"""
File transfer abstraction.

Wraps the `scp` library (SCP protocol over an existing Paramiko
transport) to perform single-file uploads and downloads, translating
low-level exceptions into the human-readable errors described in
spec section 25.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable, Optional

from scp import SCPClient, SCPException

from app.ssh.connection import ConnectionError_, SSHConnection

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int, int], None]  # (filename, bytes_transferred, total_bytes)


class TransferError(Exception):
    """A user-facing, human-readable transfer failure."""


class TransferCancelled(Exception):
    """Raised internally when a transfer is cancelled mid-flight."""


class ScpFileTransfer:
    """Performs a single upload or download over an established SSHConnection."""

    def __init__(self, connection: SSHConnection):
        self.connection = connection
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def upload(
        self,
        local_path: str,
        remote_destination_dir: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """Upload a single local file into a remote directory.

        Returns the final remote path of the uploaded file.
        """
        local = Path(local_path)
        if not local.exists():
            raise TransferError(f"The selected local file no longer exists:\n\n{local_path}")
        if not local.is_file():
            raise TransferError(f"The selected local path is not a file:\n\n{local_path}")

        remote_dir = remote_destination_dir.rstrip("/") or "/"
        remote_target = f"{remote_dir}/{local.name}"

        def _progress(filename, size, sent):
            if self._cancelled:
                raise TransferCancelled("Transfer cancelled by user.")
            if progress_callback:
                # scp's callback signature is (filename, size, sent); note
                # 'size' here is actually total bytes, 'sent' is progress.
                progress_callback(local.name, sent, size)

        try:
            if not self.connection.connected:
                raise TransferError("Not connected to the server.")
            with SCPClient(self.connection._client.get_transport(), progress=_progress) as scp:  # noqa: SLF001
                scp.put(str(local), remote_path=remote_target)
        except TransferCancelled:
            raise
        except PermissionError as exc:
            raise TransferError(
                "Permission denied. The current user does not have permission "
                "to write to this remote path."
            ) from exc
        except SCPException as exc:
            raise TransferError(self._humanize_scp_error(str(exc))) from exc
        except OSError as exc:
            raise TransferError(f"Transfer failed: {exc}") from exc

        return remote_target

    def download(
        self,
        remote_path: str,
        local_destination_dir: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """Download a single remote file into a local directory.

        Returns the final local path of the downloaded file.
        """
        if not self.connection.remote_file_exists(remote_path):
            raise TransferError(
                f"The selected remote file no longer exists:\n\n{remote_path}"
            )

        local_dir = Path(local_destination_dir)
        try:
            local_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise TransferError(
                "The selected destination directory does not exist or cannot be written to."
            ) from exc

        remote_filename = remote_path.rsplit("/", 1)[-1]
        local_target = local_dir / remote_filename

        def _progress(filename, size, sent):
            if self._cancelled:
                raise TransferCancelled("Transfer cancelled by user.")
            if progress_callback:
                progress_callback(remote_filename, sent, size)

        try:
            with SCPClient(self.connection._client.get_transport(), progress=_progress) as scp:  # noqa: SLF001
                scp.get(remote_path, local_path=str(local_target))
        except TransferCancelled:
            # Best-effort cleanup of a partial file.
            try:
                if local_target.exists():
                    local_target.unlink()
            except OSError:
                pass
            raise
        except PermissionError as exc:
            raise TransferError(
                "Permission denied. The current user does not have permission "
                "to write to the local destination."
            ) from exc
        except SCPException as exc:
            raise TransferError(self._humanize_scp_error(str(exc))) from exc
        except OSError as exc:
            raise TransferError(f"Transfer failed: {exc}") from exc

        return str(local_target)

    @staticmethod
    def _humanize_scp_error(message: str) -> str:
        lowered = message.lower()
        if "no such file" in lowered:
            return "The selected remote file no longer exists."
        if "permission denied" in lowered:
            return "Permission denied. The current user does not have permission to access this file/path."
        return f"Transfer failed: {message}"

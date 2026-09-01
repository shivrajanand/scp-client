"""
Background transfer worker.

Runs the SSH connection + SCP transfer on a QThread so the GUI never
blocks (spec section 22). Emits Qt signals for progress, log lines,
success, and failure; supports cooperative cancellation.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from PySide6.QtCore import QObject, QThread, Signal

from app.config.models import TransferDirection, TransferRequest
from app.ssh.connection import (
    AuthenticationFailedError,
    ConnectionError_,
    HostKeyVerificationRequired,
    SSHConnection,
)
from app.transfer.progress import ProgressTracker
from app.transfer.scp_client import ScpFileTransfer, TransferCancelled, TransferError

logger = logging.getLogger(__name__)


class TransferWorker(QObject):
    """
    Runs on a background QThread. The GUI creates one instance per
    transfer attempt and moves it to a QThread before calling `run()`.
    """

    log_message = Signal(str)
    progress_updated = Signal(str, int, int, float, float, float)  # filename, sent, total, pct, speed, eta
    transfer_succeeded = Signal(str)   # resulting path
    transfer_failed = Signal(str)      # human-readable error message
    transfer_cancelled = Signal()
    host_key_verification_needed = Signal(str, str, str, bool)  # hostname, key_type, fingerprint, changed

    def __init__(
        self,
        request: TransferRequest,
        password: Optional[str],
        host_key_decision_provider=None,
    ):
        super().__init__()
        self.request = request
        self._password = password
        self._host_key_decision_provider = host_key_decision_provider
        self._scp: Optional[ScpFileTransfer] = None
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True
        if self._scp is not None:
            self._scp.cancel()

    def run(self) -> None:
        """Entry point invoked on the worker thread."""
        server = self.request.server
        connection = SSHConnection(server)

        password: Optional[str] = None
        try:
            self.log_message.emit(f"Connecting to {server.name} ({server.hostname}:{server.port})...")

            password = self._password
            connection.connect(
                password=password,
                allow_new_host_key=self._host_key_decision_provider,
            )

            self.log_message.emit("Authentication successful")

            if self._cancel_requested:
                self.transfer_cancelled.emit()
                return

            self._scp = ScpFileTransfer(connection)
            tracker = ProgressTracker(filename=self._source_filename())

            def progress_callback(filename: str, sent: int, total: int) -> None:
                snapshot = tracker.update(sent, total)
                self.progress_updated.emit(
                    filename,
                    sent,
                    total,
                    snapshot.percent,
                    snapshot.speed_bytes_per_sec,
                    snapshot.eta_seconds,
                )

            if self.request.direction == TransferDirection.UPLOAD:
                self.log_message.emit(f"Starting upload: {self.request.source_path}")
                result_path = self._scp.upload(
                    self.request.source_path,
                    self.request.destination_path,
                    progress_callback=progress_callback,
                )
            else:
                self.log_message.emit(f"Starting download: {self.request.source_path}")
                result_path = self._scp.download(
                    self.request.source_path,
                    self.request.destination_path,
                    progress_callback=progress_callback,
                )

            self.log_message.emit("Transfer completed successfully")
            self.transfer_succeeded.emit(result_path)

        except TransferCancelled:
            self.log_message.emit("Transfer cancelled")
            self.transfer_cancelled.emit()
        except AuthenticationFailedError as exc:
            self.log_message.emit("Authentication failed")
            self.transfer_failed.emit(
                "Authentication failed.\n\nThe server rejected the supplied username/password."
            )
        except HostKeyVerificationRequired as exc:
            self.host_key_verification_needed.emit(
                exc.hostname, exc.key_type, exc.fingerprint, exc.changed
            )
            self.transfer_failed.emit(
                "Host key verification is required before this connection can proceed."
            )
        except ConnectionError_ as exc:
            self.log_message.emit("Connection failed")
            self.transfer_failed.emit(str(exc))
        except TransferError as exc:
            self.log_message.emit("Transfer failed")
            self.transfer_failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - safety net for unexpected errors
            logger.exception("Unexpected error during transfer")
            self.transfer_failed.emit(f"An unexpected error occurred: {exc}")
        finally:
            # Discard the password from local scope as soon as possible.
            password = None
            connection.close()

    def _source_filename(self) -> str:
        path = self.request.source_path.replace("\\", "/")
        return path.rstrip("/").rsplit("/", 1)[-1] or path


def run_transfer_in_thread(
    request: TransferRequest,
    password: Optional[str],
    host_key_decision_provider=None,
) -> tuple[QThread, TransferWorker]:
    """Convenience helper: creates the worker + thread and wires them up.

    The caller is responsible for connecting to the worker's signals
    *before* starting the returned thread, and for keeping references to
    both objects alive for the duration of the transfer.
    """
    thread = QThread()
    worker = TransferWorker(request, password, host_key_decision_provider)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.transfer_succeeded.connect(thread.quit)
    worker.transfer_failed.connect(thread.quit)
    worker.transfer_cancelled.connect(thread.quit)

    return thread, worker

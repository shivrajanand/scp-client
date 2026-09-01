"""
Main application window.

Implements the core workflow from spec sections 7-11: pick a direction,
pick a server, pick source/destination, transfer, watch progress, read
the activity log.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFrame,
)

from app.config.manager import ConfigManager
from app.config.models import (
    AppPreferences,
    Server,
    ServerSource,
    TransferDirection,
    TransferRequest,
)
from app.gui.password_dialog import PasswordDialog
from app.gui.remote_browser import RemoteBrowserDialog
from app.gui.server_manager import ServerManagerDialog
from app.gui.styles import stylesheet_for_theme
from app.ssh.config_loader import load_ssh_config_servers
from app.ssh.connection import SSHConnection
from app.ssh.host_keys import trust_host_key
from app.transfer.progress import format_bytes, format_eta, format_speed
from app.transfer.worker import TransferWorker, run_transfer_in_thread
from app.utils.paths import get_downloads_directory, get_windows_username, remote_home_directory

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SCP Transfer")
        self.resize(680, 640)

        self.config_manager = ConfigManager()
        self.preferences: AppPreferences = self.config_manager.load_preferences()
        self.manual_servers: List[Server] = self.config_manager.load_servers()
        self.ssh_config_servers: List[Server] = load_ssh_config_servers()

        self.direction: TransferDirection = TransferDirection.UPLOAD
        self._active_thread = None
        self._active_worker: Optional[TransferWorker] = None
        self._browsed_connection: Optional[SSHConnection] = None

        self._build_ui()
        self._apply_theme(self.preferences.theme)
        self._refresh_server_dropdown()
        self._on_direction_changed(TransferDirection.UPLOAD)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # --- Header row -------------------------------------------------
        header_row = QHBoxLayout()
        title = QLabel("SCP Transfer")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        header_row.addWidget(title)
        header_row.addStretch()
        self.settings_button = QPushButton("⚙ Servers")
        self.settings_button.clicked.connect(self._open_server_manager)
        header_row.addWidget(self.settings_button)
        self.theme_button = QPushButton("Toggle Theme")
        self.theme_button.clicked.connect(self._toggle_theme)
        header_row.addWidget(self.theme_button)
        root.addLayout(header_row)

        # --- Direction ----------------------------------------------------
        root.addWidget(self._section_label("TRANSFER"))
        direction_row = QHBoxLayout()
        self.upload_button = QPushButton("↑ Send to Server")
        self.download_button = QPushButton("↓ Fetch from Server")
        for btn in (self.upload_button, self.download_button):
            btn.setObjectName("DirectionButton")
            btn.setCheckable(True)
            direction_row.addWidget(btn)
        self.upload_button.setChecked(True)
        self.upload_button.clicked.connect(lambda: self._on_direction_changed(TransferDirection.UPLOAD))
        self.download_button.clicked.connect(lambda: self._on_direction_changed(TransferDirection.DOWNLOAD))
        root.addLayout(direction_row)

        # --- Server -------------------------------------------------------
        root.addWidget(self._section_label("SERVER"))
        self.server_combo = QComboBox()
        self.server_combo.currentIndexChanged.connect(self._on_server_changed)
        root.addWidget(self.server_combo)

        # --- Source ---------------------------------------------------------
        self.source_label = self._section_label("SOURCE")
        root.addWidget(self.source_label)
        source_row = QHBoxLayout()
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("No file selected")
        self.source_browse_button = QPushButton("Browse...")
        self.source_browse_button.clicked.connect(self._on_browse_source)
        source_row.addWidget(self.source_edit)
        source_row.addWidget(self.source_browse_button)
        root.addLayout(source_row)

        # --- Destination ------------------------------------------------
        self.destination_label = self._section_label("DESTINATION")
        root.addWidget(self.destination_label)
        dest_row = QHBoxLayout()
        self.destination_edit = QLineEdit()
        self.destination_browse_button = QPushButton("Browse...")
        self.destination_browse_button.clicked.connect(self._on_browse_destination)
        dest_row.addWidget(self.destination_edit)
        dest_row.addWidget(self.destination_browse_button)
        root.addLayout(dest_row)

        # --- Transfer button ----------------------------------------------
        self.transfer_button = QPushButton("TRANSFER")
        self.transfer_button.setObjectName("PrimaryButton")
        self.transfer_button.clicked.connect(self._on_transfer_clicked)
        root.addWidget(self.transfer_button)

        self.cancel_button = QPushButton("Cancel Transfer")
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        self.cancel_button.setVisible(False)
        root.addWidget(self.cancel_button)

        # --- Progress -------------------------------------------------------
        root.addWidget(self._section_label("PROGRESS"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        root.addWidget(self.progress_bar)

        self.progress_detail_label = QLabel("")
        root.addWidget(self.progress_detail_label)

        # --- Activity log -----------------------------------------------
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(separator)
        root.addWidget(self._section_label("ACTIVITY"))
        self.activity_log = QPlainTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setMaximumBlockCount(2000)
        root.addWidget(self.activity_log, stretch=1)

        self.statusBar().showMessage("Ready")

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionLabel")
        return label

    def _apply_theme(self, theme: str) -> None:
        self.preferences.theme = theme
        self.setStyleSheet(stylesheet_for_theme(theme))

    def _toggle_theme(self) -> None:
        new_theme = "light" if self.preferences.theme == "dark" else "dark"
        self._apply_theme(new_theme)
        self._save_preferences()

    # ------------------------------------------------------------------
    # Server list management
    # ------------------------------------------------------------------
    def _refresh_server_dropdown(self) -> None:
        self.server_combo.blockSignals(True)
        self.server_combo.clear()

        if self.ssh_config_servers:
            self.server_combo.addItem("── SSH Config ──")
            self.server_combo.model().item(self.server_combo.count() - 1).setEnabled(False)
            for server in self.ssh_config_servers:
                self.server_combo.addItem(server.display_label(), userData=server)

        enabled_manual = [s for s in self.manual_servers if s.enabled]
        if enabled_manual:
            self.server_combo.addItem("── Saved Servers ──")
            self.server_combo.model().item(self.server_combo.count() - 1).setEnabled(False)
            for server in enabled_manual:
                self.server_combo.addItem(server.display_label(), userData=server)

        self.server_combo.blockSignals(False)

        # Restore last-selected server if possible.
        if self.preferences.last_server_name:
            for i in range(self.server_combo.count()):
                data = self.server_combo.itemData(i)
                if isinstance(data, Server) and data.name == self.preferences.last_server_name:
                    self.server_combo.setCurrentIndex(i)
                    break
        self._on_server_changed()

    def _current_server(self) -> Optional[Server]:
        data = self.server_combo.currentData()
        return data if isinstance(data, Server) else None

    def _on_server_changed(self) -> None:
        server = self._current_server()
        if server:
            self.preferences.last_server_name = server.name
        if self.direction == TransferDirection.UPLOAD and server:
            self.destination_edit.setText(remote_home_directory(server.username))

    def _open_server_manager(self) -> None:
        dialog = ServerManagerDialog(self.manual_servers, parent=self)
        if dialog.exec():
            self.manual_servers = dialog.servers
            try:
                self.config_manager.save_servers(self.manual_servers)
            except Exception as exc:
                QMessageBox.warning(self, "Server Manager", f"Could not save servers: {exc}")
            self._refresh_server_dropdown()

    # ------------------------------------------------------------------
    # Direction handling
    # ------------------------------------------------------------------
    def _on_direction_changed(self, direction: TransferDirection) -> None:
        self.direction = direction
        self.upload_button.setChecked(direction == TransferDirection.UPLOAD)
        self.download_button.setChecked(direction == TransferDirection.DOWNLOAD)

        self.source_edit.clear()
        self.destination_edit.clear()

        if direction == TransferDirection.UPLOAD:
            self.source_label.setText("SOURCE (Local File)")
            self.destination_label.setText("DESTINATION (Remote Directory)")
            self.source_browse_button.setText("Browse...")
            self.destination_browse_button.setText("Browse...")
            server = self._current_server()
            if server:
                self.destination_edit.setText(remote_home_directory(server.username))
        else:
            self.source_label.setText("SOURCE (Remote File)")
            self.destination_label.setText("DESTINATION (Local Folder)")
            self.source_browse_button.setText("Browse Remote...")
            self.destination_browse_button.setText("Browse Folder...")
            self.destination_edit.setText(str(get_downloads_directory()))
            self.source_edit.setPlaceholderText("Use 'Browse Remote...' to select a file")

    # ------------------------------------------------------------------
    # Source / destination selection
    # ------------------------------------------------------------------
    def _on_browse_source(self) -> None:
        if self.direction == TransferDirection.UPLOAD:
            path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload")
            if path:
                self.source_edit.setText(path)
        else:
            self._browse_remote_for_source()

    def _browse_remote_for_source(self) -> None:
        server = self._current_server()
        if not server:
            QMessageBox.information(self, "Fetch from Server", "Select a server first.")
            return

        connection = self._connect_with_prompt(server)
        if connection is None:
            return

        start_path = self.destination_edit.text() or "."
        try:
            home = connection.resolve_home_directory()
        except Exception:
            home = remote_home_directory(server.username)
        start_path = home

        browser = RemoteBrowserDialog(connection, start_path, parent=self)
        if browser.exec() and browser.selected_file_path:
            self.source_edit.setText(browser.selected_file_path)
            self._log(f"Selected remote file: {browser.selected_file_path}")

        connection.close()

    def _on_browse_destination(self) -> None:
        if self.direction == TransferDirection.UPLOAD:
            self._browse_remote_for_destination()
        else:
            folder = QFileDialog.getExistingDirectory(
                self, "Select Download Destination", self.destination_edit.text()
            )
            if folder:
                self.destination_edit.setText(folder)

    def _browse_remote_for_destination(self) -> None:
        server = self._current_server()
        if not server:
            QMessageBox.information(self, "Send to Server", "Select a server first.")
            return

        connection = self._connect_with_prompt(server)
        if connection is None:
            return

        try:
            home = connection.resolve_home_directory()
        except Exception:
            home = remote_home_directory(server.username)

        browser = RemoteBrowserDialog(connection, home, parent=self)
        # We reuse the file browser for directory navigation; the current
        # path shown becomes the destination directory when the user
        # cancels out after navigating (a lightweight directory picker).
        browser.select_button.setText("Use This Folder")
        browser.select_button.clicked.disconnect()
        browser.select_button.clicked.connect(lambda: self._accept_remote_dir(browser))
        if browser.exec() and browser.selected_file_path:
            self.destination_edit.setText(browser.selected_file_path)

        connection.close()

    @staticmethod
    def _accept_remote_dir(browser: RemoteBrowserDialog) -> None:
        browser.selected_file_path = browser.current_path
        browser.accept()

    def _connect_with_prompt(self, server: Server) -> Optional[SSHConnection]:
        password = PasswordDialog.prompt(server.name, server.username, server.hostname, self)
        if password is None:
            return None

        connection = SSHConnection(server)
        try:
            self._log(f"Connecting to {server.hostname}:{server.port}")

            def on_new_key(hostname, key_type, fingerprint, changed):
                return self._prompt_host_key_trust(hostname, key_type, fingerprint, changed, connection)

            connection.connect(password=password, allow_new_host_key=on_new_key)
            self._log("Authentication successful")
            return connection
        except Exception as exc:
            QMessageBox.critical(self, "Connection Failed", str(exc))
            return None
        finally:
            password = None

    def _prompt_host_key_trust(self, hostname, key_type, fingerprint, changed, connection) -> bool:
        if changed:
            text = (
                f"WARNING: The host key for {hostname} has CHANGED.\n\n"
                f"New fingerprint: {fingerprint}\n\n"
                "This could indicate a security issue. Only continue if you are "
                "certain the server's key was legitimately changed."
            )
        else:
            text = (
                f"The server's host key is not known.\n\nHost: {hostname}\n"
                f"Fingerprint: {fingerprint}\n\nDo you trust this host?"
            )
        box = QMessageBox(self)
        box.setWindowTitle("Host Key Verification")
        box.setText(text)
        trust_once = box.addButton("Trust Once", QMessageBox.ButtonRole.AcceptRole)
        trust = box.addButton("Trust && Save", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked is trust_once:
            return True
        if clicked is trust:
            # Persistence is handled after a successful connect via a
            # follow-up call, since we don't have the raw PKey here.
            self._pending_host_key_persist = True
            return True
        return False

    # ------------------------------------------------------------------
    # Transfer
    # ------------------------------------------------------------------
    def _validate_transfer(self) -> Optional[str]:
        server = self._current_server()
        if not server:
            return "Please select a server."

        source = self.source_edit.text().strip()
        destination = self.destination_edit.text().strip()

        if self.direction == TransferDirection.UPLOAD:
            if not source:
                return "Please select a local file to upload."
            if not Path(source).exists():
                return f"The selected local file no longer exists:\n\n{source}"
            if not Path(source).is_file():
                return "The selected local path is not a file."
            if not destination:
                return "Please specify a remote destination directory."
        else:
            if not source:
                return "Please select a remote file to download."
            if not destination:
                return "Please select a local destination folder."

        return None

    def _on_transfer_clicked(self) -> None:
        error = self._validate_transfer()
        if error:
            QMessageBox.warning(self, "Cannot Transfer", error)
            return

        server = self._current_server()
        source = self.source_edit.text().strip()
        destination = self.destination_edit.text().strip()

        if self.direction == TransferDirection.DOWNLOAD:
            local_target = Path(destination) / source.rsplit("/", 1)[-1]
            if local_target.exists() and not self._confirm_overwrite(str(local_target)):
                return

        request = TransferRequest(
            direction=self.direction,
            server=server,
            source_path=source,
            destination_path=destination,
        )

        password = PasswordDialog.prompt(server.name, server.username, server.hostname, self)
        if password is None:
            return

        def host_key_decision(hostname, key_type, fingerprint, changed) -> bool:
            return self._prompt_host_key_trust(hostname, key_type, fingerprint, changed, None)

        thread, worker = run_transfer_in_thread(request, password, host_key_decision)
        self._active_thread = thread
        self._active_worker = worker

        worker.log_message.connect(self._log)
        worker.progress_updated.connect(self._on_progress_updated)
        worker.transfer_succeeded.connect(self._on_transfer_succeeded)
        worker.transfer_failed.connect(self._on_transfer_failed)
        worker.transfer_cancelled.connect(self._on_transfer_cancelled_ui)
        thread.finished.connect(self._on_thread_finished)

        self._set_transfer_in_progress(True)
        self.progress_bar.setValue(0)
        self.progress_detail_label.setText("")
        self._log(f"Selected server: {server.name}")

        thread.start()

    def _confirm_overwrite(self, path: str) -> bool:
        result = QMessageBox.question(
            self,
            "File Already Exists",
            f"The destination file already exists.\n\n{path}\n\nDo you want to replace it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _on_cancel_clicked(self) -> None:
        if self._active_worker:
            self._active_worker.cancel()
            self._log("Cancellation requested...")

    def _set_transfer_in_progress(self, in_progress: bool) -> None:
        self.transfer_button.setEnabled(not in_progress)
        self.cancel_button.setVisible(in_progress)
        self.server_combo.setEnabled(not in_progress)
        self.upload_button.setEnabled(not in_progress)
        self.download_button.setEnabled(not in_progress)

    def _on_progress_updated(self, filename, sent, total, percent, speed, eta) -> None:
        self.progress_bar.setValue(int(percent))
        self.progress_detail_label.setText(
            f"{format_bytes(sent)} / {format_bytes(total)}     "
            f"{format_speed(speed)}     ETA {format_eta(eta)}"
        )
        self.statusBar().showMessage(f"Transferring {filename}: {percent:.0f}%")

    def _on_transfer_succeeded(self, result_path: str) -> None:
        self.progress_bar.setValue(100)
        self.statusBar().showMessage("Transfer completed successfully")
        QMessageBox.information(self, "Transfer Complete", f"File transferred successfully:\n\n{result_path}")

    def _on_transfer_failed(self, message: str) -> None:
        self.statusBar().showMessage("Transfer failed")
        QMessageBox.critical(self, "Transfer Failed", message)

    def _on_transfer_cancelled_ui(self) -> None:
        self.statusBar().showMessage("Transfer cancelled")

    def _on_thread_finished(self) -> None:
        self._set_transfer_in_progress(False)
        self._active_thread = None
        self._active_worker = None
        self._save_preferences()

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------
    def _log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.activity_log.appendPlainText(f"{timestamp}  {message}")
        logger.info(message)

    def _save_preferences(self) -> None:
        try:
            self.config_manager.save_preferences(self.preferences)
        except Exception as exc:
            logger.warning("Could not save preferences: %s", exc)

    def closeEvent(self, event) -> None:
        self._save_preferences()
        super().closeEvent(event)

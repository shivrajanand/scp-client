"""
Manual server management UI.

Per spec sections 14/29, this dialog lets the user add, edit, delete,
enable/disable, and test-connect manually configured servers. There is
deliberately no password field that gets saved with the server (spec
section 14): "Password: [ NOT STORED ]".
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QCheckBox,
)

from app.config.models import Server, ServerSource
from app.ssh.connection import AuthenticationFailedError, ConnectionError_, SSHConnection


class ServerEditDialog(QDialog):
    """Add/Edit dialog for a single manual server definition."""

    def __init__(self, server: Optional[Server] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Server" if server else "Add Server")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(server.name if server else "")
        self.hostname_edit = QLineEdit(server.hostname if server else "")
        self.username_edit = QLineEdit(server.username if server else "")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(server.port if server else 22)

        not_stored_label = QLabel("NOT STORED")
        not_stored_label.setStyleSheet("color: #9aa0a6; font-style: italic;")

        form.addRow("Name", self.name_edit)
        form.addRow("Hostname / IP", self.hostname_edit)
        form.addRow("Username", self.username_edit)
        form.addRow("Port", self.port_spin)
        form.addRow("Password", not_stored_label)

        layout.addLayout(form)

        hint = QLabel("You will be prompted for the password each time you connect.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9aa0a6;")
        layout.addWidget(hint)

        button_row = QHBoxLayout()
        self.test_button = QPushButton("Test")
        self.test_button.clicked.connect(self._on_test)
        button_row.addWidget(self.test_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.result_server: Optional[Server] = None

    def _build_server(self) -> Server:
        return Server(
            name=self.name_edit.text().strip(),
            hostname=self.hostname_edit.text().strip(),
            username=self.username_edit.text().strip(),
            port=self.port_spin.value(),
            source=ServerSource.MANUAL,
        )

    def _validate(self) -> Optional[str]:
        if not self.name_edit.text().strip():
            return "Name is required."
        if not self.hostname_edit.text().strip():
            return "Hostname / IP is required."
        if not self.username_edit.text().strip():
            return "Username is required."
        return None

    def _on_save(self) -> None:
        error = self._validate()
        if error:
            QMessageBox.warning(self, "Invalid Server", error)
            return
        self.result_server = self._build_server()
        self.accept()

    def _on_test(self) -> None:
        error = self._validate()
        if error:
            QMessageBox.warning(self, "Invalid Server", error)
            return

        from app.gui.password_dialog import PasswordDialog

        server = self._build_server()
        password = PasswordDialog.prompt(server.name, server.username, server.hostname, self)
        if password is None:
            return

        self.test_button.setEnabled(False)
        self.test_button.setText("Testing...")
        try:
            connection = SSHConnection(server)
            try:
                connection.connect(password=password, allow_new_host_key=lambda *a: True)
                QMessageBox.information(self, "Connection Test", "Connection successful.")
            finally:
                connection.close()
        except AuthenticationFailedError:
            QMessageBox.critical(
                self, "Connection Test",
                "Authentication failed.\n\nThe server rejected the supplied username/password.",
            )
        except ConnectionError_ as exc:
            QMessageBox.critical(self, "Connection Test", str(exc))
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Connection Test", f"Unexpected error: {exc}")
        finally:
            password = None
            self.test_button.setEnabled(True)
            self.test_button.setText("Test")


class ServerManagerDialog(QDialog):
    """Lists manual servers with add/edit/delete/enable controls."""

    def __init__(self, servers: List[Server], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Server Manager")
        self.setMinimumSize(420, 380)

        # Work on a copy; caller reads .servers back out after exec().
        self.servers: List[Server] = [s for s in servers if s.source == ServerSource.MANUAL]

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Manually Configured Servers"))

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.list_widget)
        self._refresh_list()

        button_row = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.edit_button = QPushButton("Edit")
        self.delete_button = QPushButton("Delete")
        self.toggle_button = QPushButton("Enable/Disable")
        for btn in (self.add_button, self.edit_button, self.delete_button, self.toggle_button):
            button_row.addWidget(btn)
        layout.addLayout(button_row)

        self.add_button.clicked.connect(self._on_add)
        self.edit_button.clicked.connect(self._on_edit)
        self.delete_button.clicked.connect(self._on_delete)
        self.toggle_button.clicked.connect(self._on_toggle)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.accept)
        close_buttons.accepted.connect(self.accept)
        layout.addWidget(close_buttons)

    def _refresh_list(self) -> None:
        self.list_widget.clear()
        for server in self.servers:
            label = server.display_label()
            if not server.enabled:
                label += "  [disabled]"
            item = QListWidgetItem(label)
            self.list_widget.addItem(item)

    def _selected_index(self) -> Optional[int]:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.servers):
            return None
        return row

    def _on_add(self) -> None:
        dialog = ServerEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_server:
            if any(s.name == dialog.result_server.name for s in self.servers):
                QMessageBox.warning(self, "Duplicate Name", "A server with this name already exists.")
                return
            self.servers.append(dialog.result_server)
            self._refresh_list()

    def _on_edit(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        dialog = ServerEditDialog(server=self.servers[index], parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_server:
            dialog.result_server.enabled = self.servers[index].enabled
            self.servers[index] = dialog.result_server
            self._refresh_list()

    def _on_delete(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        server = self.servers[index]
        confirm = QMessageBox.question(
            self, "Delete Server", f"Delete server '{server.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            del self.servers[index]
            self._refresh_list()

    def _on_toggle(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        self.servers[index].enabled = not self.servers[index].enabled
        self._refresh_list()

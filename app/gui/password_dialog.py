"""
Secure password prompt dialog.

Per spec section 16 / `gui/password_dialog.py` responsibilities:
  - Request a password from the user at connection time.
  - Mask the password input.
  - Return the password to the connection layer.
  - Never persist the password anywhere.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class PasswordDialog(QDialog):
    """Modal dialog that prompts for a password for a specific server/user."""

    def __init__(self, server_name: str, username: str, hostname: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Authentication Required")
        self.setModal(True)
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)

        info_label = QLabel(f"Server: {server_name}\nHost: {hostname}\nUser: {username}")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        form = QFormLayout()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.returnPressed.connect(self.accept)
        form.addRow("Password:", self.password_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Connect")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.password_edit.setFocus()

    def password(self) -> str:
        return self.password_edit.text()

    def clear_password(self) -> None:
        """Explicitly scrub the field's contents from the widget."""
        self.password_edit.clear()

    @staticmethod
    def prompt(server_name: str, username: str, hostname: str, parent=None) -> Optional[str]:
        """Show the dialog and return the entered password, or None if cancelled.

        The dialog's own field is cleared immediately after reading the
        value, and the dialog is scheduled for deletion so the masked
        text does not linger in memory longer than necessary.
        """
        dialog = PasswordDialog(server_name, username, hostname, parent)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            value = dialog.password()
        else:
            value = None
        dialog.clear_password()
        dialog.deleteLater()
        return value

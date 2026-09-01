"""
Remote filesystem navigation dialog.

Per spec sections 17/18: read-only browsing, navigate into/up
directories, refresh, select a file (not a directory) for transfer.
No delete/rename/move/chmod/chown/execute/shell functionality exists
here or anywhere else in the application.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.config.models import RemoteEntry
from app.ssh.connection import ConnectionError_, SSHConnection
from app.transfer.progress import format_bytes
from app.utils.paths import remote_join, remote_parent


class RemoteBrowserDialog(QDialog):
    """Read-only remote directory browser used to pick a file to download."""

    def __init__(self, connection: SSHConnection, start_path: str, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.current_path = start_path
        self.selected_file_path: Optional[str] = None

        self.setWindowTitle(f"Remote Browser - {connection.server.name}")
        self.setMinimumSize(520, 420)

        layout = QVBoxLayout(self)

        header = QLabel(f"Remote: {connection.server.name}    User: {connection.server.username}")
        layout.addWidget(header)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Path:"))
        self.path_edit = QLineEdit(self.current_path)
        self.path_edit.returnPressed.connect(self._navigate_to_typed_path)
        path_row.addWidget(self.path_edit)
        layout.addLayout(path_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Size"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_row_activated)
        layout.addWidget(self.table)

        nav_row = QHBoxLayout()
        self.up_button = QPushButton("Up")
        self.refresh_button = QPushButton("Refresh")
        self.select_button = QPushButton("Select File")
        self.up_button.clicked.connect(self._go_up)
        self.refresh_button.clicked.connect(self._refresh)
        self.select_button.clicked.connect(self._on_select_clicked)
        nav_row.addWidget(self.up_button)
        nav_row.addWidget(self.refresh_button)
        nav_row.addStretch()
        nav_row.addWidget(self.select_button)
        layout.addLayout(nav_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._entries: List[RemoteEntry] = []
        self._refresh()

    def _navigate_to_typed_path(self) -> None:
        self.current_path = self.path_edit.text().strip() or self.current_path
        self._refresh()

    def _refresh(self) -> None:
        try:
            entries = self.connection.list_directory(self.current_path)
        except ConnectionError_ as exc:
            QMessageBox.critical(self, "Remote Browser", str(exc))
            return

        self._entries = entries
        self.path_edit.setText(self.current_path)
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            name_item = QTableWidgetItem(("📁 " if entry.is_dir else "📄 ") + entry.name)
            type_item = QTableWidgetItem("Directory" if entry.is_dir else "File")
            size_text = "" if entry.is_dir or entry.size is None else format_bytes(entry.size)
            size_item = QTableWidgetItem(size_text)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, type_item)
            self.table.setItem(row, 2, size_item)

    def _go_up(self) -> None:
        self.current_path = remote_parent(self.current_path)
        self._refresh()

    def _on_row_activated(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._entries):
            return
        entry = self._entries[row]
        if entry.is_dir:
            self.current_path = entry.path if entry.path.endswith("/") else entry.path + "/"
            self._refresh()
        else:
            self.selected_file_path = entry.path
            self.accept()

    def _on_select_clicked(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._entries):
            QMessageBox.information(self, "Remote Browser", "Select a file first.")
            return
        entry = self._entries[row]
        if entry.is_dir:
            QMessageBox.information(
                self, "Remote Browser", "Directories cannot be selected for transfer in this version."
            )
            return
        self.selected_file_path = entry.path
        self.accept()

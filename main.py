#!/usr/bin/env python3
"""
SCP Transfer Client - entry point.

Initializes the Qt application, sets up logging, loads configuration,
and shows the main window.
"""

import sys

from PySide6.QtWidgets import QApplication

from app.config.manager import get_app_data_dir
from app.gui.main_window import MainWindow
from app.utils.logging import setup_logging


def main() -> int:
    setup_logging(log_dir=get_app_data_dir())

    app = QApplication(sys.argv)
    app.setApplicationName("SCP Transfer Client")
    app.setOrganizationName("SCPTransferClient")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

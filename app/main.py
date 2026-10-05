"""Application entry point for Cmdly."""

import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import ConfigManager
from app.ui.main_window import MainWindow
from app.ui.icons import get_icon


def main():
    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Cmdly")
    app.setOrganizationName("Cmdly")
    app.setApplicationDisplayName("Cmdly Launcher")

    # Set Application Icon
    app_icon = get_icon("cpu", "#3b82f6", 32)
    app.setWindowIcon(app_icon)

    config_manager = ConfigManager()
    window = MainWindow(config_manager)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

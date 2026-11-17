#!/usr/bin/env python3
"""Entry point for CachyOS Softmgr."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

from icons import make_icon
from main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("CachyOS-Softmgr")
    app.setApplicationDisplayName("CachyOS Softmgr")
    app.setOrganizationName("CachyOS")
    app.setOrganizationDomain("cachyos.org")
    app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    app.setWindowIcon(make_icon("brand", size=128))
    if hasattr(app, "setDesktopFileName"):
        app.setDesktopFileName("cachyos-softmgr")

    families = set(QFontDatabase.families())
    preferred = next((name for name in ("Inter", "Noto Sans", "Ubuntu") if name in families), "")
    ui_font = QFont(preferred or app.font().family(), 11)
    ui_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.15)
    ui_font.setWordSpacing(0.35)
    app.setFont(ui_font)

    window = MainWindow(app)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

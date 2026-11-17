"""Qt workers for package inventory, update checks, and transactions."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

import backend
import disk_report
from backend import Package


class LoadPackagesWorker(QThread):
    packages_loaded = pyqtSignal(object)
    error_occurred = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, force_refresh: bool = True, parent=None):
        super().__init__(parent)
        self.force_refresh = force_refresh
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        self.progress.emit("Membaca daftar Pacman dan Flatpak…")
        try:
            packages = backend.get_all_packages(force=self.force_refresh)
            if not self._cancelled:
                self.packages_loaded.emit(packages)
        except Exception as exc:
            if not self._cancelled:
                self.error_occurred.emit(str(exc))


class ScanUpdatesWorker(QThread):
    updates_loaded = pyqtSignal(object)
    progress = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        self.progress.emit("Memeriksa pembaruan Pacman, AUR, dan Flatpak…")
        try:
            updates = backend.get_outdated_packages(force=True)
            if not self._cancelled:
                self.updates_loaded.emit(updates)
        except Exception as exc:
            if not self._cancelled:
                self.error_occurred.emit(str(exc))


class DiskReportWorker(QThread):
    """Collect disk and application size information without blocking the UI."""

    report_loaded = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def run(self) -> None:
        try:
            self.report_loaded.emit(disk_report.collect_disk_report())
        except Exception as exc:
            self.error_occurred.emit(str(exc))


class OperationWorker(QThread):
    progress = pyqtSignal(str)
    operation_finished = pyqtSignal(bool, str)

    def __init__(
        self,
        operation: str,
        packages: list[Package] | None = None,
        update_all: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.operation = operation
        self.packages = packages or []
        self.update_all = update_all

    def _emit_output(self, line: str) -> None:
        cleaned = line.rstrip("\r\n")
        if cleaned:
            self.progress.emit(cleaned)

    def run(self) -> None:
        try:
            if self.operation == "update":
                success, message = backend.update_packages(
                    self.packages,
                    update_all=self.update_all,
                    on_output=self._emit_output,
                )
            elif self.operation == "uninstall":
                success, message = backend.batch_uninstall_packages(
                    self.packages,
                    on_output=self._emit_output,
                )
            else:
                success, message = False, f"Operasi tidak dikenal: {self.operation}"
            self.operation_finished.emit(success, message)
        except Exception as exc:
            backend._logger().exception("Worker operation failed: %s", self.operation)
            self.operation_finished.emit(False, f"Kesalahan tak terduga:\n{exc}")

"""CachyOS Software Manager desktop interface."""

from __future__ import annotations

import re
from pathlib import Path

from PyQt6.QtCore import QSettings, QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QSizePolicy,
    QStatusBar,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

import backend
from backend import Package
from disk_report import DiskItem, DiskReport, DiskVolume
from icons import make_icon, set_stateful_button_icon
from theme import DARK, LIGHT, get_stylesheet
from workers import DiskReportWorker, LoadPackagesWorker, OperationWorker, ScanUpdatesWorker


_PACKAGE_ROLE = Qt.ItemDataRole.UserRole
_FILTER_DELAY_MS = 180
APP_VERSION = Path(__file__).with_name("VERSION").read_text(encoding="utf-8").strip()


def _format_bytes(value: int) -> str:
    amount = float(max(0, value))
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return "0 B"


class ChevronComboBox(QComboBox):
    """Combo box with a small vector chevron instead of the platform glyph."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().color(self.foregroundRole())
        if not self.isEnabled():
            color.setAlpha(110)
        painter.setPen(QPen(color, 1.7, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        path = QPainterPath()
        x = self.width() - 19
        y = self.height() / 2 - 2
        path.moveTo(x - 4, y)
        path.lineTo(x, y + 4)
        path.lineTo(x + 4, y)
        painter.drawPath(path)
        painter.end()


class VolumeCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("volume_card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(8)
        title_row = QHBoxLayout()
        self.title = QLabel("Partisi")
        self.title.setObjectName("volume_title")
        self.percentage = QLabel("—")
        self.percentage.setObjectName("volume_percentage")
        title_row.addWidget(self.title)
        title_row.addStretch()
        title_row.addWidget(self.percentage)
        layout.addLayout(title_row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(12)
        layout.addWidget(self.progress)
        self.details = QLabel("Menunggu data…")
        self.details.setObjectName("volume_details")
        self.details.setWordWrap(True)
        layout.addWidget(self.details)

    def set_volume(self, volume: DiskVolume) -> None:
        self.title.setText(f"{volume.label} · {volume.path}")
        self.percentage.setText(f"{volume.percent_used:.1f}%".replace(".", ",") + " terpakai")
        self.progress.setValue(round(volume.percent_used * 10))
        self.details.setText(
            f"{_format_bytes(volume.used_bytes)} terpakai dari {_format_bytes(volume.total_bytes)}"
            f" · tersedia {_format_bytes(volume.free_bytes)}\n"
            f"Titik kait: {volume.mountpoint} · {volume.filesystem} · {volume.device}"
        )


def _version_key(value: str) -> tuple:
    return tuple((1, int(part)) if part.isdigit() else (0, part.casefold())
                 for part in re.split(r"(\d+)", value) if part)


def _size_key(value: str) -> tuple[int, float]:
    match = re.match(r"\s*([\d.]+)\s*([kmgt]?i?b)?\s*$", value, re.IGNORECASE)
    if not match:
        return 1, 0.0
    unit = (match.group(2) or "b").casefold().replace("ib", "b")
    power = {"b": 0, "kb": 1, "mb": 2, "gb": 3, "tb": 4}.get(unit, 0)
    return 0, float(match.group(1)) * (1024 ** power)


class SortItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:
        left = self.data(Qt.ItemDataRole.UserRole + 1)
        right = other.data(Qt.ItemDataRole.UserRole + 1)
        return (left if left is not None else (0, self.text().casefold())) < (
            right if right is not None else (0, other.text().casefold())
        )


class StatCard(QWidget):
    def __init__(self, title: str, value_object: str, parent=None):
        super().__init__(parent)
        self.setObjectName("stat_card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 9, 14, 9)
        layout.setSpacing(2)
        self.value_label = QLabel("—")
        self.value_label.setObjectName(value_object)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("sk_label")
        layout.addWidget(self.value_label)
        layout.addWidget(self.title_label)


class PackageDetailsDialog(QDialog):
    def __init__(self, package: Package, theme: dict, new_version: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("details_dialog")
        self.setWindowTitle(f"Detail Paket · {package.name}")
        self.setMinimumSize(600, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(10)

        heading = QLabel(package.name)
        heading.setObjectName("dialog_title")
        layout.addWidget(heading)
        summary = QPlainTextEdit()
        summary.setObjectName("details_output")
        summary.setReadOnly(True)
        source = package.source
        rows = [
            f"Sumber: {source}",
            f"Versi terpasang: {package.version}",
            f"Versi tersedia: {new_version or '—'}",
            f"Ukuran: {package.size or 'Tidak diketahui'}",
        ]
        if package.app_id:
            rows.append(f"ID aplikasi: {package.app_id}")
        if package.origin:
            rows.append(f"Sumber Flatpak: {package.origin}")
        if package.installation:
            rows.append(f"Instalasi: {package.installation}")
        if package.install_date:
            rows.append(f"Tanggal instalasi: {package.install_date}")
        if package.dependencies:
            rows.append(f"Dependensi: {package.dependencies}")
        if package.description:
            rows.extend(["", package.description])
        summary.setPlainText("\n".join(rows))
        layout.addWidget(summary)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Tutup")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class TransactionDialog(QDialog):
    """Non-blocking transaction monitor with streamed output and final log."""

    def __init__(self, title: str, log_path: str, parent=None):
        super().__init__(parent)
        self.setObjectName("transaction_dialog")
        self.setWindowTitle(title)
        self.setMinimumSize(680, 430)
        self._complete = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(10)
        self.status_label = QLabel("Menjalankan transaksi…")
        self.status_label.setObjectName("transaction_status")
        layout.addWidget(self.status_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(4)
        layout.addWidget(self.progress)
        self.output = QPlainTextEdit()
        self.output.setObjectName("terminal_output")
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(12000)
        self.output.setPlaceholderText("Output transaksi akan muncul di sini…")
        layout.addWidget(self.output, 1)
        self.log_hint = QLabel(f"Log aplikasi: {log_path}")
        self.log_hint.setObjectName("log_hint")
        self.log_hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.log_hint)
        row = QHBoxLayout()
        self.open_log = QPushButton("Buka Folder Log")
        self.open_log.setObjectName("btn_refresh")
        self.open_log.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(backend.get_log_path().parent))))
        row.addWidget(self.open_log)
        row.addStretch()
        self.close_button = QPushButton("Transaksi berjalan…")
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.accept)
        row.addWidget(self.close_button)
        layout.addLayout(row)

    def append_output(self, line: str) -> None:
        self.output.appendPlainText(line)

    def finish(self, succeeded: bool, summary: str) -> None:
        self._complete = True
        self.progress.hide()
        self.status_label.setText("Transaksi selesai" if succeeded else "Transaksi gagal atau hanya sebagian yang selesai")
        if summary:
            self.append_output("\n── Ringkasan ──\n" + summary)
        self.close_button.setText("Tutup")
        self.close_button.setEnabled(True)

    def closeEvent(self, event) -> None:
        if not self._complete:
            event.ignore()
            return
        event.accept()


class MainWindow(QMainWindow):
    def __init__(self, app: QApplication, parent=None, auto_load: bool = True):
        super().__init__(parent)
        self.app = app
        self.settings = QSettings("CachyOS", "CachyOS-Softmgr")
        self.current_theme = LIGHT if self.settings.value("theme", "dark") == "light" else DARK
        self.packages: list[Package] = []
        self.updates: dict[tuple, str] = {}
        self.update_warnings: list[str] = []
        self.helper_name = backend.get_aur_helper_name()
        self._workers = set()
        self.load_worker: LoadPackagesWorker | None = None
        self.scan_worker: ScanUpdatesWorker | None = None
        self.disk_worker: DiskReportWorker | None = None
        self.operation_worker: OperationWorker | None = None
        self.disk_report: DiskReport | None = None
        self.transaction_dialog: TransactionDialog | None = None
        self._load_generation = 0
        self._operation_running = False
        self._close_requested = False

        self.filter_timer = QTimer(self)
        self.filter_timer.setSingleShot(True)
        self.filter_timer.setInterval(_FILTER_DELAY_MS)
        self.filter_timer.timeout.connect(self._apply_filter)

        self._build_window()
        self.app.setStyleSheet(get_stylesheet(self.current_theme))
        self._set_theme_button()
        if auto_load:
            self._load_packages(force=False)

    def _build_window(self) -> None:
        self.setWindowTitle(f"CachyOS Softmgr · Versi terbaru {APP_VERSION}")
        self.setWindowIcon(make_icon("brand", self.current_theme["accent"], 64))
        self.setMinimumSize(1080, 720)
        self.resize(1320, 840)
        root = QWidget()
        root.setObjectName("window_root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())
        separator = QFrame()
        separator.setObjectName("header_separator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(1)
        outer.addWidget(separator)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 15, 22, 14)
        layout.setSpacing(9)
        layout.addWidget(self._build_stats())
        layout.addWidget(self._build_tabs())
        self.filter_row = self._build_filter_row()
        layout.addWidget(self.filter_row)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        self.page_stack = QStackedWidget()
        self.page_stack.addWidget(self._build_package_page())
        self.page_stack.addWidget(self._build_disk_page())
        layout.addWidget(self.page_stack, 1)
        outer.addWidget(content, 1)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Siap")

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("header_panel")
        header.setFixedHeight(78)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 0, 24, 0)
        self.app_logo = QLabel()
        self.app_logo.setObjectName("app_logo")
        self.app_logo.setPixmap(make_icon("brand", self.current_theme["accent"], 42).pixmap(42, 42))
        layout.addWidget(self.app_logo)
        block = QWidget()
        block.setFixedHeight(78)
        block_layout = QVBoxLayout(block)
        # Move the title's lower glyph edge to the marked baseline; keep the brand line below it.
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(0)
        block_layout.addSpacing(16)
        title = QLabel("CachyOS Softmgr")
        title.setObjectName("app_title")
        self.app_title = title
        subtitle = QLabel("PACMAN   ·   AUR   ·   FLATPAK")
        subtitle.setObjectName("app_subtitle")
        block_layout.addWidget(title)
        block_layout.addStretch(1)
        block_layout.addWidget(subtitle)
        layout.addWidget(block)
        layout.addStretch()
        self.helper_badge = QLabel(f"AUR · {self.helper_name}" if self.helper_name else "AUR belum aktif")
        self.helper_badge.setObjectName("helper_badge")
        self.helper_badge.setToolTip(self._aur_helper_tooltip())
        layout.addWidget(self.helper_badge)
        layout.addSpacing(12)
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("btn_theme_toggle")
        self.theme_button.setFixedSize(152, 40)
        self.theme_button.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_button)
        return header

    def _build_stats(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 2)
        layout.setSpacing(8)
        self.stat_total = StatCard("TERPASANG", "sv_total")
        self.stat_pacman = StatCard("PACMAN", "sv_pacman")
        self.stat_aur = StatCard("AUR", "sv_aur")
        self.stat_flatpak = StatCard("FLATPAK", "sv_flatpak")
        self.stat_updates = StatCard("PEMBARUAN TERSEDIA", "sv_outdated")
        for card in (self.stat_total, self.stat_pacman, self.stat_aur, self.stat_flatpak, self.stat_updates):
            card.setFixedHeight(62)
            layout.addWidget(card)
        layout.addStretch()
        return bar

    def _build_filter_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        self.filter_info = QLabel("")
        self.filter_info.setObjectName("filter_info_label")
        layout.addWidget(self.filter_info)
        layout.addStretch()
        source_label = QLabel("Sumber:")
        source_label.setObjectName("filter_type_label")
        layout.addWidget(source_label)
        self.source_filter = ChevronComboBox()
        self.source_filter.addItems(["Semua sumber", "Pacman", "AUR", "Flatpak"])
        self.source_filter.setFixedSize(160, 36)
        self.source_filter.currentTextChanged.connect(self._schedule_filter)
        layout.addWidget(self.source_filter)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Cari nama atau deskripsi paket…")
        self.search.addAction(make_icon("search", self.current_theme["text_secondary"], 18), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setFixedSize(340, 42)
        self.search.textChanged.connect(self._schedule_filter)
        layout.addWidget(self.search)
        return row

    def _build_tabs(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabBar()
        self.tabs.setObjectName("package_tabs")
        self.tabs.addTab(make_icon("package", self.current_theme["accent"], 18), "Aplikasi")
        self.tabs.addTab(make_icon("update", self.current_theme["accent"], 18), "Pembaruan")
        self.tabs.addTab(make_icon("storage", self.current_theme["accent"], 18), "Penyimpanan")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)
        layout.addStretch()
        self.update_coverage = QLabel(self._coverage_text())
        self.update_coverage.setObjectName("coverage_note")
        layout.addWidget(self.update_coverage)
        return row

    def _coverage_text(self) -> str:
        helper = f"AUR melalui {self.helper_name}" if self.helper_name else "AUR belum aktif"
        flatpak = "Flatpak aktif" if backend.is_flatpak_available() else "Flatpak opsional"
        return f"{helper}  ·  {flatpak}"

    def _aur_helper_tooltip(self) -> str:
        if self.helper_name:
            return (f"AUR (Arch User Repository) dikelola melalui {self.helper_name}, "
                    "alat bantu untuk mencari, membangun, memasang, dan memperbarui paket AUR.")
        return "AUR adalah repositori paket komunitas Arch. Pasang paru atau yay untuk mengaktifkan pengelolaannya."

    def _build_package_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        layout.addWidget(self._build_table(), 1)
        layout.addWidget(self._build_actions())
        return page

    def _build_table(self) -> QTableWidget:
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["", "Nama Paket", "Sumber", "Terpasang", "Tersedia", "Ukuran"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in range(2, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        for column, width in ((0, 44), (2, 128), (3, 150), (4, 150), (5, 112)):
            self.table.setColumnWidth(column, width)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.setSortingEnabled(True)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        self.table.itemDoubleClicked.connect(self._show_package_details)
        return self.table

    def _build_actions(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("action_bar")
        bar.setFixedHeight(64)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(9)
        self.selection_label = QLabel("Centang paket untuk menampilkan aksinya")
        self.selection_label.setObjectName("label_selected")
        layout.addWidget(self.selection_label, 1)
        self.refresh_button = QPushButton("Muat ulang")
        self.refresh_button.setObjectName("btn_refresh")
        self.refresh_button.setFixedSize(136, 42)
        self.refresh_button.setIconSize(QSize(20, 20))
        set_stateful_button_icon(
            self.refresh_button, "refresh", self.current_theme["accent"],
            self.current_theme["text_on_accent"], self.current_theme["text_muted"], 20,
        )
        self.refresh_button.clicked.connect(lambda: self._load_packages(force=True))
        layout.addWidget(self.refresh_button)
        self.update_button = QPushButton("Perbarui")
        self.update_button.setObjectName("btn_update")
        self.update_button.setMinimumSize(180, 38)
        set_stateful_button_icon(
            self.update_button, "update", self.current_theme["bg_primary"],
            self.current_theme["bg_primary"], self.current_theme["text_muted"], 20,
        )
        self.update_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.update_button.clicked.connect(self._on_update_clicked)
        layout.addWidget(self.update_button)
        self.remove_button = QPushButton("Copot")
        self.remove_button.setObjectName("btn_uninstall")
        self.remove_button.setMinimumSize(155, 38)
        set_stateful_button_icon(
            self.remove_button, "trash", "#FFFFFF", "#FFFFFF",
            self.current_theme["text_muted"], 20,
        )
        self.remove_button.clicked.connect(self._on_uninstall_clicked)
        layout.addWidget(self.remove_button)
        return bar

    def _build_disk_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading_row = QHBoxLayout()
        heading_block = QVBoxLayout()
        heading_block.setSpacing(2)
        title = QLabel("Penggunaan penyimpanan")
        title.setObjectName("disk_title")
        subtitle = QLabel("Lihat kapasitas root dan home serta perangkat lunak yang paling banyak memakai ruang.")
        subtitle.setObjectName("disk_subtitle")
        heading_block.addWidget(title)
        heading_block.addWidget(subtitle)
        heading_row.addLayout(heading_block)
        heading_row.addStretch()
        self.disk_refresh_button = QPushButton("Muat ulang")
        self.disk_refresh_button.setObjectName("btn_refresh")
        self.disk_refresh_button.setFixedSize(136, 42)
        self.disk_refresh_button.setIconSize(QSize(20, 20))
        set_stateful_button_icon(
            self.disk_refresh_button, "refresh", self.current_theme["accent"],
            self.current_theme["text_on_accent"], self.current_theme["text_muted"], 20,
        )
        self.disk_refresh_button.clicked.connect(lambda: self._load_disk_report(force=True))
        heading_row.addWidget(self.disk_refresh_button)
        layout.addLayout(heading_row)

        volume_row = QHBoxLayout()
        volume_row.setSpacing(10)
        self.disk_volume_cards = {key: VolumeCard() for key in ("root", "home")}
        volume_row.addWidget(self.disk_volume_cards["root"])
        volume_row.addWidget(self.disk_volume_cards["home"])
        layout.addLayout(volume_row)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Partisi:"))
        self.disk_volume_filter = ChevronComboBox()
        self.disk_volume_filter.addItems(["Semua partisi", "Root (/)", "Home"])
        self.disk_volume_filter.setFixedSize(175, 40)
        self.disk_volume_filter.currentIndexChanged.connect(self._populate_disk_table)
        controls.addWidget(self.disk_volume_filter)
        controls.addSpacing(8)
        controls.addWidget(QLabel("Sumber:"))
        self.disk_source_filter = ChevronComboBox()
        self.disk_source_filter.addItems(["Semua sumber", "Pacman", "AUR", "Flatpak", "Data Flatpak", "Cache Pacman"])
        self.disk_source_filter.setFixedSize(180, 40)
        self.disk_source_filter.currentIndexChanged.connect(self._populate_disk_table)
        controls.addWidget(self.disk_source_filter)
        controls.addStretch()
        self.disk_count = QLabel("Memuat data…")
        self.disk_count.setObjectName("disk_subtitle")
        controls.addWidget(self.disk_count)
        layout.addLayout(controls)

        self.disk_table = QTableWidget(0, 4)
        self.disk_table.setObjectName("disk_table")
        self.disk_table.setHorizontalHeaderLabels(["Perangkat lunak / folder", "Sumber", "Ukuran perkiraan", "Relatif"])
        header = self.disk_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.disk_table.setColumnWidth(1, 145)
        self.disk_table.setColumnWidth(2, 155)
        self.disk_table.setColumnWidth(3, 210)
        self.disk_table.verticalHeader().hide()
        self.disk_table.setAlternatingRowColors(True)
        self.disk_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.disk_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.disk_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.disk_table.setShowGrid(False)
        self.disk_table.horizontalHeader().setHighlightSections(False)
        self.disk_table.itemSelectionChanged.connect(self._show_disk_item_details)
        layout.addWidget(self.disk_table, 1)

        self.disk_detail = QLabel("Ukuran paket Pacman/AUR berasal dari metadata paket. Data aplikasi diukur langsung dari folder pengguna.")
        self.disk_detail.setObjectName("disk_note")
        self.disk_detail.setWordWrap(True)
        layout.addWidget(self.disk_detail)
        self.disk_warnings = QLabel("")
        self.disk_warnings.setObjectName("disk_warning")
        self.disk_warnings.setWordWrap(True)
        self.disk_warnings.hide()
        layout.addWidget(self.disk_warnings)
        return page

    def _on_tab_changed(self, index: int) -> None:
        is_disk = index == 2
        self.filter_row.setVisible(not is_disk)
        self.progress_bar.setVisible(not is_disk and self.load_worker is not None)
        self.page_stack.setCurrentIndex(1 if is_disk else 0)
        self.update_coverage.setVisible(not is_disk)
        if is_disk and self.disk_report is None and self.disk_worker is None:
            self._load_disk_report()
        if not is_disk:
            self._apply_filter()
        else:
            self._update_action_buttons()

    def _load_disk_report(self, force: bool = False) -> None:
        if self.disk_worker is not None and self.disk_worker.isRunning():
            return
        if self.disk_report is not None and not force:
            return
        self.disk_refresh_button.setEnabled(False)
        self.disk_count.setText("Menghitung penggunaan penyimpanan…")
        self.disk_warnings.hide()
        worker = DiskReportWorker(parent=self)
        self.disk_worker = worker
        worker.report_loaded.connect(self._on_disk_report_loaded)
        worker.error_occurred.connect(self._on_disk_report_error)
        self._track_worker(worker)
        worker.start()

    def _on_disk_report_loaded(self, report: DiskReport) -> None:
        self.disk_report = report
        self.disk_refresh_button.setEnabled(True)
        volumes = {volume.key: volume for volume in report.volumes}
        for key, card in self.disk_volume_cards.items():
            volume = volumes.get(key)
            if volume is not None:
                card.set_volume(volume)
        if "root" in volumes and "home" in volumes and volumes["root"].device_id == volumes["home"].device_id:
            self.disk_note_same_volume = "Root dan home berada pada perangkat/partisi yang sama."
        else:
            self.disk_note_same_volume = ""
        warnings = "\n".join(report.warnings)
        self.disk_warnings.setText(warnings)
        self.disk_warnings.setVisible(bool(warnings))
        self._populate_disk_table()
        self.status_bar.showMessage("Informasi penyimpanan berhasil diperbarui")

    def _on_disk_report_error(self, error: str) -> None:
        self.disk_refresh_button.setEnabled(True)
        self.disk_count.setText("Data penyimpanan tidak dapat dimuat")
        self.disk_warnings.setText(error)
        self.disk_warnings.show()

    def _populate_disk_table(self, *args) -> None:
        if self.disk_report is None:
            return
        volume_index = self.disk_volume_filter.currentIndex()
        source = self.disk_source_filter.currentText()
        volumes = {volume.key: volume for volume in self.disk_report.volumes}
        selected_volume = {1: volumes.get("root"), 2: volumes.get("home")}.get(volume_index)
        items = [
            item for item in self.disk_report.items
            if (selected_volume is None or item.device_id == selected_volume.device_id)
            and (source == "Semua sumber" or item.source == source)
        ]
        items.sort(key=lambda item: item.size_bytes, reverse=True)
        maximum = max((item.size_bytes for item in items), default=0)
        self.disk_table.setRowCount(0)
        self.disk_table.setSortingEnabled(False)
        for row, item in enumerate(items):
            self.disk_table.insertRow(row)
            self.disk_table.setRowHeight(row, 46)
            name = QTableWidgetItem(item.name)
            name.setToolTip(item.details or item.name)
            name.setData(Qt.ItemDataRole.UserRole, item)
            source_item = QTableWidgetItem(item.source)
            source_icon = {"Pacman": "package", "AUR": "aur", "Flatpak": "flatpak"}.get(item.source)
            if source_icon:
                source_item.setIcon(make_icon(source_icon, self.current_theme["accent"], 16))
            size_item = QTableWidgetItem(_format_bytes(item.size_bytes))
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.disk_table.setItem(row, 0, name)
            self.disk_table.setItem(row, 1, source_item)
            self.disk_table.setItem(row, 2, size_item)
            meter = QProgressBar()
            meter.setRange(0, 1000)
            meter.setValue(round(item.size_bytes / maximum * 1000) if maximum else 0)
            meter.setTextVisible(False)
            meter.setFixedHeight(10)
            meter.setObjectName("disk_meter")
            holder = QWidget()
            holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(10, 0, 10, 0)
            holder_layout.addWidget(meter)
            self.disk_table.setCellWidget(row, 3, holder)
        self.disk_count.setText(f"{len(items)} item · diurutkan dari yang terbesar")
        self.disk_detail.setText(
            (self.disk_note_same_volume + " " if getattr(self, "disk_note_same_volume", "") else "")
            + "Ukuran paket Pacman/AUR adalah perkiraan dari metadata paket; data aplikasi pengguna dan cache diukur langsung."
        )

    def _show_disk_item_details(self) -> None:
        row = self.disk_table.currentRow()
        item = self.disk_table.item(row, 0) if row >= 0 else None
        disk_item = item.data(Qt.ItemDataRole.UserRole) if item else None
        if isinstance(disk_item, DiskItem):
            details = f"{disk_item.name} · {disk_item.source} · {_format_bytes(disk_item.size_bytes)}"
            if disk_item.details:
                details += f" · {disk_item.details}"
            self.disk_detail.setText(details)

    def _track_worker(self, worker) -> None:
        self._workers.add(worker)
        worker.finished.connect(lambda w=worker: self._worker_finished(w))

    def _worker_finished(self, worker) -> None:
        self._workers.discard(worker)
        if self.load_worker is worker:
            self.load_worker = None
        if self.scan_worker is worker:
            self.scan_worker = None
        if self.operation_worker is worker:
            self.operation_worker = None
        if self.disk_worker is worker:
            self.disk_worker = None
            self.disk_refresh_button.setEnabled(True)
        worker.deleteLater()
        self._maybe_close_after_workers()

    def _load_packages(self, force: bool = True) -> None:
        self.helper_name = backend.get_aur_helper_name()
        self.helper_badge.setText(f"AUR · {self.helper_name}" if self.helper_name else "AUR belum aktif")
        self.helper_badge.setToolTip(self._aur_helper_tooltip())
        self.update_coverage.setText(self._coverage_text())
        self.update_coverage.setToolTip("")
        self._load_generation += 1
        generation = self._load_generation
        for worker in (self.load_worker, self.scan_worker):
            if worker is not None and worker.isRunning():
                worker.cancel()
        self.load_worker = None
        self.scan_worker = None
        self.updates = {}
        self.table.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.progress_bar.show()
        self.selection_label.setText("Memuat paket dari sistem…")
        self.stat_updates.value_label.setText("…")

        worker = LoadPackagesWorker(force_refresh=force, parent=self)
        self.load_worker = worker
        worker.progress.connect(lambda text, g=generation: self._show_status(text, g))
        worker.packages_loaded.connect(lambda items, g=generation: self._on_packages_loaded(items, g))
        worker.error_occurred.connect(lambda error, g=generation: self._on_load_error(error, g))
        self._track_worker(worker)
        worker.start()

    def _show_status(self, text: str, generation: int) -> None:
        if generation == self._load_generation:
            self.status_bar.showMessage(text)

    def _on_packages_loaded(self, packages: list[Package], generation: int) -> None:
        if generation != self._load_generation:
            return
        self.packages = packages
        self.table.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.progress_bar.hide()
        self.stat_total.value_label.setText(str(len(packages)))
        self.stat_pacman.value_label.setText(str(sum(p.source == "Pacman" for p in packages)))
        self.stat_aur.value_label.setText(str(sum(p.source == "AUR" for p in packages)))
        self.stat_flatpak.value_label.setText(str(sum(p.source == "Flatpak" for p in packages)))
        self._populate_table()
        self._apply_filter()
        self.status_bar.showMessage(f"{len(packages)} paket dimuat · memeriksa pembaruan…")

        worker = ScanUpdatesWorker(parent=self)
        self.scan_worker = worker
        worker.progress.connect(lambda text, g=generation: self._show_status(text, g))
        worker.updates_loaded.connect(lambda result, g=generation: self._on_updates_loaded(result, g))
        worker.error_occurred.connect(lambda error, g=generation: self._on_update_scan_error(error, g))
        self._track_worker(worker)
        worker.start()

    def _on_load_error(self, error: str, generation: int) -> None:
        if generation != self._load_generation:
            return
        self.progress_bar.hide()
        self.table.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.selection_label.setText("Daftar paket gagal dimuat")
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Gagal membaca paket")
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setText("Daftar paket tidak dapat dimuat.")
        dialog.setInformativeText(error)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.button(QMessageBox.StandardButton.Ok).setText("Tutup")
        self._prepare_message_box(dialog)
        dialog.exec()

    def _on_updates_loaded(self, result, generation: int) -> None:
        if generation != self._load_generation:
            return
        self.updates = dict(result.updates)
        self.update_warnings = list(result.warnings)
        for package in self.packages:
            package.is_outdated = package.key in self.updates
            package.new_version = self.updates.get(package.key, "")
        self.stat_updates.value_label.setText(str(len(self.updates)))
        self._refresh_rows()
        self._apply_filter()
        if self.update_warnings:
            self.update_coverage.setText("Sebagian sumber gagal diperiksa")
            self.update_coverage.setToolTip("\n".join(self.update_warnings))
            self.status_bar.showMessage("Pembaruan terbaca dengan peringatan · arahkan kursor ke ringkasan sumber untuk detail")
        else:
            self.update_coverage.setText(self._coverage_text())
            self.update_coverage.setToolTip("")
            self.status_bar.showMessage(f"Paket siap · {len(self.updates)} pembaruan tersedia")

    def _on_update_scan_error(self, error: str, generation: int) -> None:
        if generation != self._load_generation:
            return
        self.update_warnings = [error]
        self.update_coverage.setText("Pemeriksaan sumber gagal")
        self.update_coverage.setToolTip(error)
        self.stat_updates.value_label.setText("?")
        self._apply_filter()
        self.status_bar.showMessage("Pemeriksaan pembaruan gagal; daftar paket tetap tersedia")

    def _populate_table(self) -> None:
        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for row, package in enumerate(self.packages):
            self.table.insertRow(row)
            self.table.setRowHeight(row, 48)
            checkbox = QTableWidgetItem("")
            checkbox.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            checkbox.setCheckState(Qt.CheckState.Unchecked)
            checkbox.setData(_PACKAGE_ROLE, package)
            self.table.setItem(row, 0, checkbox)

            name = SortItem(package.name)
            name.setData(_PACKAGE_ROLE, package)
            name.setData(Qt.ItemDataRole.UserRole + 1, (0, package.name.casefold()))
            name.setFont(QFont("", 11, QFont.Weight.Medium))
            tooltip = package.description or package.name
            if package.origin:
                tooltip += f"\nSumber Flatpak: {package.origin}"
            if package.installation:
                tooltip += f"\nInstalasi: {package.installation}"
            name.setToolTip(tooltip)
            self.table.setItem(row, 1, name)

            source_text = package.source
            source = SortItem(source_text)
            source.setData(Qt.ItemDataRole.UserRole + 1, (0, source_text.casefold()))
            source_icon = {"Pacman": "package", "AUR": "aur", "Flatpak": "flatpak"}.get(package.source)
            source_color = {"Pacman": "badge_pacman_fg", "AUR": "badge_aur_fg", "Flatpak": "badge_flatpak_fg"}.get(package.source)
            if source_icon:
                source.setIcon(make_icon(source_icon, self.current_theme[source_color], 16))
            self.table.setItem(row, 2, source)
            self._center(source)

            version = SortItem(package.version)
            version.setData(Qt.ItemDataRole.UserRole + 1, (0, _version_key(package.version)))
            self._center(version)
            self.table.setItem(row, 3, version)

            newer = SortItem(package.new_version or "—")
            newer.setData(Qt.ItemDataRole.UserRole + 1, (0, _version_key(package.new_version)) if package.new_version else (1, ()))
            self._center(newer)
            self.table.setItem(row, 4, newer)

            size = SortItem(package.size)
            if package.size.strip().casefold() in {"n/a", "unknown"}:
                size.setText("Tidak diketahui")
            size.setData(Qt.ItemDataRole.UserRole + 1, _size_key(package.size))
            self._center(size)
            self.table.setItem(row, 5, size)
            self._style_row(row, package)
        self.table.blockSignals(False)
        self.table.setSortingEnabled(sorting)
        self.table.clearSelection()
        self._update_action_buttons()

    @staticmethod
    def _center(item: QTableWidgetItem) -> None:
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

    def _style_row(self, row: int, package: Package) -> None:
        colors = self.current_theme
        name = self.table.item(row, 1)
        name.setText(package.name)
        name.setForeground(QColor(colors["outdated"] if package.is_outdated else colors["text_primary"]))
        for column in (3, 5):
            self.table.item(row, column).setForeground(QColor(colors["text_secondary"]))
        self.table.item(row, 4).setForeground(QColor(colors["outdated"] if package.is_outdated else colors["text_muted"]))
        self.table.item(row, 4).setIcon(
            make_icon("update", colors["outdated"], 16) if package.is_outdated else QIcon()
        )
        source_colors = {
            "Pacman": colors["badge_pacman_fg"],
            "AUR": colors["badge_aur_fg"],
            "Flatpak": colors["badge_flatpak_fg"],
        }
        self.table.item(row, 2).setForeground(QColor(source_colors.get(package.source, colors["text_secondary"])))
        source_icon = {"Pacman": "package", "AUR": "aur", "Flatpak": "flatpak"}.get(package.source)
        source_icon_color = {
            "Pacman": colors["badge_pacman_fg"],
            "AUR": colors["badge_aur_fg"],
            "Flatpak": colors["badge_flatpak_fg"],
        }.get(package.source)
        self.table.item(row, 2).setIcon(
            make_icon(source_icon, source_icon_color, 16) if source_icon and source_icon_color else QIcon()
        )
        checkbox = self.table.item(row, 0)
        if backend.is_critical_package(package.name) and package.source in {"Pacman", "AUR"}:
            checkbox.setToolTip("Paket sistem penting. Peringatan tambahan muncul sebelum penghapusan.")

    def _refresh_rows(self) -> None:
        packages = {package.key: package for package in self.packages}
        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            check = self.table.item(row, 0)
            old: Package = check.data(_PACKAGE_ROLE)
            package = packages.get(old.key)
            if package is None:
                continue
            check.setData(_PACKAGE_ROLE, package)
            name = self.table.item(row, 1)
            name.setData(_PACKAGE_ROLE, package)
            name.setData(Qt.ItemDataRole.UserRole + 1, (0, package.name.casefold()))
            self.table.item(row, 3).setText(package.version)
            self.table.item(row, 3).setData(Qt.ItemDataRole.UserRole + 1, (0, _version_key(package.version)))
            self.table.item(row, 4).setText(package.new_version or "—")
            self.table.item(row, 4).setData(Qt.ItemDataRole.UserRole + 1,
                (0, _version_key(package.new_version)) if package.new_version else (1, ()))
            self._style_row(row, package)
        self.table.blockSignals(False)
        self.table.setSortingEnabled(sorting)

    def _schedule_filter(self, *args) -> None:
        self.filter_timer.start()

    def _apply_filter(self, *args) -> None:
        search = self.search.text().strip().casefold()
        source = self.source_filter.currentText()
        update_tab = self.tabs.currentIndex() == 1
        visible = 0
        for row in range(self.table.rowCount()):
            package: Package = self.table.item(row, 1).data(_PACKAGE_ROLE)
            shown = (
                (source == "Semua sumber" or source == package.source)
                and (not update_tab or package.key in self.updates)
                and (not search or search in package.name.casefold() or search in package.description.casefold())
            )
            self.table.setRowHidden(row, not shown)
            visible += int(shown)
        self.filter_info.setText(f"{visible} dari {len(self.packages)} paket" if search or source != "Semua sumber" or update_tab else "")
        self._update_action_buttons()

    def _checked_packages(self) -> list[Package]:
        return [
            self.table.item(row, 0).data(_PACKAGE_ROLE)
            for row in range(self.table.rowCount())
            if self.table.item(row, 0).checkState() == Qt.CheckState.Checked
        ]

    def _selected_package(self) -> Package | None:
        row = self.table.currentRow()
        item = self.table.item(row, 1) if row >= 0 else None
        return item.data(_PACKAGE_ROLE) if item else None

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            self._update_action_buttons()

    def _update_action_buttons(self, *args) -> None:
        checked = self._checked_packages()
        self.remove_button.setEnabled(bool(checked) and not self._operation_running)
        self.remove_button.setText("Copot" if not checked else f"Copot pilihan ({len(checked)})")
        if checked:
            can_update = all(package.key in self.updates for package in checked)
            self.update_button.setText(f"Perbarui pilihan ({len(checked)})")
            self.update_button.setToolTip(
                "Memperbarui Pacman, AUR dan/atau Flatpak yang dicentang."
                if can_update else "Centang hanya paket yang memiliki update tersedia."
            )
            self.update_button.setEnabled(can_update and not self._operation_running)
        elif self.tabs.currentIndex() == 1 and self.updates:
            self.update_button.setText(f"Perbarui semua ({len(self.updates)})")
            self.update_button.setToolTip("Memperbarui Pacman, AUR, dan Flatpak yang tersedia.")
            self.update_button.setEnabled(not self._operation_running)
        else:
            self.update_button.setText("Perbarui")
            self.update_button.setToolTip("Buka tab Pembaruan untuk melihat paket yang dapat diperbarui.")
            self.update_button.setEnabled(False)

        if checked:
            names = ", ".join(package.name for package in checked[:3])
            rest = f" +{len(checked) - 3}" if len(checked) > 3 else ""
            self.selection_label.setText(f"{len(checked)} paket dicentang: {names}{rest}")
        else:
            package = self._selected_package()
            self.selection_label.setText(
                f"{package.name} · {package.version} · {package.source}"
                if package else "Centang paket untuk menampilkan aksinya"
            )

    def _show_package_details(self, item: QTableWidgetItem) -> None:
        package = self.table.item(item.row(), 1).data(_PACKAGE_ROLE)
        PackageDetailsDialog(package, self.current_theme, self.updates.get(package.key, ""), self).exec()

    def _on_update_clicked(self) -> None:
        checked = self._checked_packages()
        update_all = not checked
        packages = checked
        if update_all and (self.tabs.currentIndex() != 1 or not self.updates):
            return
        if checked and not all(package.key in self.updates for package in checked):
            return
        if not self._confirm_update(packages, update_all):
            return
        self._start_operation("update", packages=packages, update_all=update_all)

    def _confirm_update(self, packages: list[Package], update_all: bool) -> bool:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Konfirmasi Pembaruan")
        dialog.setIcon(QMessageBox.Icon.Question)
        if update_all:
            dialog.setText(f"Perbarui semua paket dari sumber yang didukung? ({len(self.updates)} update)")
            dialog.setInformativeText(
                "Pacman menjalankan full system upgrade. AUR dibangun lewat helper yang tersedia, dan Flatpak memakai remote terpasang."
            )
            names = [f"{key[1]} → {version} ({key[0]})" for key, version in self.updates.items()]
        else:
            dialog.setText(f"Perbarui {len(packages)} paket yang dicentang?")
            has_aur = any(package.source == "AUR" for package in packages)
            warning = "Paket lain dapat ikut diperbarui agar sistem tetap konsisten."
            if has_aur:
                warning += " AUR menjalankan PKGBUILD sebagai pengguna Anda; pembaruan dapat mengeksekusi skrip build dari sumber AUR."
            dialog.setInformativeText(warning)
            pacman_sync = any(package.source in {"Pacman", "AUR"} for package in packages)
            if pacman_sync:
                names = [
                    f"{key[1]} → {version} (Pacman)"
                    for key, version in self.updates.items()
                    if key[0] == "Pacman"
                ]
                if not names:
                    names.append("Sinkronisasi sistem Pacman penuh")
                names.extend(
                    f"{package.name} · {package.source} · {self.updates[package.key]}"
                    for package in packages if package.source != "Pacman"
                )
                dialog.setInformativeText(
                    warning + " Daftar rincian memuat semua pembaruan Pacman yang terdeteksi."
                )
            else:
                names = [f"{package.name} · {package.source} · {self.updates[package.key]}" for package in packages]
        dialog.setDetailedText("\n".join(names))
        dialog.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes)
        dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
        dialog.button(QMessageBox.StandardButton.Cancel).setText("Batal")
        dialog.button(QMessageBox.StandardButton.Yes).setText("Jalankan pembaruan")
        self._prepare_message_box(dialog)
        return dialog.exec() == QMessageBox.StandardButton.Yes

    def _on_uninstall_clicked(self) -> None:
        packages = self._checked_packages()
        if not packages:
            return
        critical = [p for p in packages if p.source in {"Pacman", "AUR"} and backend.is_critical_package(p.name)]
        if critical:
            warning = QMessageBox(self)
            warning.setWindowTitle("Peringatan: paket sistem penting")
            warning.setIcon(QMessageBox.Icon.Warning)
            warning.setText("Pilihan ini mencakup paket penting bagi sistem operasi.")
            warning.setInformativeText(
                "Menghapus kernel, komponen inti, jaringan, atau bootloader dapat membuat sistem gagal "
                "memulai atau kehilangan fungsi penting. Pacman dapat menolak penghapusan bila masih "
                "dibutuhkan paket lain. Paket terpilih: " + ", ".join(p.name for p in critical)
            )
            warning.setDetailedText("Paket penting terpilih:\n" + "\n".join(p.name for p in critical))
            warning.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes)
            warning.setDefaultButton(QMessageBox.StandardButton.Cancel)
            warning.button(QMessageBox.StandardButton.Cancel).setText("Batal")
            warning.button(QMessageBox.StandardButton.Yes).setText("Saya paham, lanjutkan")
            self._prepare_message_box(warning)
            if warning.exec() != QMessageBox.StandardButton.Yes:
                return

        dialog = QMessageBox(self)
        dialog.setWindowTitle("Konfirmasi terakhir" if critical else "Konfirmasi Penghapusan")
        dialog.setIcon(QMessageBox.Icon.Warning if critical else QMessageBox.Icon.Question)
        dialog.setText(
            f"Copot {len(critical)} paket sistem penting?" if critical
            else f"Hapus {len(packages)} paket/aplikasi?"
        )
        info_parts = []
        if critical:
            info_parts.append(
                "Konfirmasi terakhir untuk: " + ", ".join(p.name for p in critical)
                + ". Pastikan Anda memang ingin mencopotnya."
            )
        elif any(p.source in {"Pacman", "AUR"} for p in packages):
            info_parts.append(
                "Pacman menghapus paket terpilih dalam satu transaksi. Dependensi otomatis yang tidak lagi "
                "dibutuhkan dapat ikut dihapus; berkas konfigurasi yang diubah dapat disimpan sebagai .pacsave."
            )
        if any(p.source == "Flatpak" for p in packages):
            info_parts.append("Data pengguna Flatpak tetap tersimpan setelah aplikasi dihapus.")
        if info_parts:
            dialog.setInformativeText("\n".join(info_parts))
        dialog.setDetailedText("\n".join(f"{p.name} · {p.source} · {p.installation or 'default'}" for p in packages))
        dialog.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes)
        dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
        dialog.button(QMessageBox.StandardButton.Cancel).setText("Batal")
        dialog.button(QMessageBox.StandardButton.Yes).setText("Copot paket penting" if critical else "Copot pilihan")
        self._prepare_message_box(dialog)
        if dialog.exec() == QMessageBox.StandardButton.Yes:
            self._start_operation("uninstall", packages=packages)

    @staticmethod
    def _prepare_message_box(dialog: QMessageBox) -> None:
        """Give confirmation popups room and localize Qt's details toggle."""
        dialog.setMinimumWidth(640)
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        for button in dialog.findChildren(QPushButton):
            if button.objectName() == "qt_msgbox_detailedtext" or button.text().startswith("Show Details"):
                button.setText("Rincian paket")
                button.setMinimumWidth(130)
                button.clicked.connect(
                    lambda _checked=False, details_button=button, message_box=dialog: QTimer.singleShot(
                        0,
                        lambda target=details_button, box=message_box: MainWindow._localize_details_button(
                            target, box
                        ),
                    )
                )
            button.setMinimumHeight(42)
        QTimer.singleShot(0, lambda box=dialog: MainWindow._resize_message_box(box))

    @staticmethod
    def _resize_message_box(dialog: QMessageBox) -> None:
        # QMessageBox recalculates its own minimum width during show; apply our
        # comfortable size once its native layout has finished that pass.
        if dialog.isVisible():
            dialog.setMinimumSize(640, 230)
            dialog.resize(max(dialog.width(), 640), max(dialog.height(), 230))

    @staticmethod
    def _localize_details_button(button: QPushButton, dialog: QMessageBox) -> None:
        button.setText(
            "Sembunyikan rincian" if button.text().startswith("Hide Details") else "Rincian paket"
        )
        MainWindow._resize_message_box(dialog)

    def _start_operation(self, operation: str, packages: list[Package] | None = None, update_all: bool = False) -> None:
        if self._operation_running:
            return
        self._operation_running = True
        self._set_controls_enabled(False)
        action = "Pembaruan paket" if operation == "update" else "Penghapusan paket"
        self.transaction_dialog = TransactionDialog(action, str(backend.get_log_path()), self)
        self.transaction_dialog.setModal(True)
        self.transaction_dialog.show()
        worker = OperationWorker(operation, packages, update_all, parent=self)
        self.operation_worker = worker
        worker.progress.connect(self.transaction_dialog.append_output)
        worker.operation_finished.connect(self._on_operation_finished)
        self._track_worker(worker)
        worker.start()

    def _on_operation_finished(self, succeeded: bool, summary: str) -> None:
        self._operation_running = False
        self._set_controls_enabled(True)
        if self.transaction_dialog:
            self.transaction_dialog.finish(succeeded, summary)
        self.status_bar.showMessage("Transaksi selesai · daftar sedang disegarkan")
        # Pacman/AUR/Flatpak batches can partially succeed; always reload state.
        self._load_packages(force=True)

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.table.setEnabled(enabled)
        self.source_filter.setEnabled(enabled)
        self.search.setEnabled(enabled)
        self.tabs.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)
        self._update_action_buttons()

    def _toggle_theme(self) -> None:
        self.current_theme = LIGHT if self.current_theme is DARK else DARK
        self.settings.setValue("theme", "light" if self.current_theme is LIGHT else "dark")
        self.app.setStyleSheet(get_stylesheet(self.current_theme))
        self._set_theme_button()
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            package = self.table.item(row, 1).data(_PACKAGE_ROLE)
            self._style_row(row, package)
        self.table.blockSignals(False)

    def _set_theme_button(self) -> None:
        self.app_logo.setPixmap(make_icon("brand", self.current_theme["accent"], 42).pixmap(42, 42))
        for index, icon_name in enumerate(("package", "update", "storage")):
            self.tabs.setTabIcon(index, make_icon(icon_name, self.current_theme["accent"], 18))
        set_stateful_button_icon(
            self.refresh_button, "refresh", self.current_theme["accent"],
            self.current_theme["text_on_accent"], self.current_theme["text_muted"], 20,
        )
        set_stateful_button_icon(
            self.disk_refresh_button, "refresh", self.current_theme["accent"],
            self.current_theme["text_on_accent"], self.current_theme["text_muted"], 20,
        )
        set_stateful_button_icon(
            self.update_button, "update", self.current_theme["bg_primary"],
            self.current_theme["bg_primary"], self.current_theme["text_muted"], 20,
        )
        set_stateful_button_icon(
            self.remove_button, "trash", "#FFFFFF", "#FFFFFF",
            self.current_theme["text_muted"], 20,
        )
        if self.current_theme is LIGHT:
            self.theme_button.setText("Mode gelap")
            set_stateful_button_icon(
                self.theme_button, "moon", self.current_theme["text_secondary"],
                self.current_theme["accent"], self.current_theme["text_muted"], 20,
            )
        else:
            self.theme_button.setText("Mode terang")
            set_stateful_button_icon(
                self.theme_button, "sun", self.current_theme["text_secondary"],
                self.current_theme["accent"], self.current_theme["text_muted"], 20,
            )

    def _maybe_close_after_workers(self) -> None:
        if self._close_requested and not self._workers:
            QTimer.singleShot(0, self.close)

    def closeEvent(self, event) -> None:
        active = [worker for worker in self._workers if worker.isRunning()]
        if active:
            self._close_requested = True
            if self.load_worker:
                self.load_worker.cancel()
            if self.scan_worker:
                self.scan_worker.cancel()
            self.status_bar.showMessage("Menunggu operasi paket selesai sebelum keluar…")
            event.ignore()
            return
        if self.transaction_dialog and not self.transaction_dialog._complete:
            self.transaction_dialog.close()
        event.accept()

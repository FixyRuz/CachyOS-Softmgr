"""CachyOS palette and PyQt6 stylesheets for dark and light themes (v4)."""


# ─────────────────────────────────────────────────────────────────────────────
# Palet Warna
# ─────────────────────────────────────────────────────────────────────────────

# Tema Gelap: hitam kebiruan + aksen Cyan elektrik
DARK: dict[str, str] = {
    "bg_primary":    "#0B0F18",
    "bg_surface":    "#131926",
    "bg_card":       "#1A2236",
    "bg_hover":      "#1F2A42",
    "bg_selected":   "#162338",
    "border":        "#243050",
    "border_active": "#00C8F0",
    "accent":        "#00C8F0",
    "accent_dim":    "#008BAA",
    "accent_glow":   "#00C8F030",
    "accent2":       "#8B5CF6",
    "accent3":       "#F97316",
    # [NEW] Warna emas/amber untuk paket out-of-date
    "outdated":      "#F59E0B",          # amber-400
    "outdated_dim":  "#D97706",          # amber-600
    "outdated_bg":   "#F59E0B18",        # amber semi-transparent
    "outdated_glow": "#F59E0B30",
    # ─────────────
    "text_primary":   "#DCE8F8",
    "text_secondary": "#7A8FB0",
    "text_muted":     "#3A4A68",
    "text_on_accent": "#0B0F18",
    "success":        "#10D9A0",
    "success_dim":    "#0BAB7E",
    "danger":         "#F43F5E",
    "danger_dark":    "#C0293F",
    "warning":        "#FBBF24",
    "badge_pacman_fg":    "#00C8F0",
    "badge_pacman_bg":    "#00C8F012",
    "badge_pacman_border":"#00C8F040",
    "badge_aur_fg":       "#8B5CF6",
    "badge_aur_bg":       "#8B5CF612",
    "badge_aur_border":   "#8B5CF640",
    "badge_flatpak_fg":   "#F97316",
    "badge_flatpak_bg":   "#F9731612",
    "badge_flatpak_border":"#F9731640",
}

# Tema Terang: bersih, high-contrast, profesional
LIGHT: dict[str, str] = {
    "bg_primary":    "#EEF2F9",
    "bg_surface":    "#FFFFFF",
    "bg_card":       "#F5F8FE",
    "bg_hover":      "#E2EAF8",
    "bg_selected":   "#C8DFFE",
    "border":        "#C2CEDF",
    "border_active": "#0369A1",
    "accent":        "#0369A1",
    "accent_dim":    "#024F7A",
    "accent_glow":   "#0369A118",
    "accent2":       "#7C3AED",
    "accent3":       "#C2410C",
    # [NEW] Warna amber untuk out-of-date (lebih gelap agar terbaca di bg terang)
    "outdated":      "#B45309",          # amber-700 — kontras baik di bg putih
    "outdated_dim":  "#92400E",          # amber-800
    "outdated_bg":   "#FEF3C712",        # amber-100 semi-transparent
    "outdated_glow": "#F59E0B20",
    # ─────────────
    "text_primary":   "#0F1929",
    "text_secondary": "#3D5068",
    "text_muted":     "#8099B4",
    "text_on_accent": "#FFFFFF",
    "success":        "#059669",
    "success_dim":    "#047857",
    "danger":         "#DC2626",
    "danger_dark":    "#B91C1C",
    "warning":        "#B45309",
    "badge_pacman_fg":    "#0369A1",
    "badge_pacman_bg":    "#0369A112",
    "badge_pacman_border":"#0369A145",
    "badge_aur_fg":       "#7C3AED",
    "badge_aur_bg":       "#7C3AED12",
    "badge_aur_border":   "#7C3AED45",
    "badge_flatpak_fg":   "#C2410C",
    "badge_flatpak_bg":   "#C2410C12",
    "badge_flatpak_border":"#C2410C45",
}


# ─────────────────────────────────────────────────────────────────────────────
# Stylesheet Generator
# ─────────────────────────────────────────────────────────────────────────────

def get_stylesheet(t: dict) -> str:
    """
    Buat stylesheet global yang mencakup SEMUA elemen UI.

    PENTING — double-brace convention:
      CSS yang menggunakan kurung kurawal {} harus ditulis {{ }} di dalam
      f-string Python agar tidak diinterpretasikan sebagai placeholder
      variabel.  Ini adalah penyebab bug #1 (NameError: name 'background').

    Satu panggilan app.setStyleSheet(get_stylesheet(tema_baru)) cukup untuk
    memperbarui seluruh aplikasi sekaligus.
    """
    # ── [BUG FIX #1] Setiap { dan } CSS wajib ditulis {{ dan }} ────────────
    return f"""

/* ═══════════════════════════════════════════════════════
   ① BASE — Semua widget, default global
═══════════════════════════════════════════════════════ */

QMainWindow, QDialog {{
    background-color: {t['bg_primary']};
    color: {t['text_primary']};
}}

QWidget {{
    background-color: transparent;
    color: {t['text_primary']};
    font-family: "Inter", "Noto Sans", "Segoe UI", sans-serif;
    font-size: 14px;
}}

QMainWindow > QWidget {{
    background-color: {t['bg_primary']};
}}


/* ═══════════════════════════════════════════════════════
   ② HEADER PANEL
   ObjectName: header_panel, app_logo, app_title, app_subtitle
═══════════════════════════════════════════════════════ */

QWidget#header_panel {{
    background-color: {t['bg_surface']};
    border-bottom: 1px solid {t['border']};
}}

QLabel#app_logo {{
    min-width: 42px;
    min-height: 42px;
    color: {t['accent']};
    background-color: transparent;
    padding-right: 14px;
}}

QLabel#app_title {{
    font-size: 21px;
    font-weight: 800;
    color: {t['text_primary']};
    letter-spacing: 0.35px;
    background-color: transparent;
}}

QLabel#app_subtitle {{
    font-size: 10px;
    color: {t['text_muted']};
    letter-spacing: 1.6px;
    background-color: transparent;
}}

QPushButton#btn_theme_toggle {{
    background-color: transparent;
    color: {t['text_secondary']};
    border: 1px solid {t['border']};
    border-radius: 17px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.2px;
    padding: 0px;
}}
QPushButton#btn_theme_toggle:hover {{
    border-color: {t['accent']};
    color: {t['accent']};
    background-color: {t['accent_glow']};
}}
QPushButton#btn_theme_toggle:pressed {{
    background-color: {t['border']};
}}

QFrame#header_separator {{
    background-color: {t['border']};
    border: none;
    max-height: 1px;
}}


/* ═══════════════════════════════════════════════════════
   ③ STAT CARDS
   ObjectName: stat_card, sv_total, sv_pacman, sv_aur,
               sv_flatpak, sv_outdated [NEW], sk_label
═══════════════════════════════════════════════════════ */

QWidget#stat_card {{
    background-color: {t['bg_card']};
    border: 1px solid {t['border']};
    border-radius: 8px;
}}

QLabel#sv_total, QLabel#sv_pacman {{
    font-size: 20px;
    font-weight: 800;
    color: {t['accent']};
    background-color: transparent;
}}
QLabel#sv_aur {{
    font-size: 20px;
    font-weight: 800;
    color: {t['accent2']};
    background-color: transparent;
}}
QLabel#sv_flatpak {{
    font-size: 20px;
    font-weight: 800;
    color: {t['accent3']};
    background-color: transparent;
}}

/* [NEW] Kartu OUT-DATE — warna emas/amber */
QLabel#sv_outdated {{
    font-size: 20px;
    font-weight: 800;
    color: {t['outdated']};
    background-color: transparent;
}}

QLabel#sk_label {{
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    color: {t['text_secondary']};
    background-color: transparent;
}}


/* ═══════════════════════════════════════════════════════
   ④ FILTER BAR
═══════════════════════════════════════════════════════ */

QLabel#filter_info_label,
QLabel#filter_type_label {{
    font-size: 12px;
    color: {t['text_secondary']};
    background-color: transparent;
}}

QLabel#coverage_note {{
    color: {t['text_muted']};
    font-size: 11px;
    background-color: transparent;
}}

QLabel#helper_badge {{
    color: {t['accent']};
    background-color: {t['accent_glow']};
    border: 1px solid {t['border_active']};
    border-radius: 12px;
    padding: 6px 11px;
    font-size: 12px;
    font-weight: 700;
}}

QLabel#dialog_title {{
    color: {t['text_primary']};
    font-size: 18px;
    font-weight: 800;
}}

QLabel#transaction_status {{
    color: {t['accent']};
    font-size: 13px;
    font-weight: 700;
}}

QLabel#log_hint {{
    color: {t['text_muted']};
    font-size: 11px;
}}

QLabel#disk_title {{
    color: {t['text_primary']};
    font-size: 20px;
    font-weight: 750;
    letter-spacing: 0.25px;
}}
QLabel#disk_subtitle, QLabel#volume_details {{
    color: {t['text_secondary']};
    font-size: 12px;
}}
QLabel#volume_title {{
    color: {t['text_primary']};
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.2px;
}}
QLabel#volume_percentage {{
    color: {t['accent']};
    font-size: 15px;
    font-weight: 700;
}}
QLabel#disk_note {{
    color: {t['text_secondary']};
    font-size: 12px;
}}
QLabel#disk_warning {{
    color: {t['warning']};
    background-color: {t['bg_card']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 8px 12px;
}}
QFrame#volume_card {{
    background-color: {t['bg_surface']};
    border: 1px solid {t['border']};
    border-radius: 10px;
}}

QTabBar#package_tabs::tab {{
    background-color: transparent;
    color: {t['text_secondary']};
    border: 1px solid transparent;
    border-bottom: 2px solid transparent;
    padding: 10px 16px;
    margin-right: 4px;
    font-size: 14px;
    font-weight: 600;
}}
QTabBar#package_tabs::tab:selected {{
    color: {t['accent']};
    border-bottom-color: {t['accent']};
}}
QTabBar#package_tabs::tab:hover:!selected {{
    color: {t['text_primary']};
    background-color: {t['bg_hover']};
}}


/* ═══════════════════════════════════════════════════════
   ⑤ ACTION BAR
   ObjectName: action_bar, label_selected
═══════════════════════════════════════════════════════ */

QWidget#action_bar {{
    background-color: {t['bg_surface']};
    border: 1px solid {t['border']};
    border-radius: 10px;
}}

QLabel#label_selected {{
    color: {t['text_secondary']};
    font-size: 13px;
    background-color: transparent;
}}


/* ═══════════════════════════════════════════════════════
   ⑥ TABLE WIDGET
═══════════════════════════════════════════════════════ */

QTableWidget {{
    background-color: {t['bg_surface']};
    alternate-background-color: {t['bg_card']};
    border: 1px solid {t['border']};
    border-radius: 10px;
    gridline-color: transparent;
    selection-background-color: {t['bg_selected']};
    selection-color: {t['text_primary']};
    outline: none;
    show-decoration-selected: 1;
}}
QTableWidget::item {{
    padding: 0px 12px;
    border: none;
    color: {t['text_primary']};
}}
QTableWidget::item:selected {{
    background-color: {t['bg_selected']};
    color: {t['text_primary']};
    border-left: 2px solid {t['accent']};
}}
QTableWidget::item:hover:!selected {{
    background-color: {t['bg_hover']};
}}

QHeaderView {{
    background-color: {t['bg_card']};
    border: none;
}}
QHeaderView::section {{
    background-color: {t['bg_card']};
    color: {t['text_muted']};
    padding: 12px 12px;
    border: none;
    border-bottom: 1px solid {t['border']};
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.75px;
    text-transform: uppercase;
}}
QHeaderView::section:hover {{
    background-color: {t['bg_hover']};
    color: {t['text_secondary']};
}}
QHeaderView::section:first  {{ border-top-left-radius: 9px; }}
QHeaderView::section:last   {{ border-top-right-radius: 9px; }}
QHeaderView::down-arrow, QHeaderView::up-arrow {{ image: none; width: 0; height: 0; }}


/* ═══════════════════════════════════════════════════════
   ⑦ SEARCH BAR / LINE EDIT
═══════════════════════════════════════════════════════ */

QLineEdit {{
    background-color: {t['bg_card']};
    border: 1.5px solid {t['border']};
    border-radius: 8px;
    padding: 5px 14px;
    color: {t['text_primary']};
    font-size: 14px;
    selection-background-color: {t['accent']};
    selection-color: {t['text_on_accent']};
}}
QLineEdit:focus {{
    border-color: {t['accent']};
    background-color: {t['bg_surface']};
}}
QLineEdit::placeholder {{ color: {t['text_muted']}; }}


/* ═══════════════════════════════════════════════════════
   ⑧ COMBO BOX
═══════════════════════════════════════════════════════ */

QComboBox {{
    background-color: {t['bg_card']};
    border: 1.5px solid {t['border']};
    border-radius: 8px;
    padding: 7px 14px;
    color: {t['text_primary']};
    font-size: 13px;
    min-width: 120px;
}}
QComboBox:hover {{ border-color: {t['accent']}; }}
QComboBox:focus  {{ border-color: {t['accent']}; outline: none; }}
QComboBox::drop-down {{ border: none; width: 28px; subcontrol-position: right center; }}
QComboBox::down-arrow {{ image: none; width: 0px; height: 0px; border: none; }}
QComboBox QAbstractItemView {{
    background-color: {t['bg_card']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    selection-background-color: {t['bg_hover']};
    selection-color: {t['text_primary']};
    color: {t['text_primary']};
    padding: 4px;
    outline: none;
}}


/* ═══════════════════════════════════════════════════════
   ⑨ PUSH BUTTONS — Base + Variants
═══════════════════════════════════════════════════════ */

QPushButton {{
    background-color: {t['bg_card']};
    color: {t['text_primary']};
    border: 1.5px solid {t['border']};
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 500;
    font-size: 14px;
    outline: none;
}}
QPushButton:hover {{
    background-color: {t['bg_hover']};
    border-color: {t['accent']};
    color: {t['accent']};
}}
QPushButton:pressed  {{ background-color: {t['border']}; }}
QPushButton:disabled {{
    color: {t['text_muted']};
    border-color: {t['border']};
    background-color: {t['bg_card']};
}}

/* Tombol Uninstall — merah */
QPushButton#btn_uninstall {{
    background-color: {t['danger']};
    color: #FFFFFF;
    border: none;
    font-weight: 700;
    letter-spacing: 0.3px;
}}
QPushButton#btn_uninstall:hover   {{ background-color: {t['danger_dark']}; }}
QPushButton#btn_uninstall:pressed {{ background-color: {t['danger_dark']}; padding-top: 10px; }}
QPushButton#btn_uninstall:disabled {{
    background-color: {t['bg_card']};
    color: {t['text_muted']};
    border: 1.5px solid {t['border']};
    font-weight: 500;
}}

/* [NEW] Tombol Update — hijau tosca/success */
QPushButton#btn_update {{
    background-color: {t['success']};
    color: {t['bg_primary']};
    border: none;
    font-weight: 700;
    letter-spacing: 0.3px;
}}
QPushButton#btn_update:hover   {{ background-color: {t['success_dim']}; }}
QPushButton#btn_update:pressed {{ background-color: {t['success_dim']}; padding-top: 10px; }}
QPushButton#btn_update:disabled {{
    background-color: {t['bg_card']};
    color: {t['text_muted']};
    border: 1.5px solid {t['border']};
    font-weight: 500;
}}

/* Tombol Refresh — outlined */
QPushButton#btn_refresh {{
    background-color: transparent;
    border-color: {t['accent']};
    color: {t['accent']};
    font-weight: 600;
}}
QPushButton#btn_refresh:hover {{
    background-color: {t['accent']};
    color: {t['text_on_accent']};
    border-color: {t['accent']};
}}
QPushButton#btn_refresh:disabled {{
    border-color: {t['border']};
    color: {t['text_muted']};
    background-color: transparent;
}}


/* ═══════════════════════════════════════════════════════
   ⑩ PROGRESS BAR
═══════════════════════════════════════════════════════ */

QProgressBar {{
    background-color: {t['border']};
    border: none;
    border-radius: 2px;
    height: 3px;
    font-size: 0px;
}}
QProgressBar::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0   {t['accent']},
        stop:0.5 {t['accent2']},
        stop:1   {t['accent3']}
    );
    border-radius: 2px;
}}
QProgressBar#disk_meter {{
    background-color: {t['border']};
    border: none;
    border-radius: 4px;
}}
QProgressBar#disk_meter::chunk {{
    background-color: {t['accent']};
    border-radius: 4px;
}}


/* ═══════════════════════════════════════════════════════
   ⑪ SCROLLBAR
═══════════════════════════════════════════════════════ */

QScrollBar:vertical {{
    background-color: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: {t['border']};
    border-radius: 5px;
    min-height: 32px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{ background-color: {t['accent']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,  QScrollBar::sub-page:vertical {{
    height: 0; background: transparent;
}}
QScrollBar:horizontal {{
    background-color: transparent;
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background-color: {t['border']};
    border-radius: 5px;
    min-width: 32px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{ background-color: {t['accent']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,  QScrollBar::sub-page:horizontal {{
    width: 0; background: transparent;
}}


/* ═══════════════════════════════════════════════════════
   ⑫ STATUS BAR
═══════════════════════════════════════════════════════ */

QStatusBar {{
    background-color: {t['bg_surface']};
    color: {t['text_muted']};
    border-top: 1px solid {t['border']};
    font-size: 11px;
    padding: 3px 12px;
}}
QStatusBar::item {{ border: none; }}


/* ═══════════════════════════════════════════════════════
   ⑬ DIALOG & MESSAGE BOX
═══════════════════════════════════════════════════════ */

QDialog {{
    background-color: {t['bg_surface']};
}}
QMessageBox {{
    background-color: {t['bg_surface']};
    color: {t['text_primary']};
}}
QMessageBox QLabel {{
    color: {t['text_primary']};
    font-size: 14px;
    line-height: 1.35;
}}
QMessageBox QPushButton {{
    min-width: 160px;
    min-height: 42px;
    padding: 7px 12px;
    font-size: 14px;
    font-weight: 600;
}}


/* ═══════════════════════════════════════════════════════
   ⑭ TEXT EDIT (terminal output di dialog)
═══════════════════════════════════════════════════════ */

QTextEdit#terminal_output, QPlainTextEdit#terminal_output,
QPlainTextEdit#details_output {{
    background-color: {t['bg_primary']};
    color: {t['accent']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 11px;
    padding: 10px;
    selection-background-color: {t['accent']};
    selection-color: {t['text_on_accent']};
}}


/* ═══════════════════════════════════════════════════════
   ⑮ TOOLTIP
═══════════════════════════════════════════════════════ */

QToolTip {{
    background-color: {t['bg_card']};
    color: {t['text_primary']};
    border: 1px solid {t['border']};
    border-radius: 5px;
    padding: 5px 10px;
    font-size: 11px;
}}


/* ═══════════════════════════════════════════════════════
   ⑯ FRAME / SEPARATOR GENERIK
═══════════════════════════════════════════════════════ */

QFrame[frameShape="4"],
QFrame[frameShape="5"] {{
    color: {t['border']};
    background-color: {t['border']};
}}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Badge Style untuk Dialog
# ─────────────────────────────────────────────────────────────────────────────

def get_badge_style(source: str, t: dict) -> str:
    """
    Inline style untuk badge pill sumber paket di ConfirmUninstallDialog.
    Hanya digunakan di dialog (lifetime singkat) — acceptable pakai inline.

    [BUG FIX #1] f-string di sini juga menggunakan double-brace {{ }}.
    """
    key_map = {
        "Pacman":  ("badge_pacman_fg",  "badge_pacman_bg",  "badge_pacman_border"),
        "AUR":     ("badge_aur_fg",     "badge_aur_bg",     "badge_aur_border"),
        "Flatpak": ("badge_flatpak_fg", "badge_flatpak_bg", "badge_flatpak_border"),
    }
    fg_k, bg_k, bd_k = key_map.get(source, key_map["Pacman"])
    fg = t.get(fg_k, t["accent"])
    bg = t.get(bg_k, t["bg_card"])
    bd = t.get(bd_k, t["border"])
    # [BUG FIX #1] double braces {{ }} agar f-string tidak error
    return f"""
        QLabel {{
            background-color: {bg};
            color: {fg};
            border: 1px solid {bd};
            border-radius: 4px;
            padding: 2px 9px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.2px;
        }}
    """

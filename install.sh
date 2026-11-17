#!/usr/bin/env bash
# Install CachyOS Softmgr on CachyOS / Arch Linux.

set -euo pipefail

APP_NAME="cachyos-softmgr"
INSTALL_DIR="/opt/${APP_NAME}"
BIN_LINK="/usr/local/bin/${APP_NAME}"
DESKTOP_FILE="/usr/share/applications/${APP_NAME}.desktop"
ICON_FILE="/usr/share/icons/hicolor/scalable/apps/${APP_NAME}.svg"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=false

usage() {
    printf 'Pemakaian: %s [--dry-run]\n' "$0"
    printf 'Pasang CachyOS Softmgr dan daftarkan launcher desktop.\n'
}

if [[ "$#" -gt 1 ]]; then
    usage >&2
    exit 2
fi
case "${1:-}" in
    "") ;;
    --dry-run) DRY_RUN=true ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Opsi tidak dikenal: %s\n' "$1" >&2; usage >&2; exit 2 ;;
esac

REQUIRED_FILES=(
    main.py main_window.py backend.py workers.py theme.py icons.py disk_report.py README.md VERSION
    TAG.txt LICENSE uninstall.sh cachyos-softmgr.desktop assets/cachyos-softmgr.svg assets/Icon.svg
)
for file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -s "${SCRIPT_DIR}/${file}" ]]; then
        printf 'File aplikasi wajib tidak ditemukan atau kosong: %s\n' "$file" >&2
        exit 1
    fi
done
IFS= read -r APP_VERSION < "${SCRIPT_DIR}/VERSION"

printf 'CachyOS Softmgr v%s\n' "$APP_VERSION"
printf 'Folder aplikasi : %s\nLauncher        : %s\nMenu desktop    : %s\n' \
    "$INSTALL_DIR" "$BIN_LINK" "$DESKTOP_FILE"
printf 'Dependensi      : python, python-pyqt6, polkit, qt6-base, qt6-wayland\n'
printf 'Installer akan menjalankan pacman -Syu agar pemasangan tidak membuat partial upgrade.\n'

if [[ "${DRY_RUN}" == true ]]; then
    printf '\nMode simulasi: tidak ada dependensi atau file sistem yang diubah.\n'
    exit 0
fi

if [[ ! -t 0 || ! -t 1 ]]; then
    printf 'Jalankan install.sh dari terminal interaktif agar persetujuan pacman dapat ditampilkan.\n' >&2
    printf 'Gunakan --dry-run untuk melihat rencana pemasangan tanpa terminal.\n' >&2
    exit 2
fi
command -v pacman >/dev/null || { printf 'pacman tidak ditemukan; installer ini untuk CachyOS/Arch.\n' >&2; exit 1; }

if [[ "${EUID}" -eq 0 ]]; then
    SUDO=()
else
    command -v sudo >/dev/null || { printf 'sudo tidak ditemukan.\n' >&2; exit 1; }
    sudo -v
    SUDO=(sudo)
fi

step() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
ok() { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m⚠ %s\033[0m\n' "$*"; }

step "Memasang dependensi sistem"
printf 'Pacman akan menampilkan ringkasan transaksi dan meminta persetujuan sebelum melanjutkan.\n'
"${SUDO[@]}" pacman -Syu --needed python python-pyqt6 polkit qt6-base qt6-wayland
command -v python >/dev/null || { printf 'Python tidak tersedia setelah pemasangan dependensi.\n' >&2; exit 1; }

step "Menyalin aplikasi ke ${INSTALL_DIR}"
"${SUDO[@]}" install -d -m 755 "${INSTALL_DIR}"
for file in main.py main_window.py backend.py workers.py theme.py icons.py disk_report.py README.md VERSION TAG.txt LICENSE; do
    "${SUDO[@]}" install -m 644 "${SCRIPT_DIR}/${file}" "${INSTALL_DIR}/${file}"
done
"${SUDO[@]}" install -D -m 644 "${SCRIPT_DIR}/assets/cachyos-softmgr.svg" "${ICON_FILE}"
"${SUDO[@]}" install -D -m 644 "${SCRIPT_DIR}/assets/cachyos-softmgr.svg" "${INSTALL_DIR}/assets/cachyos-softmgr.svg"
"${SUDO[@]}" install -D -m 644 "${SCRIPT_DIR}/assets/Icon.svg" "${INSTALL_DIR}/assets/Icon.svg"
"${SUDO[@]}" install -m 755 "${SCRIPT_DIR}/uninstall.sh" "${INSTALL_DIR}/uninstall.sh"
"${SUDO[@]}" install -m 644 "${SCRIPT_DIR}/cachyos-softmgr.desktop" "${DESKTOP_FILE}"

step "Mendaftarkan launcher"
LAUNCHER_TMP="$(mktemp)"
trap 'rm -f -- "${LAUNCHER_TMP}"' EXIT
cat >"${LAUNCHER_TMP}" <<EOF
#!/usr/bin/env bash
exec /usr/bin/env python "${INSTALL_DIR}/main.py" "\$@"
EOF
"${SUDO[@]}" install -m 755 "${LAUNCHER_TMP}" "${BIN_LINK}"

step "Memeriksa instalasi"
for file in main.py main_window.py backend.py workers.py theme.py icons.py disk_report.py assets/Icon.svg assets/cachyos-softmgr.svg uninstall.sh; do
    [[ -s "${INSTALL_DIR}/${file}" ]] || { printf 'File instalasi tidak lengkap: %s\n' "$file" >&2; exit 1; }
done
[[ -x "${INSTALL_DIR}/uninstall.sh" ]] || { printf 'Uninstaller tidak executable.\n' >&2; exit 1; }
[[ -x "${BIN_LINK}" ]] || { printf 'Launcher tidak executable.\n' >&2; exit 1; }
[[ -s "${DESKTOP_FILE}" ]] || { printf 'Entri menu desktop tidak ditemukan.\n' >&2; exit 1; }

if command -v update-desktop-database >/dev/null; then
    "${SUDO[@]}" update-desktop-database /usr/share/applications >/dev/null 2>&1 || warn "Cache menu desktop tidak dapat diperbarui otomatis."
fi
if command -v gtk-update-icon-cache >/dev/null; then
    "${SUDO[@]}" gtk-update-icon-cache -f /usr/share/icons/hicolor >/dev/null 2>&1 || warn "Cache ikon tidak dapat diperbarui otomatis."
fi
if command -v flatpak >/dev/null; then
    ok "Flatpak terdeteksi."
else
    warn "Flatpak tidak terpasang; fitur Pacman dan AUR tetap tersedia."
fi
if command -v paru >/dev/null; then
    ok "Helper AUR paru terdeteksi."
elif command -v yay >/dev/null; then
    ok "Helper AUR yay terdeteksi."
else
    warn "paru/yay tidak ditemukan; integrasi AUR belum aktif."
fi

printf '\n\033[1;32mCachyOS Softmgr v%s berhasil dipasang.\033[0m\n' "$APP_VERSION"
printf 'Jalankan %s atau cari CachyOS Softmgr di menu aplikasi.\n' "$BIN_LINK"
printf 'Copot aplikasi dengan %s/uninstall.sh.\n' "$INSTALL_DIR"

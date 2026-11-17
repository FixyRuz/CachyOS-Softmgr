#!/usr/bin/env bash
# Remove CachyOS Softmgr files installed by install.sh.

set -euo pipefail

APP_NAME="cachyos-softmgr"
INSTALL_DIR="/opt/${APP_NAME}"
BIN_LINK="/usr/local/bin/${APP_NAME}"
DESKTOP_FILE="/usr/share/applications/${APP_NAME}.desktop"
ICON_FILE="/usr/share/icons/hicolor/scalable/apps/${APP_NAME}.svg"
DRY_RUN=false

case "${1:-}" in
    "") ;;
    --dry-run) DRY_RUN=true ;;
    --help|-h)
        printf 'Pemakaian: %s [--dry-run]\n' "$0"
        printf 'Menghapus file aplikasi CachyOS Softmgr dari lokasi instalasi sistem.\n'
        exit 0
        ;;
    *)
        printf 'Opsi tidak dikenal: %s\n' "$1" >&2
        printf 'Gunakan --help untuk bantuan.\n' >&2
        exit 2
        ;;
esac

TARGETS=("${INSTALL_DIR}" "${BIN_LINK}" "${DESKTOP_FILE}" "${ICON_FILE}")

printf 'File yang akan dihapus:\n'
for target in "${TARGETS[@]}"; do
    printf '  %s\n' "$target"
done
printf '\nData pengguna, paket Pacman/AUR/Flatpak, dan dependensi sistem tidak dihapus.\n'

if [[ "${DRY_RUN}" == true ]]; then
    printf '\nMode simulasi: tidak ada file yang diubah.\n'
    exit 0
fi

if [[ ! -t 0 ]]; then
    printf 'Jalankan uninstall.sh dari terminal interaktif, atau gunakan --dry-run untuk simulasi.\n' >&2
    exit 2
fi

read -r -p 'Lanjutkan menghapus CachyOS Softmgr? [y/N] ' answer
if [[ "${answer,,}" != "y" && "${answer,,}" != "yes" ]]; then
    printf 'Penghapusan dibatalkan.\n'
    exit 0
fi

if [[ "${EUID}" -eq 0 ]]; then
    SUDO=()
else
    command -v sudo >/dev/null || { printf 'sudo tidak ditemukan.\n' >&2; exit 1; }
    sudo -v
    SUDO=(sudo)
fi

for target in "${TARGETS[@]}"; do
    if [[ -e "${target}" || -L "${target}" ]]; then
        "${SUDO[@]}" rm -rf -- "${target}"
        printf 'Dihapus: %s\n' "$target"
    else
        printf 'Sudah tidak ada: %s\n' "$target"
    fi
done

if command -v update-desktop-database >/dev/null; then
    "${SUDO[@]}" update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null; then
    "${SUDO[@]}" gtk-update-icon-cache -f /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

printf '\nCachyOS Softmgr berhasil dihapus. Data pengguna dan paket sistem tetap tersimpan.\n'

"""Package queries and operations for CachyOS Software Manager."""

from __future__ import annotations

import logging
import os
import queue
import re
import shlex
import shutil
import stat
import subprocess
import threading
import time
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, Iterable


APP_NAME = "cachyos-softmgr"
CACHE_TTL = 300.0
UPDATE_TTL = 120.0
PACMAN_LOCK = Path("/var/lib/pacman/db.lck")
PackageKey = tuple[str, str, str, str]
OutputCallback = Callable[[str], None]


@dataclass
class Package:
    name: str
    version: str
    size: str
    source: str
    description: str = ""
    app_id: str = ""
    is_outdated: bool = False
    new_version: str = ""
    origin: str = ""
    installation: str = ""
    dependencies: str = ""
    install_date: str = ""

    @property
    def key(self) -> PackageKey:
        return self.source, self.name, self.app_id, self.installation


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and not self.timed_out


@dataclass(frozen=True)
class UpdateScanResult:
    updates: dict[PackageKey, str]
    warnings: list[str]


class BackendError(RuntimeError):
    """Raised when installed-package inventory cannot be read."""


class _TTLCache:
    def __init__(self, ttl: float):
        self.ttl = ttl
        self.value = None
        self.updated_at = 0.0

    def get(self):
        if self.value is not None and time.monotonic() - self.updated_at < self.ttl:
            return self.value
        return None

    def set(self, value) -> None:
        self.value = value
        self.updated_at = time.monotonic()

    def clear(self) -> None:
        self.value = None
        self.updated_at = 0.0


_packages_cache = _TTLCache(CACHE_TTL)
_updates_cache = _TTLCache(UPDATE_TTL)


def get_log_path() -> Path:
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache_home / APP_NAME / "app.log"


def _logger() -> logging.Logger:
    logger = logging.getLogger(APP_NAME)
    if logger.handlers:
        return logger
    try:
        path = get_log_path()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    except OSError:
        logger.addHandler(logging.NullHandler())
    return logger


def _pacman_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update({"LC_ALL": "C", "LANG": "C"})
    return env


def _run_command(
    command: Iterable[str],
    *,
    timeout: float | None = 60,
    env: dict[str, str] | None = None,
    on_output: OutputCallback | None = None,
    label: str = "command",
) -> CommandResult:
    """Run an argument vector, stream both pipes, and log output and outcome."""
    args = tuple(str(part) for part in command)
    logger = _logger()
    started = time.monotonic()
    logger.info("START [%s] %s", label, shlex.join(args))
    try:
        process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            close_fds=True,
        )
    except OSError as exc:
        duration = time.monotonic() - started
        logger.error("SPAWN FAILED [%s] %.2fs: %s", label, duration, exc)
        return CommandResult(args, 127, "", str(exc), duration)

    lines: queue.Queue[tuple[str, str | None]] = queue.Queue()

    def read_pipe(name: str, stream) -> None:
        try:
            for line in iter(stream.readline, ""):
                lines.put((name, line))
        finally:
            lines.put((name, None))
            stream.close()

    readers = [
        threading.Thread(target=read_pipe, args=("stdout", process.stdout), daemon=True),
        threading.Thread(target=read_pipe, args=("stderr", process.stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()

    output: dict[str, list[str]] = {"stdout": [], "stderr": []}
    ended: set[str] = set()
    timed_out = False
    while len(ended) < 2:
        if timeout is not None and not timed_out and time.monotonic() - started > timeout:
            timed_out = True
            logger.error("TIMEOUT [%s] after %.1fs", label, timeout)
            try:
                process.kill()
            except ProcessLookupError:
                pass
        try:
            channel, line = lines.get(timeout=0.1)
        except queue.Empty:
            continue
        if line is None:
            ended.add(channel)
            continue
        output[channel].append(line)
        logger.debug("OUTPUT [%s:%s] %s", label, channel, line.rstrip())
        if on_output is not None:
            try:
                on_output(line)
            except Exception:
                logger.exception("Output callback failed for %s", label)

    for reader in readers:
        reader.join(timeout=0.2)
    returncode = process.wait()
    duration = time.monotonic() - started
    logger.info("END [%s] code=%s duration=%.2fs timeout=%s", label, returncode, duration, timed_out)
    if output["stderr"]:
        logger.warning("STDERR [%s]\n%s", label, "".join(output["stderr"]).rstrip())
    return CommandResult(
        args, returncode, "".join(output["stdout"]), "".join(output["stderr"]), duration, timed_out
    )


def _result_text(result: CommandResult, action: str) -> str:
    if result.timed_out:
        return f"{action} melewati batas waktu ({int(result.duration)} detik). Lihat log untuk detail."
    if result.returncode == 126:
        return "Operasi dibatalkan pada dialog otorisasi Polkit."
    if result.returncode == 127:
        return "Perintah tidak dapat dijalankan. Pastikan program yang dibutuhkan terpasang."
    combined = "\n".join(x.strip() for x in (result.stdout, result.stderr) if x.strip())
    if "CACHYOS_SOFTMGR_AUTH_CANCELLED" in combined:
        return "Operasi AUR dibatalkan pada dialog password."
    if result.succeeded:
        return f"{action} selesai."
    if combined:
        lines = combined.splitlines()
        if len(lines) > 30:
            return "… (bagian akhir output) …\n" + "\n".join(lines[-30:])
        return combined
    return f"{action} gagal (kode {result.returncode})."


def invalidate_cache() -> None:
    _packages_cache.clear()
    _updates_cache.clear()


def is_flatpak_available() -> bool:
    return shutil.which("flatpak") is not None


def is_pkexec_available() -> bool:
    return shutil.which("pkexec") is not None


def get_aur_helper() -> str | None:
    """Prefer paru when present, otherwise use yay."""
    return shutil.which("paru") or shutil.which("yay")


def get_aur_helper_name() -> str | None:
    path = get_aur_helper()
    return Path(path).name if path else None


def is_critical_package(name: str) -> bool:
    name = name.strip().casefold()
    fixed = {
        "archlinux-keyring", "archlinux-mirrorlist", "base",
        "bash", "btrfs-progs", "cachyos-hooks", "cachyos-keyring",
        "cachyos-mirrorlist", "cachyos-settings", "coreutils", "cryptsetup",
        "dbus", "dhcpcd", "dosfstools", "dracut", "e2fsprogs",
        "efibootmgr", "filesystem", "gdm", "glibc", "gnome-shell", "grub",
        "iwd", "lightdm", "linux-firmware", "lvm2", "mdadm", "mkinitcpio",
        "networkmanager", "pacman", "plasma-desktop", "plasma-workspace",
        "polkit", "refind", "sddm", "sudo", "systemd", "systemd-boot",
        "systemd-libs", "util-linux", "wayland", "wpa_supplicant",
        "xorg-server", "xfsprogs",
    }
    return name in fixed or name.startswith(("linux", "mkinitcpio", "systemd-"))


def _check_pacman_lock() -> str | None:
    if PACMAN_LOCK.exists():
        return f"Pacman sedang dipakai proses lain ({PACMAN_LOCK}). Tunggu proses itu selesai lalu coba lagi."
    return None


def get_all_packages(force: bool = False) -> list[Package]:
    if not force:
        cached = _packages_cache.get()
        if cached is not None:
            return list(cached)
    packages = get_pacman_packages()
    if is_flatpak_available():
        try:
            packages.extend(get_flatpak_packages())
        except BackendError as exc:
            _logger().warning("Flatpak inventory unavailable: %s", exc)
    packages.sort(key=lambda package: (package.name.casefold(), package.source, package.installation))
    _packages_cache.set(packages)
    return list(packages)


def get_pacman_packages() -> list[Package]:
    env = _pacman_env()
    foreign_result = _run_command(["pacman", "-Qmq"], env=env, timeout=30, label="pacman foreign packages")
    foreign = {line.strip() for line in foreign_result.stdout.splitlines() if line.strip()} if foreign_result.succeeded else set()

    result = _run_command(["pacman", "-Qei"], env=env, timeout=90, label="pacman package inventory")
    if result.succeeded and result.stdout.strip():
        return _parse_pacman_qi_output(result.stdout, foreign)
    fallback = _run_command(["pacman", "-Qe"], env=env, timeout=60, label="pacman inventory fallback")
    if fallback.succeeded:
        packages = []
        for line in fallback.stdout.splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                name, version = parts
                packages.append(Package(name, version, "N/A", "AUR" if name in foreign else "Pacman", app_id=name))
        return packages
    raise BackendError(_result_text(result, "Membaca daftar paket Pacman") + "\n" + _result_text(fallback, "Fallback Pacman"))


def _parse_pacman_qi_output(output: str, foreign_packages: set[str]) -> list[Package]:
    packages: list[Package] = []
    current: dict[str, str] = {}
    for raw_line in output.splitlines() + [""]:
        if not raw_line.strip():
            if current.get("Name"):
                packages.append(_build_pacman_package(current, foreign_packages))
            current = {}
            continue
        if raw_line[0].isspace():
            continue
        if ":" in raw_line:
            key, _, value = raw_line.partition(":")
            current[key.strip()] = value.strip()
    return packages


def _build_pacman_package(data: dict[str, str], foreign_packages: set[str]) -> Package:
    name = data.get("Name", "unknown")
    return Package(
        name=name,
        version=data.get("Version", "Unknown"),
        size=data.get("Installed Size", "Unknown"),
        source="AUR" if name in foreign_packages else "Pacman",
        description=data.get("Description", ""),
        app_id=name,
        dependencies=data.get("Depends On", ""),
        install_date=data.get("Install Date", ""),
    )


def get_flatpak_packages() -> list[Package]:
    if not is_flatpak_available():
        return []
    fields = "name,application,version,size,origin,installation,description"
    result = _run_command(["flatpak", "list", "--app", f"--columns={fields}"], timeout=60, label="flatpak inventory")
    if not result.succeeded:
        raise BackendError(_result_text(result, "Membaca daftar Flatpak"))
    packages: list[Package] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2 or not parts[1].strip():
            continue
        name, app_id = parts[0].strip(), parts[1].strip()
        packages.append(Package(
            name=name or app_id,
            version=parts[2].strip() if len(parts) > 2 else "Unknown",
            size=parts[3].strip() if len(parts) > 3 else "Unknown",
            source="Flatpak",
            description=parts[6].strip() if len(parts) > 6 else "",
            app_id=app_id,
            origin=parts[4].strip() if len(parts) > 4 else "",
            installation=parts[5].strip() if len(parts) > 5 else "system",
        ))
    return packages


def _parse_upgrade_lines(output: str) -> dict[str, str]:
    upgrades: dict[str, str] = {}
    for raw_line in output.splitlines():
        match = re.match(r"^\s*([A-Za-z0-9@._+:-]+)\s+\S+\s+->\s+(\S+)\s*$", raw_line)
        if match:
            upgrades[match.group(1)] = match.group(2)
    return upgrades


def get_outdated_packages(force: bool = False) -> UpdateScanResult:
    if not force:
        cached = _updates_cache.get()
        if cached is not None:
            return cached
    upgrades: dict[PackageKey, str] = {}
    warnings: list[str] = []
    pacman = _run_command(["pacman", "-Qu"], env=_pacman_env(), timeout=30, label="pacman update check")
    if not pacman.succeeded and pacman.returncode != 1:
        warnings.append("Pacman: " + _result_text(pacman, "Cek update"))
    for name, version in _parse_upgrade_lines(pacman.stdout).items():
        upgrades[("Pacman", name, name, "")] = version

    helper = get_aur_helper()
    if helper:
        aur = _run_command([helper, "-Qua"], timeout=30, label=f"{Path(helper).name} AUR update check")
        if not aur.succeeded:
            warnings.append(f"{Path(helper).name}: " + _result_text(aur, "Cek update AUR"))
        for name, version in _parse_upgrade_lines(aur.stdout).items():
            upgrades[("AUR", name, name, "")] = version
    elif _get_foreign_names():
        warnings.append("Paket AUR/foreign terpasang, tetapi paru maupun yay tidak ditemukan.")

    if is_flatpak_available():
        try:
            installed_flatpaks = get_flatpak_packages()
        except BackendError as exc:
            warnings.append("Flatpak: " + str(exc))
            installed_flatpaks = []
        scopes = dict.fromkeys(package.installation or "system" for package in installed_flatpaks)
        for installation in scopes:
            flatpak_updates = _run_command(
                ["flatpak", "remote-ls", *_flatpak_scope_args(installation), "--updates", "--app", "--columns=application,version"],
                timeout=45,
                label=f"flatpak update check ({installation})",
            )
            if not flatpak_updates.succeeded:
                warnings.append(f"Flatpak ({installation}): " + _result_text(flatpak_updates, "Cek update"))
                continue
            installed_by_id: dict[str, list[Package]] = {}
            for package in installed_flatpaks:
                if (package.installation or "system") == installation:
                    installed_by_id.setdefault(package.app_id, []).append(package)
            for line in flatpak_updates.stdout.splitlines():
                parts = [part.strip() for part in line.split("\t")]
                if not parts or not parts[0] or parts[0].casefold() == "application":
                    continue
                app_id = parts[0]
                version = parts[1] if len(parts) > 1 and parts[1] else "Update tersedia"
                for package in installed_by_id.get(app_id, []):
                    upgrades[package.key] = version

    result = UpdateScanResult(upgrades, warnings)
    _updates_cache.set(result)
    return result


def _validate_names(names: Iterable[str], pattern: str, label: str) -> list[str]:
    values = list(dict.fromkeys(names))
    if any(not re.fullmatch(pattern, value) for value in values):
        raise ValueError(f"Nama {label} berisi karakter yang tidak valid.")
    return values


def _askpass_path() -> Path:
    directory = get_log_path().parent / "askpass"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        directory.chmod(0o700)
    except OSError:
        pass
    path = directory / "sudo-askpass.py"
    source = '''#!/usr/bin/env python3
import sys
from PyQt6.QtWidgets import QApplication, QInputDialog, QLineEdit

app = QApplication([])
prompt = sys.argv[1] if len(sys.argv) > 1 else "Masukkan kata sandi sudo"
password, accepted = QInputDialog.getText(None, "Otorisasi AUR", prompt, QLineEdit.EchoMode.Password)
if accepted:
    sys.stdout.write(password + "\\n")
    sys.stdout.flush()
    raise SystemExit(0)
sys.stderr.write("CACHYOS_SOFTMGR_AUTH_CANCELLED\\n")
raise SystemExit(1)
'''
    if not path.exists() or path.read_text(encoding="utf-8") != source:
        path.write_text(source, encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return path


def _sudo_askpass_wrapper_path() -> Path | None:
    sudo = shutil.which("sudo")
    if not sudo:
        return None
    directory = get_log_path().parent / "askpass"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        directory.chmod(0o700)
    except OSError:
        pass
    path = directory / "sudo-askpass-wrapper"
    source = f"#!/bin/sh\nexec {shlex.quote(sudo)} -A \"$@\"\n"
    if not path.exists() or path.read_text(encoding="utf-8") != source:
        path.write_text(source, encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return path


def _helper_env() -> dict[str, str]:
    env = _pacman_env()
    env["SUDO_ASKPASS"] = str(_askpass_path())
    env["SUDO_PROMPT"] = "Password diperlukan untuk memasang paket AUR: "
    return env


def _run_pacman_update(names: list[str] | None, on_output: OutputCallback | None) -> tuple[bool, str]:
    lock_error = _check_pacman_lock()
    if lock_error:
        return False, lock_error
    if not is_pkexec_available():
        return False, "pkexec tidak ditemukan. Pastikan Polkit terpasang dan aktif."
    if names:
        targets = _validate_names(names, r"[A-Za-z0-9@._+:-]+", "paket")
        args = ["pkexec", "/usr/bin/pacman", "-Syu", "--needed", "--noconfirm", *targets]
    else:
        args = ["pkexec", "/usr/bin/pacman", "-Syu", "--noconfirm"]
    result = _run_command(args, timeout=None, env=_pacman_env(), on_output=on_output, label="Pacman update")
    if result.succeeded:
        invalidate_cache()
    return result.succeeded, _result_text(result, "Update Pacman")


def _run_aur_update(names: list[str] | None, helper: str, on_output: OutputCallback | None) -> tuple[bool, str]:
    helper_path = shutil.which(helper) if helper in {"paru", "yay"} else shutil.which("paru") or shutil.which("yay")
    if not helper_path:
        return False, "AUR dilewati: paru maupun yay tidak ditemukan."
    sudo_wrapper = _sudo_askpass_wrapper_path()
    if not sudo_wrapper:
        return False, "AUR dilewati: sudo tidak ditemukan untuk otorisasi pemasangan paket."
    if names:
        targets = _validate_names(names, r"[A-Za-z0-9@._+:-]+", "paket AUR")
        args = [helper_path, "-S", "--aur", "--needed", "--noconfirm", "--sudo", str(sudo_wrapper), *targets]
    else:
        args = [helper_path, "-Sua", "--noconfirm", "--sudo", str(sudo_wrapper)]
    result = _run_command(
        args,
        timeout=None,
        env=_helper_env(),
        on_output=on_output,
        label=f"{Path(helper_path).name} AUR update",
    )
    if result.succeeded:
        invalidate_cache()
    return result.succeeded, _result_text(result, "Update AUR")


def _flatpak_scope_args(installation: str) -> list[str]:
    value = (installation or "system").casefold()
    if value in {"user", "user installation"}:
        return ["--user"]
    if value in {"system", "default", "system installation"}:
        return ["--system"]
    return [f"--installation={installation}"]


def _run_flatpak_update(packages: list[Package] | None, on_output: OutputCallback | None) -> tuple[bool, str]:
    if not is_flatpak_available():
        return False, "Flatpak dilewati: flatpak tidak terpasang."
    groups: dict[str, list[Package]] = {}
    if packages is None:
        try:
            installed = get_flatpak_packages()
        except BackendError as exc:
            return False, "Tidak dapat membaca instalasi Flatpak: " + str(exc)
        for package in installed:
            groups.setdefault(package.installation or "system", [])
        if not groups:
            return True, "Tidak ada aplikasi Flatpak terpasang untuk diperbarui."
    else:
        for package in packages:
            groups.setdefault(package.installation or "system", []).append(package)
    results = []
    for installation, group in groups.items():
        args = ["flatpak", "update", "--noninteractive", "--assumeyes"]
        if installation:
            args.extend(_flatpak_scope_args(installation))
        if group:
            ids = _validate_names((package.app_id for package in group), r"[A-Za-z0-9_.+-]+", "Application ID")
            args.extend(ids)
        result = _run_command(args, timeout=None, on_output=on_output, label="Flatpak update")
        results.append((result.succeeded, _result_text(result, "Update Flatpak")))
        if result.succeeded:
            invalidate_cache()
    return all(success for success, _ in results), "\n\n".join(message for _, message in results)


def update_packages(
    packages: list[Package] | None = None,
    *,
    update_all: bool = False,
    on_output: OutputCallback | None = None,
) -> tuple[bool, str]:
    """Update Pacman, AUR, and Flatpak as separate, logged transactions."""
    if update_all:
        selected = None
        selected_pacman = selected_aur = selected_flatpak = None
    else:
        selected = packages or []
        if not selected:
            return False, "Tidak ada paket yang dipilih."
        selected_pacman = [p.name for p in selected if p.source == "Pacman"]
        selected_aur = [p.name for p in selected if p.source == "AUR"]
        selected_flatpak = [p for p in selected if p.source == "Flatpak"]

    reports: list[tuple[str, bool, str]] = []
    # Refresh repo packages before building AUR packages. Even AUR-only selection
    # needs this full system sync to avoid a partial-upgrade build environment.
    if update_all or selected_pacman or selected_aur:
        ok, message = _run_pacman_update(None if update_all or selected_aur else selected_pacman, on_output)
        reports.append(("Pacman", ok, message))
    else:
        ok = True

    if update_all:
        helper = get_aur_helper()
        foreign = _get_foreign_names()
        if helper and foreign:
            aur_ok, aur_message = _run_aur_update(None, helper, on_output) if ok else (
                False, "AUR dilewati karena pembaruan Pacman gagal; sinkronkan sistem sebelum membangun paket AUR."
            )
            reports.append(("AUR", aur_ok, aur_message))
        elif foreign and not helper:
            reports.append(("AUR", False, "Paket AUR/foreign terpasang, tetapi paru/yay tidak ditemukan."))
    elif selected_aur:
        helper = get_aur_helper()
        if not helper:
            reports.append(("AUR", False, "Update AUR memerlukan paru atau yay."))
        elif ok:
            aur_ok, aur_message = _run_aur_update(selected_aur, helper, on_output)
            reports.append(("AUR", aur_ok, aur_message))
        else:
            reports.append(("AUR", False, "AUR dilewati karena pembaruan Pacman gagal."))

    if update_all or selected_flatpak:
        flat_ok, flat_message = _run_flatpak_update(selected_flatpak, on_output)
        if is_flatpak_available():
            reports.append(("Flatpak", flat_ok, flat_message))

    success = all(ok for _, ok, _ in reports) if reports else False
    summary = "\n\n".join(f"[{source}] {'BERHASIL' if ok else 'GAGAL / DILEWATI'}\n{message}" for source, ok, message in reports)
    _logger().info("UPDATE SUMMARY success=%s sources=%s", success, ",".join(source for source, _, _ in reports))
    return success, summary


def update_all_packages(on_output: OutputCallback | None = None) -> tuple[bool, str]:
    return update_packages(update_all=True, on_output=on_output)


def _get_foreign_names() -> list[str]:
    result = _run_command(["pacman", "-Qmq"], env=_pacman_env(), timeout=30, label="foreign package query")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()] if result.succeeded else []


def _run_pacman_uninstall(names: list[str], on_output: OutputCallback | None) -> tuple[bool, str]:
    lock_error = _check_pacman_lock()
    if lock_error:
        return False, lock_error
    if not names:
        return True, "Tidak ada paket Pacman/AUR terpilih."
    if not is_pkexec_available():
        return False, "pkexec tidak ditemukan. Pastikan Polkit terpasang dan aktif."
    targets = _validate_names(names, r"[A-Za-z0-9@._+:-]+", "paket")
    result = _run_command(
        ["pkexec", "/usr/bin/pacman", "--noconfirm", "-Rs", *targets],
        timeout=None,
        env=_pacman_env(),
        on_output=on_output,
        label="Pacman batch uninstall",
    )
    if result.succeeded:
        invalidate_cache()
        return True, _result_text(result, "Uninstall Pacman/AUR")
    message = _result_text(result, "Uninstall Pacman/AUR")
    if result.returncode not in (126, 127):
        message += (
            "\n\nPacman menghapus paket dalam satu transaksi. Jika satu paket masih "
            "dibutuhkan paket lain, seluruh batch Pacman dapat ditolak. Coba pilih "
            "paket yang tidak terkait secara terpisah."
        )
    return False, message


def _run_flatpak_uninstall(packages: list[Package], on_output: OutputCallback | None) -> tuple[bool, str]:
    if not packages:
        return True, "Tidak ada aplikasi Flatpak terpilih."
    if not is_flatpak_available():
        return False, "flatpak tidak ditemukan."
    groups: dict[str, list[Package]] = {}
    for package in packages:
        groups.setdefault(package.installation or "system", []).append(package)
    reports = []
    for installation, group in groups.items():
        ids = _validate_names((p.app_id for p in group), r"[A-Za-z0-9_.+-]+", "Application ID")
        command = ["flatpak", "uninstall", "--noninteractive", "--assumeyes"]
        command.extend(_flatpak_scope_args(installation))
        command.extend(ids)
        result = _run_command(command, timeout=None, on_output=on_output, label="Flatpak batch uninstall")
        reports.append((result.succeeded, _result_text(result, "Uninstall Flatpak")))
        if result.succeeded:
            invalidate_cache()
    return all(ok for ok, _ in reports), "\n\n".join(message for _, message in reports)


def batch_uninstall_packages(
    packages: list[Package], on_output: OutputCallback | None = None
) -> tuple[bool, str]:
    if not packages:
        return False, "Tidak ada paket yang dipilih."
    package_names = [p.name for p in packages if p.source in {"Pacman", "AUR"}]
    flatpak_packages = [p for p in packages if p.source == "Flatpak"]
    reports = []
    if package_names:
        ok, message = _run_pacman_uninstall(package_names, on_output)
        reports.append(("Pacman/AUR", ok, message))
    if flatpak_packages:
        ok, message = _run_flatpak_uninstall(flatpak_packages, on_output)
        reports.append(("Flatpak", ok, message))
    unknown = [p for p in packages if p.source not in {"Pacman", "AUR", "Flatpak"}]
    if unknown:
        reports.append(("Tidak dikenal", False, ", ".join(p.name for p in unknown)))
    success = all(ok for _, ok, _ in reports)
    text = "\n\n".join(f"[{source}] {'BERHASIL' if ok else 'GAGAL'}\n{message}" for source, ok, message in reports)
    _logger().info("UNINSTALL SUMMARY success=%s count=%d", success, len(packages))
    return success, text


def uninstall_package(pkg: Package, on_output: OutputCallback | None = None) -> tuple[bool, str]:
    return batch_uninstall_packages([pkg], on_output)

"""Read-only, background-friendly report for root/home storage and app sizes."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiskVolume:
    key: str
    label: str
    path: str
    mountpoint: str
    device: str
    filesystem: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    device_id: int

    @property
    def percent_used(self) -> float:
        return (self.used_bytes / self.total_bytes * 100) if self.total_bytes else 0.0


@dataclass(frozen=True)
class DiskItem:
    name: str
    source: str
    size_bytes: int
    device_id: int
    details: str = ""


@dataclass(frozen=True)
class DiskReport:
    volumes: tuple[DiskVolume, ...]
    items: tuple[DiskItem, ...]
    warnings: tuple[str, ...]


def _run(args: list[str], timeout: float = 30) -> tuple[int, str, str]:
    env = os.environ.copy()
    env.update({"LC_ALL": "C", "LANG": "C"})
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"Batas waktu terlampaui: {args[0]}"
    except OSError as exc:
        return 127, "", str(exc)


def size_to_bytes(value: str) -> int:
    match = re.search(r"([\d,.]+)\s*([kmgt]?i?b|bytes?)?", value or "", re.IGNORECASE)
    if not match:
        return 0
    try:
        number = float(match.group(1).replace(",", ""))
    except ValueError:
        return 0
    unit = (match.group(2) or "b").casefold().replace("ib", "b")
    power = {"b": 0, "byte": 0, "bytes": 0, "kb": 1, "mb": 2, "gb": 3, "tb": 4}.get(unit, 0)
    return int(number * (1024 ** power))


def _mount_info(path: Path) -> tuple[str, str, str]:
    code, output, _error = _run(
        ["findmnt", "--target", str(path), "--noheadings", "--output", "TARGET,SOURCE,FSTYPE"],
        timeout=10,
    )
    if code == 0 and output.strip():
        fields = output.strip().split(maxsplit=2)
        fields += [""] * (3 - len(fields))
        return fields[0], fields[1], fields[2]
    return str(path), "Tidak diketahui", "Tidak diketahui"


def _volume(key: str, label: str, path: Path) -> DiskVolume | None:
    try:
        resolved = path.resolve(strict=True)
        usage = shutil.disk_usage(resolved)
        device_id = resolved.stat().st_dev
    except OSError:
        return None
    mountpoint, device, filesystem = _mount_info(resolved)
    return DiskVolume(
        key=key,
        label=label,
        path=str(resolved),
        mountpoint=mountpoint,
        device=device,
        filesystem=filesystem,
        total_bytes=usage.total,
        used_bytes=usage.used,
        free_bytes=usage.free,
        device_id=device_id,
    )


def _pacman_items(warnings: list[str]) -> list[DiskItem]:
    code, foreign_output, error = _run(["pacman", "-Qmq"])
    if code not in (0, 1):
        warnings.append("Daftar paket AUR atau luar repositori tidak dapat dibaca.")
    foreign = {line.strip() for line in foreign_output.splitlines() if line.strip()}

    code, output, error = _run(["pacman", "-Qi"], timeout=90)
    if code != 0:
        warnings.append("Ukuran paket Pacman tidak dapat dibaca.")
        return []

    packages: list[DiskItem] = []
    fields: dict[str, str] = {}

    def append_package() -> None:
        name = fields.get("Name", "").strip()
        size = size_to_bytes(fields.get("Installed Size", ""))
        if name and size:
            packages.append(DiskItem(
                name=name,
                source="AUR" if name in foreign else "Pacman",
                size_bytes=size,
                device_id=os.stat("/").st_dev,
                details="Ukuran terpasang menurut basis data Pacman",
            ))

    for line in output.splitlines() + [""]:
        if not line.strip():
            append_package()
            fields = {}
        elif line and not line[0].isspace() and ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return packages


def _flatpak_items(warnings: list[str], home_device_id: int, root_device_id: int) -> list[DiskItem]:
    if shutil.which("flatpak") is None:
        return []
    code, output, error = _run(
        ["flatpak", "list", "--app", "--columns=name,application,size,installation"],
        timeout=60,
    )
    if code != 0:
        warnings.append("Ukuran aplikasi Flatpak tidak dapat dibaca.")
        return []
    items: list[DiskItem] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        name, app_id, size = (part.strip() for part in parts[:3])
        installation = parts[3].strip().casefold() if len(parts) > 3 else "system"
        if not app_id:
            continue
        is_user = installation in {"user", "user installation"}
        items.append(DiskItem(
            name=name or app_id,
            source="Flatpak",
            size_bytes=size_to_bytes(size),
            device_id=home_device_id if is_user else root_device_id,
            details=f"ID aplikasi: {app_id} · instalasi: {installation or 'system'}",
        ))
    return items


def _directory_items(path: Path, source: str, device_id: int, warnings: list[str], timeout: float = 120) -> list[DiskItem]:
    if not path.is_dir():
        return []
    try:
        children = [child for child in path.iterdir() if child.is_dir() and not child.is_symlink()]
    except OSError as exc:
        warnings.append(f"Folder {path} tidak dapat dibaca: {exc}")
        return []
    if not children:
        return []
    code, output, error = _run(["du", "--bytes", "--summarize", "--", *(str(child) for child in children)], timeout=timeout)
    if code != 0:
        warnings.append(f"Sebagian isi folder {path} tidak dapat dibaca; ukurannya mungkin belum lengkap.")
    items: list[DiskItem] = []
    for line in output.splitlines():
        size_text, separator, item_path = line.partition("\t")
        if not separator:
            continue
        try:
            size = int(size_text)
        except ValueError:
            continue
        item_path = item_path.removesuffix(" (exited)")
        items.append(DiskItem(
            name=Path(item_path).name,
            source=source,
            size_bytes=size,
            device_id=device_id,
            details=item_path,
        ))
    return items


def collect_disk_report() -> DiskReport:
    warnings: list[str] = []
    root = _volume("root", "Root", Path("/"))
    home_path = Path.home()
    home = _volume("home", "Home", home_path)
    volumes = tuple(volume for volume in (root, home) if volume is not None)
    if root is None:
        warnings.append("Informasi partisi root tidak dapat dibaca.")
    if home is None:
        warnings.append("Informasi partisi home tidak dapat dibaca.")

    root_device = root.device_id if root else os.stat("/").st_dev
    home_device = home.device_id if home else root_device
    items = _pacman_items(warnings)
    items.extend(_flatpak_items(warnings, home_device, root_device))
    items.extend(_directory_items(home_path / ".var" / "app", "Data Flatpak", home_device, warnings))

    pacman_cache = Path("/var/cache/pacman/pkg")
    if pacman_cache.is_dir():
        try:
            cache_device = pacman_cache.stat().st_dev
            # Pacman may keep private temporary download directories here. Count
            # readable package files without attempting privileged access to them.
            cache_files = [
                entry for entry in pacman_cache.iterdir()
                if entry.is_file() and not entry.is_symlink() and os.access(entry, os.R_OK)
            ]
        except OSError:
            cache_device = root_device
            cache_files = []
        if cache_files:
            code, output, _error = _run(["du", "--bytes", "--", *(str(item) for item in cache_files)], timeout=120)
            cache_size = 0
            for line in output.splitlines():
                try:
                    cache_size += int(line.split("\t", 1)[0])
                except (ValueError, IndexError):
                    continue
            if cache_size:
                items.append(DiskItem(
                    name="Berkas paket cache Pacman",
                    source="Cache Pacman",
                    size_bytes=cache_size,
                    device_id=cache_device,
                    details=f"{pacman_cache} · berkas yang dapat dibaca pengguna",
                ))
            if code != 0:
                warnings.append("Sebagian berkas cache Pacman tidak dapat dibaca; ukuran cache mungkin belum lengkap.")

    items.sort(key=lambda item: item.size_bytes, reverse=True)
    return DiskReport(volumes=volumes, items=tuple(items), warnings=tuple(warnings))

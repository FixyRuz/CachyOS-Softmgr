# CachyOS Softmgr

**Versi 4.1.0 · Versi terbaru**

Aplikasi desktop PyQt6 untuk melihat dan mengelola paket Pacman, paket AUR/foreign melalui `paru` atau `yay`, serta aplikasi Flatpak. Proyek ini melanjutkan fondasi v2 dan v3; versi lama tetap berada di folder lokal dan tidak di publish.

## Fitur

- Daftar aplikasi Pacman, AUR/foreign, dan Flatpak dengan pencarian, filter sumber, detail paket, serta tema gelap/terang.
- Tampilan berbahasa Indonesia dengan logo dan ikon vektor khusus serta tipografi yang lebih mudah dibaca.
- Tab penyimpanan interaktif untuk kapasitas root/home, pemakaian disk, serta daftar paket, aplikasi, data Flatpak, dan cache terbesar. Ukuran paket Pacman/AUR ditandai sebagai perkiraan metadata.
- Tab pembaruan terpadu untuk Pacman, AUR, dan Flatpak. `paru` didahulukan jika keduanya tersedia; `yay` menjadi pilihan otomatis berikutnya.
- Pemindaian dan operasi berjalan di worker Qt agar antarmuka tetap merespons. Output transaksi ditampilkan langsung dan disimpan ke log bergilir.
- Pembaruan Pacman selalu menjalankan `pacman -Syu`. Pembaruan AUR juga menyinkronkan sistem lebih dulu agar proses build tidak memakai basis paket yang setengah diperbarui.
- Operasi Pacman menggunakan Polkit (`pkexec`). Helper AUR tetap berjalan sebagai pengguna biasa; `sudo` hanya dipakai untuk memasang hasil build dan meminta autentikasi melalui dialog.
- Penghapusan banyak paket, pemeriksaan transaksi Pacman yang sedang berjalan, peringatan untuk paket inti, dan pemuatan ulang setelah transaksi.
- Penghapusan Flatpak menyimpan data aplikasi pengguna. Flatpak juga dapat dipakai tanpa memasang integrasinya; fitur lain tetap berjalan.

## Persyaratan

- CachyOS atau distribusi berbasis Arch Linux.
- Python 3.11 atau lebih baru dan PyQt6 (`python-pyqt6`).
- Polkit dan `pkexec` untuk tindakan Pacman yang memerlukan hak administrator.
- `paru` atau `yay` untuk pemindaian dan pembaruan AUR. Bila keduanya terpasang, `paru` dipilih lebih dulu.
- Flatpak opsional untuk menampilkan, memperbarui, atau menghapus aplikasi Flatpak.

## Menjalankan

Jalankan langsung dari folder proyek:

```bash
python main.py
```

Untuk memasang aplikasi ke `/opt/cachyos-softmgr` dan mendaftarkannya di menu desktop:

```bash
./install.sh
```

Simulasikan lebih dulu tanpa mengubah sistem dengan `./install.sh --dry-run`. Installer menjalankan `pacman -Syu --needed` sebelum memasang dependensi agar tidak membuat partial upgrade. Pacman menampilkan transaksi dan meminta persetujuan; pembaruan sistem lain yang tersedia dapat ikut dipasang.

Untuk menghapus aplikasi setelah dipasang, jalankan `/opt/cachyos-softmgr/uninstall.sh` atau `./uninstall.sh` dari folder proyek. Skrip menampilkan lokasi yang akan dihapus dan meminta konfirmasi. Gunakan `--dry-run` untuk melihat daftar tanpa mengubah file. Data pengguna, paket, dan dependensi sistem tetap disimpan.

## Keamanan dan batas operasi

- Aplikasi tidak menggabungkan nama paket menjadi perintah shell. Target divalidasi dan proses dijalankan sebagai daftar argumen.
- Perintah Pacman berhak administrator dijalankan lewat Polkit dengan jalur `/usr/bin/pacman`; transaksi berhenti bila kunci database aktif.
- Dialog aplikasi meminta konfirmasi sebelum transaksi Pacman. Setelah itu Pacman dijalankan tanpa prompt terminal (`--noconfirm`), jadi periksa daftar rincian sebelum menyetujui. Opsi ini melewati seluruh konfirmasi Pacman; lihat [manual Pacman](https://man.archlinux.org/man/pacman.8.en).
- Paket AUR membangun PKGBUILD sebagai pengguna saat ini. PKGBUILD dapat menjalankan kode selama proses build; konfirmasi pembaruan AUR menampilkan peringatan ini.
- Memilih pembaruan Pacman/AUR menjalankan full system upgrade; daftar rincian menampilkan semua pembaruan Pacman yang terdeteksi, bukan hanya paket yang dicentang.
- Penghapusan Pacman memakai satu transaksi batch dan dapat ikut menghapus dependensi otomatis yang tidak lagi dipakai. Konfigurasi yang dimodifikasi dapat disimpan Pacman sebagai `.pacsave`.
- Peringatan paket sistem penting menggunakan daftar heuristik; peringatan membantu pengguna, tetapi tidak mengenali setiap paket khusus desktop atau konfigurasi mesin.
- Penghapusan Flatpak tidak menghapus data di direktori pengguna. Data itu dapat dibersihkan sendiri bila memang diinginkan.
- Sistem tanpa Flatpak atau helper AUR tetap dapat dipakai; ringkasan pemeriksaan memberi tahu sumber yang tidak tersedia atau gagal diperiksa.

## Pengujian

Jalankan pemeriksaan otomatis:

```bash
python -m unittest discover -s tests -v
```

Pada CachyOS, validasi manual sebelum rilis mencakup pemuatan paket, scan update, tema, otorisasi Polkit, pembaruan AUR dengan helper yang tersedia, operasi Flatpak bila dipasang, dan pemulihan tampilan setelah transaksi berhasil maupun gagal. Tes otomatis tidak menjalankan operasi yang mengubah paket sistem.

## Log dan pemecahan masalah

Log berada di `~/.cache/cachyos-softmgr/app.log` dengan maksimal tiga file rotasi. Tombol **Buka Folder Log** tersedia di dialog transaksi.

- Jika update Pacman ditolak, tunggu proses package manager lain selesai lalu refresh.
- Jika tindakan Pacman gagal karena Polkit, periksa layanan Polkit dan sesi desktop.
- Jika AUR tidak terdeteksi, pasang `paru` atau `yay`, lalu tekan **Refresh**.
- Jika pemeriksaan Flatpak gagal, verifikasi pemasangan dan remote dengan perintah Flatpak di sistem.

## Struktur

```text
main.py            Titik masuk aplikasi
main_window.py     UI, pencarian, filter, detail, dan dialog transaksi
backend.py         Pembacaan paket, scan update, keamanan perintah, logging
workers.py         Pekerjaan latar belakang Qt
theme.py           Palet dan stylesheet CachyOS
icons.py           Ikon vektor untuk UI
disk_report.py     Laporan baca-saja untuk penggunaan penyimpanan
tests/             Tes unit backend tanpa transaksi paket nyata
AUDIT.md           Ringkasan audit proyek lama dan perubahan v4
CHANGELOG.md       Catatan perubahan per versi
SECURITY.md        Kebijakan laporan kerentanan
VERSION            Versi rilis
TAG.txt            Penanda versi terbaru
install.sh         Installer sistem dengan mode simulasi
uninstall.sh       Uninstaller terkonfirmasi dengan mode simulasi
```

Lisensi: MIT.

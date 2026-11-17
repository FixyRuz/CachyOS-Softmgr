# Audit proyek lama dan baseline v4

## Sumber yang ditinjau

Audit membandingkan folder lama `cachyos-softmgr`, `cachyos-softmgr v2.0`, `cachyos-softmgr v2.1`, dan `cachyos-softmgr v3.0`. Keempat folder tetap dipertahankan; perubahan v4 dikembangkan sebagai salinan proyek baru.

## Temuan utama

- v2 memiliki GUI dan pemuatan paket yang dapat dipakai sebagai acuan. v2.0 menambahkan cache dan tampilan pembaruan; v2.1 memiliki sebagian backend AUR/Flatpak serta operasi batch.
- Integrasi v2.1 tidak konsisten dengan GUI: beberapa jalur pembaruan masih sinkron atau belum terhubung ke aksi UI, dan worker memakai sinyal lifecycle dengan nama yang berpotensi menimpa sinyal bawaan `QThread`.
- v3 memperbaiki sebagian tampilan dan worker, tetapi audit menemukan jalur UI yang masih memanggil operasi sinkron, fungsi worker yang tidak tersedia, serta dialog uninstall dengan argumen yang tidak cocok.
- Beberapa jalur update lama memakai instalasi paket terpilih tanpa full system upgrade. Pada Arch/CachyOS, operasi seperti itu berisiko menghasilkan partial upgrade.
- AUR dan Flatpak belum terintegrasi utuh pada daftar update. Output perintah, kegagalan sumber, log, pemulihan tampilan, dan konflik transaksi juga belum cukup terlihat.
- Installer lama menampilkan versi v3, memakai jalur instalasi yang tidak sama dengan nama rilis, dan tidak menjelaskan bahwa transaksi instalasi membutuhkan sinkronisasi sistem.

## Perubahan v4

- Backend dirapikan menjadi pembaca inventaris, pemindai pembaruan, dan pelaksana transaksi yang terpisah; pemanggilan proses memakai daftar argumen tanpa shell.
- Pacman selalu memakai `-Syu`; operasi administrator memakai `pkexec` dan memeriksa kunci database.
- `paru` dipilih otomatis jika tersedia, kemudian `yay`. Helper AUR tetap berjalan sebagai pengguna biasa dan memakai wrapper `sudo -A` hanya untuk pemasangan hasil build.
- Pemeriksaan Flatpak dilakukan untuk cakupan instalasi yang tercatat pada aplikasi terpasang. Penghapusan aplikasi tidak ikut menghapus data pengguna.
- Worker memakai sinyal `QThread` bawaan untuk lifecycle; proses transaksi menampilkan output, menulis log berotasi, dan UI memuat ulang daftar setelah hasil transaksi.
- UI memiliki tab Aplikasi/Pembaruan, pencarian tertunda, filter sumber, pilihan batch, detail paket, tema gelap/terang, dan peringatan sumber yang gagal diperiksa.
- Installer, launcher desktop, dokumentasi, versi, dan tag proyek diselaraskan pada rilis 4.1.0.

## Validasi

Validasi mencakup kompilasi Python, pemeriksaan script installer, tes unit parser/backend, pemuatan inventaris Pacman dan pemindaian update baca-saja di host CachyOS, serta pemeriksaan awal UI dalam mode tanpa layar. Pemeriksaan AUR `paru -Qua` berhasil dengan cache sementara dan menemukan delapan update pada saat audit. Flatpak tidak terpasang pada mesin audit, sehingga transaksi Flatpak nyata perlu diuji pada CachyOS yang menggunakannya. Pembaruan dan penghapusan paket tidak dijalankan selama audit karena dapat mengubah sistem.

Sebelum rilis publik, lakukan uji transaksi pada mesin atau VM CachyOS cadangan: otorisasi Polkit, satu update Pacman, satu update AUR, satu update Flatpak (jika dipasang), kegagalan jaringan, transaksi yang sedang memegang kunci Pacman, serta pemulihan setelah transaksi dibatalkan.

## Audit kesiapan GitHub 4.1.0 — 17 November 2026

Source memakai daftar argumen subprocess, validasi nama paket, sinkronisasi penuh `pacman -Syu`, kunci transaksi, Polkit untuk Pacman, log bergilir, dan konfirmasi UI. Pemeriksaan lokal saat persiapan rilis: 8 tes unit lulus; installer/uninstaller lolos pemeriksaan sintaks dan mode `--dry-run`; tidak ditemukan pola kredensial yang dikenal pada file source.

Batas rilis yang harus dinyatakan dengan jelas:

- Pacman memakai `--noconfirm` setelah pengguna menyetujui dialog aplikasi. Manual Pacman menjelaskan opsi itu melewati semua prompt konfirmasi; aplikasi belum menampilkan simulasi lengkap perubahan hasil resolver Pacman sebelum persetujuan.
- Peringatan paket penting adalah heuristik, bukan jaminan bahwa setiap paket desktop atau paket khusus CachyOS terdeteksi.
- Transaksi nyata Pacman, AUR, dan Flatpak belum diuji ulang pada VM bersih selama audit ini. Audit sebelumnya juga mencatat Flatpak tidak tersedia pada mesin validasi.

Kesimpulan: source layak dipublikasikan untuk tinjauan dan pengujian komunitas sebagai rilis awal 4.1.0, tetapi belum layak diklaim telah terbukti aman untuk semua konfigurasi atau sebagai rilis stabil tanpa uji transaksi di VM CachyOS. Jangan unggah file ZIP v3 lama sebagai bagian dari source rilis ini.

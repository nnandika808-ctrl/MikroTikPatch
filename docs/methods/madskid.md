# Metode madskid — 7.23.7 / 7.24.5, status SPK-2

**Kesimpulan:** batas atas metode tanpa loader adalah **7.24.5**, dan itu batas yang keras: `mode2` baru ada mulai 7.25. Sampai 7.24.5 loader boleh dibiarkan stok.

## 1. Bukti batas versi (inti SPK-2)

| Versi | `nova/bin/mode` | `nova/bin/mode2` | loader | Tabel guard `0x153e4` |
|---|---|---|---|---|
| 7.23.7 | ada, 75.688 B | **tidak ada** | 84.220 B | tidak ada |
| 7.24.5 | ada, 75.688 B | **tidak ada** | 84.220 B | tidak ada |
| 7.25.1 (stok) | ada, 96.144 B (= bakal `mode2`) | **tidak ada** | 84.176 B | tidak ada (loader stok) |
| 7.25.1 (elseif) | wrapper 202.396 B | 96.144 B | 87.092 B (diadaptasi) | ada, 8 record |

Tabel dibaca di `0x153e4` pada loader 7.23.7/7.24.5: `unpack_from` melewati EOF (84.220 < 87.012), jadi tidak ada tabel. Konfirmasi tambahan: ukuran loader 7.23.7 dan 7.24.5 identik (84.220) dan hash-nya sama.

Karena `mode2` tidak ada, guard elseif tidak punya target untuk dicocokkan, dan memasang loader elseif di 7.24.5 akan gagal pada hook-nya. Itu sebabnya `patch_loader` dikomentari di madskid.

Batas bawah metode elseif juga bukan 7.25 "ke atas" secara buta: 7.25.1 stok sudah memakai `mode` 96.144 B yang perannya berubah jadi `mode2` setelah wrapper dipasang — jadi resep 7.25.1 bergantung pada ukuran/struktur `mode` stok versi itu dan harus diperiksa ulang tiap rilis.

## 2. Cakupan patch madskid

`patch_squashfs` madskid memakai gerbang `if 'mode' in files and 'keyman' in files:` lalu mem-patch `mode` + `keyman`, dan loop generik untuk sisanya. Untuk 7.23.7/7.24.5 gerbang itu **benar** (keduanya punya `mode`), jadi tidak ada cacat seperti di v6.

Lokasi key stok per versi (dari audit, pola encoding `replace_key`):

- 7.23.7: `nova/bin/{mode,keyman,loader,sys2,installer}` + `bndl/security/nova/bin/ssh`
- 7.24.5: `nova/bin/{mode,keyman,loader,sys2,installer}` (+1 kemunculan ganda)

`ssh` di 7.23.7 hanya terpatch lewat loop generik. Jangan menambah `ssh` ke daftar skip.

## 3. Banner

madskid menimpa `nova/lib/console/logo.txt` dengan `logo.txt` di cwd. Untuk banner stok, salin file dari `banner-ref/logo-<versi>.txt`. Kalau file tidak ada, madskid jatuh ke `sed` gaya elseif (baris 1 dihapus, baris 8 diganti atribusi) — itu bukan banner stok.

Semua versi memakai logo yang sama: 510 B, sha256 `438e1067bdc90044f90f18f1d90895403757d1b8ea0084e83cbcd558563a56f7`. Satu file acuan cukup untuk seluruh lini.

## 4. Prosedur build

1. Sumber: `mikrotik-<ver>.iso` + `all_packages-x86-<ver>.zip`, versi dipatok. Catat sha256.
2. `xorriso -osirrox on -indev <iso> -extract /routeros-<ver>.npk …` dan seluruh npk lain.
3. Salin `banner-ref/logo-<ver>.txt` ke `logo.txt` di cwd patcher.
4. Set env key + URL (lihat `docs/env-build.md`), lalu `python3.12 patch.py npk <npk> -O <out>` per paket.
5. Sign seluruh `all_packages`, rakit ISO (El Torito BIOS+UEFI), IMG, ZIP.
6. `audit_keys.py` wajib 0 STOCK. Untuk 7.23.7/7.24.5 loader tetap memuat key stok? — **tidak**: loader memuat key karena hook-nya tidak dipakai, jadi tetap harus dipatch lewat loop generik. Periksa hasil audit per file, jangan menganggap loader otomatis bersih.

## 5. Yang belum diuji

- Build nyata 7.23.7 dan 7.24.5 (belum dijalankan; SPK-2 baru menetapkan batas).
- Boot/instalasi 7.24.5 setelah patch madskid dengan keypair baru.
- Jalur upgrade 7.24.5 → 7.25.1 (pernah gagal di pekerjaan lama, lihat `PANDUAN-VERSI.md` §5).

## 6. Risiko khusus

- `mode` 75.688 B di 7.23.7/7.24.5 memuat key; kalau `replace_key` gagal senyap, `mode` tetap stok dan audit yang salah (naif, `key in data`) akan melaporkan bersih. Pakai `audit_keys.py`, bukan `grep`.
- Jangan menyalin `mode`/`mode2` 7.25.1 ke versi ini tanpa uji — ABI/entry berbeda.

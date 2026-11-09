# Referensi banner stok (SPK-5)

Tujuan: membuktikan `logo.txt` yang dikirim identik dengan stok, dan menyediakan file acuan agar patcher tidak pernah menulis banner sendiri.

## Hasil

Kelima versi memakai file yang **sama persis**:

| Versi | Sumber | Ukuran | sha256 |
|---|---|---|---|
| 6.49.23 | `system-6.49.23.npk` → `nova/lib/console/logo.txt` | 510 B | `438e1067bdc90044f90f18f1d90895403757d1b8ea0084e83cbcd558563a56f7` |
| 7.23.7 | `routeros-7.23.7.npk` → idem | 510 B | sama |
| 7.24.5 | `routeros-7.24.5.npk` → idem | 510 B | sama |
| 7.25.1 | `routeros-7.25.1.npk` → idem | 510 B | sama |

File acuan tersimpan di `banner-ref/logo-<versi>.txt`. Isi: blok ASCII "MIKROTIK" + baris `MikroTik routerOS V2.4 (c) 1999-2001  http://mikrotik.com/`.

Catatan: baris terakhir memuat `mikrotik.com`. Itu **bukan** jalur update, jadi dibiarkan — jangan ikut di-rewrite.

## Kenapa file acuan wajib ada

- madskid: menimpa `logo.txt` dari `logo.txt` di cwd; kalau tidak ada, jatuh ke `sed` gaya elseif (hapus baris 1, ganti baris 8 dengan atribusi `elseif@live.cn`). Keduanya bukan banner stok.
- elseif: selalu `sed -i '1d'` + ganti baris 8. Wajib dikembalikan.
- Build acuan 7.25.1 sudah benar: hash logo di ISO = hash stok.

## Cara pakai

1. Salin `banner-ref/logo-<versi>.txt` ke `logo.txt` di cwd patcher sebelum memanggil `patch.py npk`.
2. Setelah npk selesai, buka squashfs hasil dan bandingkan:

```sh
sha256sum sq/nova/lib/console/logo.txt
# harus 438e1067bdc90044f90f18f1d90895403757d1b8ea0084e83cbcd558563a56f7
```

3. Ulangi pemeriksaan pada **ISO final** (ekstrak ulang npk dari ISO, bukan dari `iso_new/`).

## Batas klaim

Hash cocok membuktikan byte file benar. Itu tidak membuktikan konsol menampilkannya (mis. kalau ada `rc.local` yang menimpa tampilan) — periksa layar boot pada uji QEMU.

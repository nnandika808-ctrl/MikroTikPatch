# Laporan M2 — SPK-1…SPK-5

Tanggal: 8 November 2026. Semua angka di bawah berasal dari perintah yang dijalankan di sesi ini; log mentah ada di `work/spk4-verify/evidence/`.

## Status gate

| Gate | Status | Bukti / catatan |
|---|---|---|
| SPK-1 v6/loskiq | LULUS dengan syarat porting | `docs/methods/v6.md` §4 — 3 perubahan wajib di `patch_squashfs` |
| SPK-2 batas madskid | LULUS | `mode2` tidak ada di 7.23.7/7.24.5; tabel guard `0x153e4` tidak ada (EOF di 84.220 B). Batas keras = 7.24.5 |
| SPK-3 langkah minimum elseif | LULUS | `docs/methods/elseif.md` §1 |
| SPK-4 loader.7z | LULUS tanpa password | loader + wrapper pulih dari ISO acuan, hash cocok dokumen; password tidak dibutuhkan |
| SPK-5 banner | LULUS | 4 versi memakai logo identik, `438e1067…`; acuan di `banner-ref/` |

## Yang berubah dari asumsi PRD

1. **`loader.7z` bukan blocker lagi.** Isi arsip sudah terpakai pada build acuan dan bisa dipulihkan dari ISO final. Arsipnya sendiri (168.768 B, `20b09362…`) tetap tidak terbuka tanpa password, tapi tidak diperlukan.
2. **Resep historis loader belum lengkap.** Hanya tabel guard yang dipatch; public key stok masih hidup di `.text` (file `0x83ac`…`0x8408`, VMA `0x80503ac`…). Sudah ditutup dengan `patch_loader_guard.py` (32 byte, ukuran tetap, guard tetap 8/8, audit jadi 0 STOCK).
3. **Keypair di `keys/env` bukan keypair build acuan.** Private key build acuan tidak ada. Build baru wajib memakai `keys/env` dan menulis ulang tabel + salinan kode loader.
4. **Build acuan hanya me-rewrite URL upgrade.** `licence.mikrotik.com`, `cloud.mikrotik.com`, `cloud2.mikrotik.com` masih stok di `keyman`, `detnet`, `cloud`.
5. **Audit key naif tidak bekerja.** Key disimpan dalam tiga encoding bersela (`replace_key`), jadi `key in data` selalu 0 — termasuk di image yang sama sekali belum dipatch. `audit_keys.py` sekarang memakai ketiga encoding itu.
6. **v6 punya bug senyap di loskiq.** `keyman` tidak pernah dipatch karena gerbang `'mode' in files and 'keyman' in files` tidak pernah benar di v6, dan `keyman` ada di daftar skip. Build tetap "sukses".
7. **CHR v6 tidak butuh `patch_block`.** CHR dibangun dari nol, bukan ditambal in-place; boot code mentah tidak memuat key.

## Artefak kerja

- `docs/methods/{v6,madskid,elseif}.md` — prosedur + bukti + batas klaim
- `docs/env-build.md` — nama env, nilai, batas panjang, jebakan `LICENCE` vs `LICENSE`
- `docs/banner-ref.md`, `banner-ref/logo-*.txt` — acuan banner stok
- `audit_keys.py` — audit tiga-encoding, exit 1 bila ada sisa
- `patch_loader_guard.py` — patch dua salinan key loader, `--check` untuk verifikasi
- `keys/env` — ditambah 8 variabel URL (0600), backup `env.bak-*`

## Belum dikerjakan (bukan bagian M2)

- `build.sh` orkestrasi belum ada; resep masih dijalankan manual per langkah.
- Boot QEMU/FR-10 belum dijalankan untuk build baru.
- 7.25 belum diperiksa: apakah `mode` stok masih 96.144 B dan offset guard/kode masih sama.
- `npk.py verify` bagian KCDSA gagal bahkan untuk npk stok + key stok — perlu dibedah sebelum dipakai sebagai gate otomatis (bagian EdDSA bekerja normal).

## Syarat masuk M3

1. `build.sh` memanggil `patch_loader_guard.py` setelah `mode2` final terbentuk, dan gagal keras bila `--check` tidak PASS.
2. `audit_keys.py` dijalankan pada squashfs sebelum repack, bukan setelah ISO jadi.
3. Logo disalin dari `banner-ref/`, lalu diverifikasi hashnya pada ISO final.
4. Env URL terisi; verifikasi `16.79.7.181` muncul di `sys2`, `net`, `keyman`, `detnet`, `cloud`.

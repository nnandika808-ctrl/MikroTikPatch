# PRD — Lini Produksi Patch RouterOS Milik Sendiri (v6 + v7, x86 + CHR)

**Versi:** 2.1
**Tanggal:** 8 November 2026
**Pemilik:** ". ." (single-user, self-hosted)
**Menggantikan:** PRD v1.0 (ruang lingkup lebih sempit)
**Status:** M2 selesai (lihat `docs/M2-REPORT.md`) — siap masuk M3

---

## 1. Ringkasan

Membangun lini produksi patch RouterOS yang seluruhnya memakai **keypair sendiri**, mempertahankan **banner asli MikroTik**, mengaktifkan **update online ke server sendiri**, dan menghasilkan **artefak lengkap** (ISO, install image, CHR image, all_packages) untuk:

| Versi | Metode patch wajib |
|---|---|
| 6.49.23 | cara **loskiq** (jalur v6) |
| 7.23.7 | cara **madskid** |
| 7.24.5 | cara **madskid** |
| 7.25 | cara **elseif** (wajib) |
| 7.25.1 | cara **elseif** (wajib) |

Arsitektur: **x86** dan **CHR**. Semua paket di `all_packages` harus ikut ter-patch dan ter-sign ("100% patch"), bukan hanya paket sistem.

## 2. Hasil studi 3 repo (basis keputusan)

Ketiganya memakai primitif yang sama; yang berbeda adalah kelengkapan, cakupan versi, dan titik lemahnya.

**Prinsip bersama**
1. Public key MikroTik ditimpa public key kita di `mode`, `keyman`, kernel/initrd, `BOOTX64.EFI`, dan seluruh binary di squashfs (`replace_key`, dengan trik chunk 4-byte + peta byte untuk menghindari kecocokan tunggal).
2. Hostname `licence.mikrotik.com` / `download.mikrotik.com` / `cloud*.mikrotik.com` ditimpa host kita.
3. `.npk` di-sign ulang (Ed25519), lisensi dibuat dengan Curve25519/KCDSA.
4. Router memverifikasi dengan public key yang sudah ditanam.

**Perbedaan yang menentukan pemilihan metode**

- **loskiq** — `patch_squashfs` hanya mengganti key, **tanpa** rewrite URL dan tanpa penanganan banner; `npk.py` memakai magic yang sama (`0xbad0f11e`) sehingga format npk v6 masih bisa diproses. Ini satu-satunya jalur yang tersedia untuk v6, tapi butuh porting: rewrite URL v6, layout server v6, dan verifikasi tanda tangan v6.
- **madskid** — sudah punya rewrite URL (`MIKRO_*_URL` → `CUSTOM_*_URL`), penanganan `licupgr`/renew URL, dan penggantian banner dari `logo.txt` (banner "Ludens"). `patch_loader` masih dikomentari → tidak butuh `loader.7z`. Cocok untuk ≤7.24.5.
- **elseif** — satu-satunya yang mem-patch **loader** dan punya `option.npk` (busybox/shell/keygen) plus layout server `upgrade.json` + `NEWESTa7.*`. Loader wajib untuk ≥7.25. Konsekuensi: butuh `loader.7z` yang **berpassword** (password hanya ada di GitHub Secrets elseif).

**Temuan yang langsung jadi batasan teknis**
- `loader.7z` (168.768 byte, dari `upgrade.mikrotik.ltd/routeros/loader.7z`) terenkripsi; `7z` menolak tanpa password. Ini **blocker** untuk 7.25/7.25.1 dan juga dipakai `patch_v6.yml` elseif.
- Penggantian URL memakai `bytes.replace`, jadi host pengganti tidak boleh lebih panjang dari aslinya: `download.mikrotik.com` = 21, `licence.mikrotik.com` = 20, `cloud2.mikrotik.com` = 19 karakter. `16.79.7.181` (11) aman; domain harus ≤19 karakter.
- Banner: madskid menimpa `nova/lib/console/logo.txt` dengan banner sendiri; untuk banner ori, file harus dikembalikan ke versi stok (verifikasi via hash).
- Ketersediaan file (dicek hari ini): semua artefak 7.23.7 / 7.24.5 / 7.25 / 7.25.1 → HTTP 200. Untuk 6.49.23 tidak ada `routeros-*.npk` terpisah (paket sistem ada di dalam ISO), sedangkan `all_packages-x86-6.49.23.zip` dan `chr-6.49.23.img.zip` tersedia.

## 3. Tujuan & non-tujuan

**Tujuan**
- 5 versi × 2 arsitektur, semuanya bootable dan lengkap (ISO, install image, CHR image, all_packages, netinstall).
- Banner konsol identik dengan stok MikroTik.
- `check-for-updates` menunjuk ke server sendiri untuk v6 maupun v7, dan benar-benar berfungsi.
- Satu keypair stabil dipakai untuk seluruh lini (agar satu server + satu portal lisensi melayani semua versi).
- Audit otomatis yang membuktikan tidak ada key/host MikroTik tersisa.

**Non-tujuan**
- arm64/ARM/MIPS/PPC, DDNS/cloud-backup emulation, panel multi-user, CI GitHub, dukungan versi di luar daftar.

## 4. Arsitektur

```
VPS 16.79.7.181
  nginx :80   endpoint update, HTTP polos (tidak boleh mensyaratkan TLS)
    /routeros/upgrade.json                 manifest v7
    /routeros/NEWESTa7.stable|long-term    symlink -> <ver>/info
    /routeros/NEWEST6.stable|long-term     symlink -> <ver>/info   (v6)
    /routeros/<ver>/<pkg>-<ver>.npk        semua paket ter-sign
    /routeros/<ver>/routeros-<ver>.npk     paket sistem (v7)
    /routeros/<ver>/CHANGELOG, packages.csv, info
    /routeros/loader.7z                    (butuh password)
  nginx :443  portal web manusia, self-signed
    /                                      halaman status + generator lisensi
  /srv/artifacts/<ver>/<arch>/             ISO, IMG, QCOW2, ZIP, SHA256 (unduhan manual)

Build host (mesin yang sama, /root/mtp)
  keys/env                 4 kunci, 0600, root
  methods/{madskid,elseif,loskiq}/  salinan kode per metode
  build.sh <ver> <arch>    orkestrasi: unduh → patch npk → sign → patch kernel → rakit
  audit.sh <artefak>       pemeriksaan 100% patch
```

## 5. Kebutuhan fungsional

**FR-1 Keypair tunggal** — Satu pasang Ed25519 (sign paket) + satu pasang Curve25519/KCDSA (lisensi) untuk semua versi. Private key hanya di `keys/env` + backup offline terenkripsi; repo hanya memuat public key.

**FR-2 Pemilihan metode per versi** — Router pemilihan otomatis: `6.x` → loskiq, `7.23.x`/`7.24.x` → madskid, `>=7.25` → elseif. Salah metode harus menolak build (bukan diam-diam jalan).

**FR-3 Banner ori** — `logo.txt` stok dipertahankan; `patch_squashfs` tidak menimpanya. Verifikasi: `sha256` logo di image == logo dari paket stok. Nol baris identitas tambahan.

**FR-4 Rewrite URL (semua versi)** — Untuk v6, porting rewrite URL dari madskid ke jalur loskiq: `upgrade.mikrotik.com`, `download.mikrotik.com`, `licence.mikrotik.com`, `cloud*.mikrotik.com`, `licupgr`/renew → `16.79.7.181`. Untuk v7 tetap pakai env `CUSTOM_*`.

**FR-5 Patch 100%** — Setiap binary di squashfs yang memuat public key stok ditimpa; setiap paket di `all_packages` di-sign ulang. Build gagal bila ada paket yang gagal sign atau key stok tersisa.

**FR-6 Artefak lengkap per versi/arsitektur**
- x86: `mikrotik-<ver>-patched.iso` (BIOS+UEFI), `install-image-<ver>-patched.{img,qcow2,vmdk,vhdx,vdi}`, `all_packages-x86-<ver>-patched.zip`, `netinstall-<ver>-patched.zip`
- CHR: `chr-<ver>-patched.{img,qcow2,vmdk,vhdx,vdi}`, `all_packages-<ver>-patched.zip`, `chr-<ver>-patched.iso` (bila relevan)
- Semua dengan `.sha256`; manifest `MANIFEST-<ver>.json` berisi versi, arch, hash, waktu build, fingerprint key.

**FR-7 Server update** — Layani layout bagian 4 untuk v6 dan v7, termasuk `upgrade.json` yang menunjuk versi yang kita sediakan (bukan versi MikroTik terbaru yang belum kita patch). Endpoint update HTTP polos; TLS hanya di portal.

**FR-8 Lisensi** — v6/x86 & v7/x86: `licgenros <software-id>`; CHR: `licgenchr <system-id>`; ≥7.25 juga menyertakan `option.npk` (lisensi otomatis). Portal web: input ID → blok lisensi.

**FR-9 Audit** — `audit.sh` memeriksa: tidak ada public key stok, tidak ada host `*.mikrotik.com`, `npk.py verify` lolos untuk semua paket, banner cocok stok, `.sha256` valid.

**FR-10 Smoke test** — Boot QEMU (TCG) per versi/arsitektur: login, `/system/license print` valid, `check-for-updates` mengenai server sendiri (dibuktikan access log), paket stok yang tidak di-sign ditolak.

## 6. Kebutuhan non-fungsional

- **Keamanan key:** `keys/env` 0600 root; backup terenkripsi (age/gpg) di luar VPS; fingerprint key dicatat di manifest.
- **Determinisme:** versi dipatok; tidak ada `latest` saat build; build serial (RAM 1.9 GB).
- **Kapasitas:** artefak 5 versi × 2 arch ≈ 6–8 GB; sisa disk harus ≥ 25 GB saat build (saat ini 87 GB).
- **Jejak audit:** log per build di `out/<ver>-<arch>.log`, access log nginx untuk endpoint update.
- **Rollback:** minimal 2 versi terakhir tetap tersedia; symlink `NEWEST*` bisa dialihkan tanpa rebuild.

## 7. Fase studi (wajib sebelum produksi)

Setiap metode dipelajari sampai bisa dijelaskan dan direproduksi, dengan output konkret:

- **SPK-1 (loskiq/v6):** identifikasi binary & string URL pada paket v6; konfirmasi skema tanda tangan npk v6; tentukan apakah `patch_block` diperlukan untuk image CHR v6; hasil: catatan + patch percobaan yang lolos boot.
- **SPK-2 (madskid/7.23–7.24):** verifikasi batas versi atas metode tanpa loader (uji 7.24.5; cari titik di mana loader mulai wajib); hasil: batas versi terdokumentasi.
- **SPK-3 (elseif/≥7.25):** peta lengkap langkah wajib (loader, `option.npk`, kernel, squashfs); hasil: daftar langkah minimum yang tidak bisa dilewati.
- **SPK-4 (loader.7z):** ✅ selesai. Password tidak diperlukan — loader + wrapper pulih dari ISO acuan, dua salinan key ditutup `patch_loader_guard.py`. Hasil: putusan lolos + daftar offset.
- **SPK-5 (banner):** ekstrak `logo.txt` stok tiap versi, simpan sebagai referensi hash.

Keluaran fase studi: `docs/methods/{v6,madskid,elseif}.md` — cukup detail untuk dijalankan ulang tanpa membaca repo aslinya.

## 8. Milestone

| # | Milestone | Output |
|---|---|---|
| M1 | Keypair + repo + kerangka `build.sh`/`audit.sh` | ✅ keypair sudah ada & terverifikasi |
| M2 | SPK-1…SPK-5 selesai | ✅ `docs/methods/*`, `docs/M2-REPORT.md` |
| M3 | Build 7.24.5 x86 (madskid) lolos FR-9 + FR-10 | 1 artefak terverifikasi |
| M4 | Build 7.25.1 x86 + CHR (elseif) | 2 artefak terverifikasi |
| M5 | Build 6.49.23 x86 + CHR (loskiq, setelah porting) — best effort | 2 artefak terverifikasi |
| M6 | Matriks penuh 5 versi × 2 arch + all_packages | 16+ artefak, semua lolos audit |
| M7 | Server + portal lisensi + runbook | endpoint publik, dokumentasi operasional |

## 9. Kriteria penerimaan

1. Semua 5 versi × 2 arsitektur menghasilkan artefak lengkap sesuai FR-6, tiap artefak punya `.sha256` valid.
2. `audit.sh` lolos untuk setiap artefak: nol public key stok, nol host `mikrotik.com`, `npk.py verify` lolos untuk **semua** paket di `all_packages`.
3. `sha256(logo.txt)` di image == stok, untuk setiap versi.
4. Setiap image boot sampai prompt login di QEMU (x86 ISO & CHR).
5. `/system/package/update/check-for-updates` pada v6 dan v7 menjawab dari `16.79.7.181` (dibuktikan access log), dan unduhan paket dari server berhasil.
6. Paket stok tanpa sign ulang ditolak; paket kita diterima.
7. Lisensi hasil `licgenros`/`licgenchr` diterima router (level penuh, tanpa koneksi ke MikroTik).
8. `MANIFEST-<ver>.json` memuat fingerprint key yang sama untuk semua versi.

Kriteria 1–8 mengikat untuk 7.23.7 / 7.24.5 / 7.25 / 7.25.1. Untuk 6.49.23 berlaku sebagai best effort (lihat keputusan 5).

## 10. Risiko

- **R1 — Password `loader.7z` (TERTUTUP di M2).** Password tidak diperlukan: loader + wrapper pulih dari ISO acuan dengan hash yang cocok, dan resep yang kurang lengkap (hanya tabel guard, kode `.text` masih stok) sudah diperbaiki.
- **R2 — v6 tidak terdokumentasi.** loskiq hanya punya jalur key tanpa URL/banner. Mitigasi: SPK-1 sebagai gate; kalau gagal, v6 jadi best effort dan dipisahkan dari kriteria rilis.
- **R3 — Port 80/443 EC2 tertutup.** Dibuka oleh pemilik akun AWS; tanpa itu M7 tidak bisa diverifikasi.
- **R4 — Tanpa KVM.** Boot test TCG lambat (5–15 menit/boot); 16 artefak butuh waktu uji besar.
- **R5 — RAM 1.9 GB.** `mksquashfs` bisa OOM; build serial + swap.
- **R6 — Key bocor.** Rotasi berarti rebuild seluruh matriks.
- **R7 — Perubahan layout binary di rilis baru.** Versi dipatok; uji sebelum menaikkan `NEWEST*`.
- **R8 — Legalitas.** Bukan lisensi resmi MikroTik.
- **R9 — Keypair `keys/env` ≠ keypair build acuan.** Private key acuan tidak tersimpan; build baru memakai `keys/env` dan loader harus ditulis ulang per keypair. Mitigasi: backup `keys/env` offline sekarang, jangan pernah rotasi tanpa rebuild penuh.
- **R10 — Audit key naif memberi false-clean.** Key disimpan dalam 3 encoding bersela; `grep`/`key in data` selalu 0. Mitigasi: hanya `audit_keys.py` yang dipakai sebagai gate.

## 11. Matriks artefak (target akhir)

Per versi: x86 ISO, x86 install (5 format), x86 all_packages, x86 netinstall, CHR img (5 format), CHR all_packages. Total ± 16 artefak/versi-set, ± 6–8 GB.

## 12. Keputusan (final, 8 November 2026)

| # | Pertanyaan | Keputusan |
|---|---|---|
| 1 | Hostname pengganti | IP `16.79.7.181` — 11 char, di bawah batas replace() semua host stok, tanpa dependensi DNS |
| 2 | Protokol | HTTP **dan** HTTPS self-signed pada :80/:443. Terbukti 8 Nov: `check-for-updates` memakai `mode: https` dan menolak cert self-signed sampai `check-certificate=no` — server tanpa 443 membuat cek update gagal senyap |
| 3 | Cakupan 7.25 & 7.25.1 | Keduanya — jalur elseif diuji pada dua rilis berurutan |
| 4 | Password `loader.7z` | Tidak tersedia dan tidak ditunggu. Terbukti 8 Nov: 7.25.1 boot + menerima paket dari server sendiri **tanpa** patch loader maupun wrapper `mode`. 7.25/7.25.1 tetap dirilis; loader dari aset acuan (`d93a777e…`, 87.092 B) ditambal dengan `patch_loader_guard.py` bila ingin audit 0 STOCK — tidak wajib untuk boot |
| 4b | Jalur lisensi | **Offline saja**: `licgenros <software-id>` untuk x86 dan `licgenchr <system-id>` untuk CHR. Tanpa emulasi server lisensi online; `option.npk` hanya kalau dibutuhkan untuk hal lain |
| 5 | v6 bila SPK-1 gagal | Best effort — dikeluarkan dari kriteria rilis, tetap didokumentasikan |
| 6 | Port 80/443 Security Group | Dibuka oleh pemilik akun AWS (single-user) |
| 7 | Banner | Identik stok, nol tambahan; kriteria 9.3 tetap `sha256 == stok` |
| 8 | Keypair | **Keypair pilihan user** (dari README madskid), disimpan di `keys/env.user` (0600). Round-trip terverifikasi 8 Nov: `licgenros`/`licgenchr` → `License valid: True`. Menggantikan pasangan hasil `genkey` di `keys/env`; build wajib memakai `env.user` |
| 9 | Host URL | Masih placeholder `127.0.0.1` di `keys/env.user`; diarahkan ke host user sebelum build. Batas panjang tetap mengikat: LICENCE ≤20, UPGRADE ≤21, CLOUD ≤19 |

**Konsekuensi yang mengikat**
- Tidak ada domain dan tidak ada reverse proxy; semua rewrite URL memakai `16.79.7.181`.
- Sertifikat self-signed hanya untuk portal. Endpoint update tidak boleh mensyaratkan TLS, agar `check-for-updates` v6 tetap jalan.
- Identitas build (versi, fingerprint key) tampil lewat `MANIFEST-<ver>.json` dan halaman status, bukan `logo.txt`.
- Karena banner tidak boleh disentuh, `patch_squashfs` madskid harus melewati penulisan `logo.txt` sepenuhnya — bukan menulis lalu mengembalikan.

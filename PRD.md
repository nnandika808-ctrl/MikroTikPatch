# PRD — Produksi RouterOS Ter-patch Sendiri (Keypair Sendiri + Update Server Sendiri)

**Versi:** 1.0 (draft)
**Tanggal:** 8 November 2026
**Pemilik produk:** ". ." (single user / self-hosted)
**Status:** Menunggu keputusan pada bagian 11 sebelum eksekusi

---

## 1. Ringkasan

Membangun jalur produksi mandiri untuk image MikroTik RouterOS yang sudah di-patch, memakai **pasangan public/private key milik sendiri** (bukan key bawaan elseif/madskid/loskiq yang publik), dengan **server lisensi + update sendiri** yang berjalan di VPS ini.

Hasil akhir: satu set image (ISO x86, install image, CHR qcow2) yang menolak paket resmi MikroTik dan hanya menerima paket serta lisensi yang ditandatangani key kita, plus server yang melayani `check-for-updates` dan pembuatan lisensi.

## 2. Latar belakang — hasil studi 3 repo

Ketiganya memakai mekanisme yang sama; bedanya kelengkapan dan pemeliharaan.

- **elseif/MikroTikPatch** — paling lengkap dan aktif (commit Okt 2026). Punya pipeline CI penuh (`patch_v7.yml`), paket `option.npk` (busybox + shell + keygen), patch loader, `index.html` untuk halaman server, layout server update (`upgrade.json`, `NEWESTa7.*`), build ISO/install-image/CHR/netinstall, dukungan x86 + arm64. Rilisnya dipublikasikan ke `mikrotik.ltd`.
- **madskid/MikroTikPatch** — fork yang lebih sederhana. Mendokumentasikan `license.py genkey` + cara build manual. Tidak mem-patch loader, tidak ada komponen server.
- **loskiq/MikroTikPatch** — fork paling tua (Feb 2025, v7.16.2). Status: x86/CHR jalan, ARM bootloop, MIPSBE/MMIPS/SMIPS bootloop.

Mekanisme teknis yang dipakai ketiganya:

1. Public key MikroTik di dalam binary (`mode`, `keyman`, kernel/initrd, `BOOTX64.EFI`) ditimpa dengan public key kita (`patch.py`, `replace_key`).
2. Hostname `licence.mikrotik.com` / `download.mikrotik.com` / `cloud*.mikrotik.com` di binary ditimpa dengan host kita.
3. Paket `.npk` ditandatangani ulang dengan private key Ed25519 kita (`npk.py sign`), lisensi dibuat dengan private key Curve25519/KCDSA kita (`license.py`).
4. Router memverifikasi paket & lisensi dengan public key yang sudah ditanam di image.

Konsekuensi penting: **image hasil build hanya kompatibel dengan keypair yang dipakai saat build**. Ganti key = build ulang semua image.

## 3. Tujuan & non-tujuan

**Tujuan**
- Keypair eksklusif, dibuat dan disimpan sendiri, tidak pernah dipakai orang lain.
- Image yang bisa di-deploy berulang (x86 ISO, install image, CHR qcow2) dari satu pipeline yang reproducible.
- Server sendiri untuk: cek update, unduh paket, terbitkan lisensi, dan (opsional) DDNS/cloud.
- Semua artefak + dokumentasi ada di satu repo privat.

**Non-tujuan (fase ini)**
- Tidak menyentuh arsitektur ARM/MIPS/PPC (fokus x86 + CHR).
- Tidak mengejar paritas fitur `mikrotik.ltd` (multi-arsitektur, panel publik).
- Tidak menjual/mendistribusikan ke pihak lain.
- Tidak menjamin legalitas (EULA MikroTik tetap berlaku).

## 4. Arsitektur target

```
[VPS ini: 16.79.7.181]
  nginx :80/:443
    /routeros/upgrade.json              -> manifest versi (dibuat sendiri)
    /routeros/NEWESTa7.stable           -> symlink ke <ver>/info
    /routeros/NEWESTa7.long-term        -> symlink ke <ver>/info
    /routeros/<ver>/routeros-<ver>.npk  -> paket utama ter-sign
    /routeros/<ver>/<pkg>-<ver>.npk     -> paket opsional ter-sign
    /routeros/<ver>/CHANGELOG, packages.csv
    /routeros/loader.7z                 -> artefak loader (lihat risiko R2)
    /                                   -> halaman status + generator lisensi
  lisensi.mikrotik.* (emulasi)          -> endpoint lisensi online (fase 4)

[Build host = VPS yang sama, /root/mtp]
  keys/env (0600)  -> CUSTOM_*_PRIVATE_KEY / PUBLIC_KEY
  pipeline build.sh -> download ISO -> patch npk -> sign -> patch kernel -> rakit ISO/IMG
  output /root/mtp/out/*.iso|*.img|*.qcow2 + *.sha256
```

**Batasan penamaan host (keras):** penggantian URL dilakukan dengan `bytes.replace()`, jadi panjang host pengganti **tidak boleh melebihi** string aslinya. `download.mikrotik.com` = 21 karakter, `licence.mikrotik.com` = 20, `cloud2.mikrotik.com` = 19. Jika memakai IP `16.79.7.181` (11 karakter) aman. Jika memakai domain, panjang ≤ 19 karakter.

## 5. Kebutuhan fungsional

**FR-1 Keygen** — Hasilkan 2 keypair: Ed25519 (sign paket) dan Curve25519/KCDSA (lisensi). Simpan private key di file 0600 + salinan offline. Public key di-commit ke repo.
**FR-2 Patch image** — Timpa public key MikroTik + hostname URL di `mode`, `keyman`, kernel/initrd, `BOOTX64.EFI` dan seluruh paket.
**FR-3 Sign paket** — Setiap `.npk` (utama + opsional) ditandatangani ulang dengan private key Ed25519 kita; paket yang gagal sign menggagalkan build.
**FR-4 Build artefak** — Hasilkan ISO x86 (BIOS+UEFI), install image (raw/qcow2/vmdk/vhdx/vdi), dan CHR qcow2. Semua disertai `.sha256`.
**FR-5 Server update** — Sajikan `upgrade.json`, `NEWESTa7.*`, paket, CHANGELOG, `packages.csv` sesuai layout di bagian 4.
**FR-6 Terbit lisensi** — Dua jalur: (a) offline, `license.py licgenros <software-id>`; (b) `option.npk` yang otomatis memberi lisensi level tertinggi saat dipasang.
**FR-7 Portal lisensi** — Halaman web sederhana: input software-id / system-id → keluar blok lisensi.
**FR-8 Smoke test** — Skrip yang mem-boot image di QEMU dan memverifikasi: boot sukses, lisensi terpasang, `check-for-updates` menunjuk ke server kita.

## 6. Kebutuhan non-fungsional

- **Keamanan:** private key hanya di VPS (0600, owner root) + backup terenkripsi offline; tidak pernah masuk repo. Repo hanya berisi public key.
- **Reproducibility:** versi RouterOS dipatok di variabel (`VERSION=7.25.1`); build ulang menghasilkan artefak identik (kecuali timestamp).
- **Kapasitas:** sisa disk ≥ 25 GB saat build; RAM 1.9 GB cukup untuk `mksquashfs` dengan `-b 256k` tapi build harus serial (1 build pada satu waktu).
- **Observability:** log build per langkah ke `out/build-<ver>.log`; nginx access log aktif untuk endpoint update.
- **Rollback:** simpan 2 versi terakhir di server; `NEWESTa7.*` bisa diarahkan ulang tanpa build ulang.

## 7. Kebutuhan teknis

- OS: Ubuntu 24.04 (host ini).
- Paket: `squashfs-tools xorriso qemu-utils qemu-system-x86 dosfstools isolinux syslinux-common python3-pefile python3-crcmod python3-pyelftools p7zip-full zip unzip nginx`.
- Python 3.14 + `toyecc`, `sha256.py`, `npk.py`, `patch.py`, `license.py` (dari elseif).
- Source: `https://download.mikrotik.com/routeros/7.25.1/*` (ISO, install-image, chr.img, netinstall).
- Tidak ada KVM di host ini → verifikasi boot memakai QEMU TCG (lambat, ±5–15 menit per boot).

## 8. Milestone

| # | Milestone | Output | Estimasi |
|---|---|---|---|
| M1 | Keypair + repo privat + `keys/env` | public key ter-commit, private key tersimpan | 0,5 jam |
| M2 | Pipeline patch+sign berjalan untuk 1 versi | npk ter-sign, kernel ter-patch | 2–4 jam |
| M3 | Artefak ISO/install/CHR + sha256 | image siap boot | 3–5 jam |
| M4 | Server update + portal lisensi aktif | endpoint publik, `upgrade.json` | 1–2 jam |
| M5 | Smoke test QEMU lolos (FR-8) | bukti boot + update + lisensi | 2–4 jam |
| M6 | Runbook + backup key | dokumen operasional | 1 jam |

## 9. Kriteria penerimaan

1. `keys/env` berisi 4 kunci unik; public key di image **berbeda** dari key elseif/madskid/loskiq.
2. Image boot di QEMU sampai prompt login RouterOS.
3. `/system/license print` menunjukkan level 6 (atau lisensi valid) tanpa koneksi ke server MikroTik.
4. `/system/package/update/check-for-updates` mengembalikan versi dari `16.79.7.181`, bukan dari `upgrade.mikrotik.com` (dibuktikan dari access log nginx).
5. Paket resmi MikroTik yang **tidak** di-sign ulang ditolak saat instalasi.
6. Paket hasil sign kita diterima.
7. `upgrade.json` + `NEWESTa7.stable` dapat diakses publik lewat HTTP.
8. Semua artefak punya `.sha256` yang cocok.

## 10. Risiko

- **R1 — loader.7z berpassword.** `patch_loader` butuh `loader/` hasil ekstrak arsip terenkripsi dari `upgrade.mikrotik.ltd`; password hanya ada di GitHub Secrets elseif. Tanpa itu langkah patch loader dilewati (build tetap jalan). Mitigasi: minta password ke author (issue/Telegram), atau uji apakah image tanpa patch loader tetap lolos kriteria 2–6, atau buat `loader/` sendiri.
- **R2 — Port 80/443 tertutup.** Security Group EC2 belum tentu terbuka; RouterOS butuh akses HTTP keluar-masuk. Mitigasi: buka inbound 80/443 di SG, atau pakai port lain + patuh pada batas panjang host.
- **R3 — Tanpa KVM.** Boot test lambat; jangan andalkan iterasi cepat.
- **R4 — Key bocor.** Siapa pun yang punya private key bisa menerbitkan lisensi untuk image kita. Mitigasi: backup offline terenkripsi, rotasi = build ulang.
- **R5 — Versi baru mengubah layout binary.** Patch bisa gagal pada rilis mendatang (mis. string URL berubah). Mitigasi: pin versi, uji dulu di versi baru sebelum mengganti `NEWESTa7.*`.
- **R6 — RAM 1.9 GB.** `mksquashfs` besar bisa OOM saat build paralel. Mitigasi: serial + `-b 256k`, atau tambah swap.
- **R7 — Legalitas.** Bukan lisensi resmi MikroTik.

## 11. Keputusan yang dibutuhkan

1. **Hostname server:** pakai IP `16.79.7.181` (paling sederhana) atau domain pendek ≤19 karakter?
2. **Protokol:** HTTP saja, atau HTTP + HTTPS self-signed?
3. **Target arsitek:** x86 saja, CHR saja, atau keduanya?
4. **Versi:** pin `7.25.1` (stable terbaru) atau `7.24.6` (long-term)?
5. **Lisensi:** cukup jalur offline (`license.py`) atau perlu emulasi server lisensi online?
6. **Password loader.7z:** sudah punya, mau dicari, atau terima risiko tanpa patch loader?
7. **Akses jaringan:** siapa yang membuka Security Group EC2 port 80/443?

## 12. Di luar cakupan

DDNS/cloud backup emulation, dukungan arm64/ARM/MIPS, panel multi-user, otomasi CI di GitHub, migrasi dari image elseif yang sudah terpasang.

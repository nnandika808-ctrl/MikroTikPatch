# Metode elseif — 7.25 / 7.25.1, status SPK-3 + SPK-4

**Kesimpulan SPK-4:** `loader.7z` berpassword tidak lagi jadi blocker. Loader dan wrapper yang sudah diadaptasi **sudah pulih dari ISO acuan** dengan hash yang cocok dengan dokumen historis, jadi password tidak dibutuhkan untuk 7.25.1. Untuk 7.25 password juga tidak dibutuhkan karena resepnya identik; yang dibutuhkan adalah mengulang adaptasi tabel terhadap `mode2` versi itu.

**Cacat yang ditemukan dan sudah ditutup:** resep historis hanya mematch tabel guard, sehingga public key stok tetap hidup di `.text` loader (satu salinan lagi). Tanpa perbaikan ini, audit yang benar akan menolak loader.

## 1. Minimum langkah wajib (SPK-3)

Urutan diambil dari `patch_v7.yml` (setup → option → unpack ISO → paket kurang → loader → patch npk → netinstall → refind → LiveCD → ISO/IMG → CHR → checksum). Yang **tidak bisa dilewati**:

1. `option.npk` dibangun dari `busybox/{busybox_x86,keygen_x86}` (squashfs) lalu di-sign. Paket ini yang menyediakan `/pckg/option/bin/{bash,keygen}` — jalur yang diperiksa loader.
2. Seluruh npk di-`sign` ulang dengan key kita.
3. Paket sistem: patch `boot/EFI/BOOT/BOOTX64.EFI`, `boot/kernel`, `boot/initrd.rgz` (key di initramfs, 32 slot keyman v7).
4. Squashfs sistem: patch key di seluruh binary + rewrite URL, lalu **pasang wrapper**: `nova/bin/mode` (wrapper 202.396 B) menggantikan `mode` stok, dan `mode` stok dipindah jadi `nova/bin/mode2`.
5. Loader: adaptasi tabel guard ke `mode2` yang dikirim + kedua salinan key (lihat §3) + opcode auto-keygen.
6. Re-sign paket sistem, rakit ISO dengan El Torito BIOS **dan** UEFI, IMG, CHR, checksum.

Yang bisa dilewati: LiveCD Alpine (menu 2), refind, netinstall (kalau tidak masuk lingkup), `python3.npk`.

## 2. Status `loader.7z`

| Item | Nilai |
|---|---|
| File | `/tmp/loader.7z`, 168.768 B |
| sha256 | `20b09362b35e43a53f4fdc2e80ef63daff47a5739523a3d82dcb3f80bd023bd0` |
| Password | tidak tersedia (hanya di GitHub Secrets elseif) |
| Perilaku `7z l` | langsung meminta password (header terenkripsi) — "berhasil list" bukan bukti |

**Jalan keluar:** isi arsip sudah terpakai pada build acuan. Aset yang dibutuhkan pulih dari ISO final dan hash-nya cocok:

- loader teradaptasi: `d93a777ee67f3ad9ddbc9d21feb23a1a101b5c5ab2bb3f2a9fb64c2f68c57775`, 87.092 B
- wrapper `nova/bin/mode`: `aadcc83180084ce36d5238c445c31a11b339842aaf93545ea76ca4e365ccce05`, 202.396 B

Simpan keduanya sebagai asset tetap. `patch_loader.py` dari dalam arsip tidak diperlukan karena adaptasi dilakukan langsung dengan `patch_loader_guard.py`.

## 3. Struktur loader dan dua salinan key

Loader memuat 32 byte expected **licence key** di dua tempat, keduanya dengan urutan chunk `[0,1,2,3,4,6,5,7]`:

1. Tabel guard: record `{offset:u32 LE, len:u8, bytes}` di file `0x153e4`, 8 record, terminator offset 0. `offset` menunjuk posisi di `mode2`.
2. Kode hook: 8 instruksi `movl $imm32,-0xNN(%ebp)` di file `0x83ac`, `0x83b6`, `0x83c3`, `0x83d9`, `0x83e3`, `0x83f1`, `0x83fe`, `0x8405` (VMA `0x80503ac`…), yang membangun buffer yang sama di stack sebelum dipakai.

Resep historis mematch (1) saja. Akibatnya build acuan: tabel = key baru, kode = key stok. Audit mendeteksi `STOCK license` di `nova/bin/loader`.

`patch_loader_guard.py` menulis kedua tempat dan memverifikasi keduanya:

```sh
python3.12 /root/mtp/patch_loader_guard.py loader-in loader-out <licence-pubkey-hex>
python3.12 /root/mtp/patch_loader_guard.py --check loader <licence-pubkey-hex>   # PASS/FAIL
```

Pada loader acuan, perbaikan ini mengubah **tepat 32 byte** (hanya salinan kode), ukuran tetap 87.092 B, tabel guard tidak berubah, guard tetap 8/8 terhadap `mode2`.

Catatan: tabel guard meng-encode **licence key**. Ganti keypair berarti tabel dan kode harus ditulis ulang; loader acuan terikat ke key build lama.

## 4. Hasil verifikasi artefak acuan (bukti, bukan klaim)

Dari `mikrotik-7.25.1-patched.iso` → `/routeros-7.25.1.npk` → part `SQUASHFS` → `unsquashfs`:

| Pemeriksaan | Hasil |
|---|---|
| sha256 npk dalam ISO | `609fb14018e0b6ad9557a771a10339ec9cc26bb47e058524ac49999aca518b75` = sama dengan log build |
| `nova/bin/loader` | `d93a777…` = loader acuan (cocok) |
| `nova/bin/mode` | `aadcc831…` = wrapper (cocok) |
| `nova/bin/mode2` | `a0f73b60…` = target (cocok) |
| Guard 8/8 vs `mode2` | cocok, terminator `00000000` |
| Opcode auto-keygen `0x15048` | `0xeb` (nonaktif) |
| `logo.txt` vs stok | identik, `438e1067…` |
| Audit key stok sebelum perbaikan | 1 file (`loader`) |
| Audit key stok sesudah perbaikan | **0 file** |

Verifikasi tanda tangan: bagian EdDSA npk **valid** terhadap public key build yang dipulihkan dari `sys2` (`28f886e3…`). Bagian KCDSA tidak bisa diverifikasi oleh `npk.py` di host ini bahkan untuk npk stok dengan key stok — batasan tool, bukan tanda tangan rusak.

## 5. Keypair: temuan penting

Keypair di `/root/mtp/keys/env` **bukan** keypair yang dipakai build acuan:

- licence key di image: `723a34a6e3300f23e4baa06156b9327514aec170732655f16e04c17928dd770f`
- npk-sign key di image: `28f886e32c141123126cfbcad56766e99d1720ceb1f12be2468bebe7662fbedb`
- key di `keys/env`: `E65B1FFE…` / `C4323F2E…`

Private key build acuan tidak tersimpan. Konsekuensi: build baru memakai keypair `keys/env` (sudah diuji round-trip sign/verify), tabel guard dan salinan kode harus ditulis ulang, dan ISO acuan tetap berlaku sebagai artefak historis tapi tidak bisa ditandatangani ulang.

## 6. URL pada build acuan

`sys2` sudah menunjuk `ros.nansannet.web.id` (20 B, sama panjang dengan `upgrade.mikrotik.com`). Tapi:

- `keyman` masih memuat `licence.mikrotik.com`
- `detnet` masih `cloud.mikrotik.com`
- `cloud` masih `cloud2.mikrotik.com`

Artinya build acuan hanya me-rewrite URL upgrade. Build baru wajib mengisi `MIKRO_LICENCE_URL`/`CUSTOM_LICENCE_URL` dan pasangan `CLOUD*` (lihat `docs/env-build.md`), dan host pengganti sekarang `16.79.7.181` (11 B) sehingga seluruh substitusi memendek, tidak memotong.

## 7. Gate yang belum lulus

- Boot QEMU + `check-for-updates` + `license print` (FR-10) belum dijalankan untuk build baru.
- 7.25: `mode` stok harus diperiksa apakah tetap 96.144 B dan apakah offset guard/kode masih sama; jangan pakai offset 7.25.1 tanpa audit.
- CHR 7.25+: pastikan `option.npk` dan `mode`/`mode2` ikut masuk image CHR.

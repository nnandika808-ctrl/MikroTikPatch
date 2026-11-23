# MikroTikPatch

Patch RouterOS x86/CHR — produksi sendiri dengan keypair sendiri.

| | |
|---|---|
| **Banner** | 100% stok MikroTik (audit gagal build jika beda) |
| **Lisensi** | Offline, permanen P-unlimited (`deadline-at 2100-01-01`) |
| **Update** | Ke server sendiri (URL di dalam `net`+`sys2` ditulis ulang) |
| **Metode** | elseif / madskid / v6, otomatis per versi |

## Metode per versi

| Versi | Metode | Loader | Catatan |
|---|---|---|---|
| 6.49.23 | `v6` (loskiq + fix) | stok | keyman WAJIB dipatch (bug loskiq: blok `mode in files` tidak pernah aktif di v6) |
| 7.23.2–7.24.5 | `madskid` | **stok** (default) | loader ter-patch = hang; kunci permanen justru butuh loader stok |
| **7.25 / 7.25.1 / 7.25.2** | `elseif` | **guard-table rekey + 1 jmp** (lihat seksi bawah) | WAJIB `option.npk` (bash+keygen); installer x86 pilih `a` (all) |

Status terbukti (23 Nov 2026): **7.25.2 lulus** — `nlevel: 6`,
`features: extra-channels`, **tanpa `expires-in`**, tahan reboot; upgrade online
7.23.7 → 7.25.2 dari server sendiri berjalan.

## RESEP FINAL loader v7.25.x (terbukti 7.25.1 & 7.25.2)

Untuk 7.25 ke atas (method `elseif`). Hanya **33 byte** yang boleh berubah dari
loader asli elseif versi itu. Patch `.text` immediate = reboot-loop
`Starting services…`.

1. **Ambil loader asli versi itu** dari release elseif:
   ```
   curl -sSL -o r.npk https://github.com/elseif/MikroTikPatch/releases/download/<V>/routeros-<V>.npk
   7z x r.npk nova/bin/loader nova/bin/mode2
   ```
2. **Isi guard table @0x153E4** = 8 record `{offset:u32 LE, len:u8 (4), chunk:4B}`
   menunjuk posisi kunci di `mode2` versi itu. Offset per versi: **7.25.1 @0x6064,
   7.25.2 @0x8cb7**.
3. **Byte @0x15048: 0x74 → 0xEB** (`je` → `jmp`, melompati pengecekan lisensi).
   **Tanpa ini kunci diterima tapi hilang setelah reboot**.
4. **`.text` biarkan stok** — jangan sentuh 8 immediate `movl` di `0x83ac…0x8405`.
5. `patch_sys.py` pilih `assets/loader-$VER.ref` (fallback `loader-7.25.1.ref`).
6. **`option.npk` WAJIB** (hook 7.25+ cek `/pckg/option/bin/bash` sebelum `memcmp`;
   tanpa option kunci hilang setelah reboot). Installer x86 pilih `a` (all).

`assets/loader-7.25.2.ref` (sha256 `b7a77861…`) = 32 byte guard + 1 byte `@0x15048`.

## Struktur

```
build.sh                 orchestrator: pilih metode -> patch -> audit -> rakit
methods/{v6,madskid,elseif}/  patch.py, license.py, mikro.py, npk.py
assets/                  loader & wrapper referensi (bukan kunci)
bot/                     bot Telegram penerbit lisensi (/ros, /chr)
ubah_url_iso.sh          ganti URL pada ISO jadi + re-sign npk
audit_keys.py            audit: tidak boleh ada public key stok tersisa
```

## Pakai

### 1. Kunci

Buat `keys/env.user` (lihat contoh di bawah). Repo ini **tidak menyimpan
kunci** — sembunyikan file itu, jangan commit (`.gitignore` sudah meng-exclude).

```
export CUSTOM_LICENSE_PRIVATE_KEY="..."   # hasil license.py genkey
export CUSTOM_LICENSE_PUBLIC_KEY="..."
export CUSTOM_NPK_SIGN_PRIVATE_KEY="..."
export CUSTOM_NPK_SIGN_PUBLIC_KEY="..."
export MIKRO_LICENSE_PUBLIC_KEY="8E1067E4305FCDC0CFBF95C10F96E5DFE8C49AEF486BD1A4E2E96C27F01E3E32"
export MIKRO_NPK_SIGN_PUBLIC_KEY="C293CED638A2A33C681FC8DE98EE26C54EADC5390C2DFCE197D35C83C416CF59"
export MIKRO_UPGRADE_URL="download.mikrotik.com"
export CUSTOM_UPGRADE_URL="up.example.com"     # server update Anda
export MIKRO_LICENCE_URL="licence.mikrotik.com"
export CUSTOM_LICENCE_URL="up.example.com"
```

Semua URL custom **tidak boleh lebih panjang** dari aslinya (`url_sub` assert).

### 2. Build

```sh
mkdir -p work/src/7.25.1   # taruh ISO/image resmi di sini, atau biarkan
                           # build.sh mengunduh otomatis
KEYFILE=keys/env.user bash build.sh 7.25.1 x86 --only=iso,img,chr --no-boot --force
```

Artefak keluar di `/srv/artifacts/<versi>/x86/`:
`mikrotik-*-patched.iso`, `install-image-*-patched.{img,zip}`,
`chr-*-patched.{img,qcow2}`, `all_packages-x86-*-patched.zip`, semua + `.sha256`.

### 3. Terbitkan lisensi

```sh
python3 methods/v6/license.py licgenros <software-id> $CUSTOM_LICENSE_PRIVATE_KEY
python3 methods/v6/license.py licgenchr <system-id>   $CUSTOM_LICENSE_PRIVATE_KEY
```

Pasang:
- **Winbox**: System → License → paste key
- **CLI/SSH**: taruh `/var/pckg/<id>.key` lalu `/nova/bin/keyman --find-key`

Berhasil = `/system/license/print` menunjukkan level 6 / p-unlimited **tanpa
`expires-in`**, CHR menunjukkan `deadline-at 2100-01-01`. `expires-in: 23h..`
tanpa kunci terpasang itu **normal** (hitung mundur "belum ada kunci", bukan trial).

### 4. Bot Telegram (opsional)

```sh
bot/bot.py   # token di bot/token, allowlist chat_id di bot/allow
/ros 04S0-0M99   # kunci x86
/chr <system-id> # kunci CHR
```

Jalankan sebagai systemd service; contoh unit ada di docs.

## CI (GitHub Actions)

Tab **Actions** → **Patch RouterOS** → *Run workflow* → isi versi.
Syarat: secret `KEYS_ENV` berisi seluruh isi `keys/env.user`.
Hasil keluar sebagai artifact unduhan.

## Pelajaran penting (yang sudah dibuktikan, bukan teori)

1. Loader ≤7.24.5 **tidak boleh** di-patch via `patch_bin.py` → box hang saat boot. Biarkan stok (`KEEP_STOCK_LOADER=1`, default).
2. Loader madskid (`ff303b70…`) **diperlukan** supaya lisensi tidak hilang tiap reboot — jangan dibiarkan stok.
3. `nlevel` vs `level` hanya beda tampilan x86 vs CHR — bukan indikator masalah.
4. 6.49.23: pastikan keyman ter-patch (audit `our_key_files` harus ≥ 4; jika 3 = bug loskiq kambuh).
5. 7.25.x: guard-table rekey + byte `@0x15048` → `EB`, `.text` stok, dan `option.npk` wajib (lihat resep penuh di atas). Tanpa byte `@0x15048`, kunci diterima tapi hilang setelah reboot.
6. 7.25.2 terverifikasi: `nlevel: 6`, tanpa `expires-in`; upgrade online 7.23.7 → 7.25.2 jalan.

# MikroTikPatch — Produksi Sendiri

Patch RouterOS x86/CHR dengan keypair sendiri: banner stok, lisensi offline
permanen (level 6 P-unlimited), dan server update sendiri.

## Metode per versi

| Versi | Metode | Catatan |
|---|---|---|
| 6.49.23 | `v6` (loskiq + fix keyman) | keyman WAJIB dipatch (bug loskiq) |
| 7.23.7, 7.24.5 | `madskid` + loader stok | loader dibiarkan stok (default) |
| 7.25, 7.25.1 | `elseif` | wrapper mode + loader ter-guard |

## Build

```sh
# 1. siapkan keys/env.user (lihat "Kunci" di bawah)
# 2. unduh sumber ISO/image ke work/src/<versi>/
KEYFILE=keys/env.user bash build.sh <versi> x86 --only=iso,img,chr --no-boot --force
```

Hasil: `/srv/artifacts/<versi>/x86/` — ISO, install-image, CHR, all_packages (+sha256).

## Kunci

Pakai file `keys/env.user` (TIDAK ada di repo ini). Format:

```
export CUSTOM_LICENSE_PRIVATE_KEY="..."   # 9DBC.. (README madskid) atau milik sendiri
export CUSTOM_LICENSE_PUBLIC_KEY="..."
export CUSTOM_NPK_SIGN_PRIVATE_KEY="..."
export CUSTOM_NPK_SIGN_PUBLIC_KEY="..."
export MIKRO_LICENSE_PUBLIC_KEY="8E1067E4305FCDC0CFBF95C10F96E5DFE8C49AEF486BD1A4E2E96C27F01E3E32"
export MIKRO_NPK_SIGN_PUBLIC_KEY="C293CED638A2A33C681FC8DE98EE26C54EADC5390C2DFCE197D35C83C416CF59"
export MIKRO_UPGRADE_URL="download.mikrotik.com"
export CUSTOM_UPGRADE_URL="up.example.com"
export MIKRO_LICENCE_URL="licence.mikrotik.com"
export CUSTOM_LICENCE_URL="up.example.com"
export MIKRO_CLOUD_URL="cloud.mikrotik.com"
export CUSTOM_CLOUD_URL="up.example.com"
export MIKRO_RENEW_URL="renew.mikrotik.com"
export CUSTOM_RENEW_URL="up.example.com"
```

Generate keypair sendiri: `python3 methods/v6/license.py genkey`.

## Lisensi (offline)

```sh
python3 methods/v6/license.py licgenros <software-id> <CUSTOM_LICENSE_PRIVATE_KEY>   # x86
python3 methods/v6/license.py licgenchr <system-id>   <CUSTOM_LICENSE_PRIVATE_KEY>   # CHR
```

Pasang: paste lewat Winbox (System → License → Renew/paste key), atau taruh di
`/var/pckg/<id>.key` lalu `/nova/bin/keyman --find-key`.
Permanen = tidak ada `expires-in`, `deadline-at 2100-01-01`.

## Bot Telegram (opsional)

`bot/bot.py` — `/ros <software-id>`, `/chr <system-id>`. Token di
`bot/token`, allowlist chat di `bot/allow`. Jalankan sebagai service
(`roslic-bot.service`).

## Ubah URL pada ISO jadi

```sh
bash ubah_url_iso.sh <iso-asli> <versi> <npk> <iso-keluaran> <url-baru>
```

Ganti `net`+`sys2`, re-sign npk, rakit ulang ISO, verifikasi otomatis.

## Update server

Letakkan hasil build di `/srv/www/routeros/<versi>/` (npk + file `info`
berisi `<versi> <build-number>`). `NEWESTa7.stable`, `NEWESTa7.long-term`,
`NEWEST6.stable`, `NEWEST6.long-term` wajib ada.

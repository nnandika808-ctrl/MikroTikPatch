# Env build — nama variabel, nilai, dan batas panjang

Semua nilai hidup di `keys/env` (0600, root). `source keys/env` sebelum menjalankan patcher. Jangan menaruh private key di repo, log, atau dokumen.

## Aturan keras

`patch.py` memakai `bytes.replace(old, new)`. Pengganti **tidak boleh lebih panjang** dari aslinya; kalau lebih panjang, ekor string terpotong dan host jadi sampah. Panjang di bawah dihitung dari byte asli.

| Variabel | Nilai | Panjang | Pengganti | Panjang | Sisa |
|---|---|---|---|---|---|
| `MIKRO_LICENCE_URL` | `licence.mikrotik.com` | 20 | `16.79.7.181` | 11 | −9 |
| `MIKRO_UPGRADE_URL` | `upgrade.mikrotik.com` | 20 | `16.79.7.181` | 11 | −9 |
| `MIKRO_CLOUD_URL` | `cloud.mikrotik.com` | 18 | `16.79.7.181` | 11 | −7 |
| `MIKRO_CLOUD2_URL` | `cloud2.mikrotik.com` | 19 | `16.79.7.181` | 11 | −8 |

Kalau kelak pindah ke domain, batasnya 19 byte dan seluruh baris di atas harus diperiksa ulang — termasuk bahwa keempat pengganti tetap ≤ panjang masing-masing aslinya.

## Variabel yang dipakai

Key (wajib):

```
MIKRO_NPK_SIGN_PUBLIC_KEY / CUSTOM_NPK_SIGN_PUBLIC_KEY
MIKRO_LICENSE_PUBLIC_KEY  / CUSTOM_LICENSE_PUBLIC_KEY
CUSTOM_NPK_SIGN_PRIVATE_KEY
CUSTOM_LICENSE_PRIVATE_KEY
```

URL (wajib untuk build yang menunjuk server sendiri):

```
MIKRO_{LICENCE,UPGRADE,CLOUD,CLOUD2}_URL / CUSTOM_{…}_URL
```

Opsional / kosongkan bila tidak dipakai:

- `MIKRO_RENEW_URL` / `CUSTOM_RENEW_URL` — **tidak ada** host `renew.mikrotik.com` di 7.25.1 (hanya kata "renew" di `cerm`, `net`, `keyman`). Baru diisi kalau rilis tertentu benar-benar memuatnya.
- `MIKRO_CLOUD_PUBLIC_KEY` / `CUSTOM_CLOUD_PUBLIC_KEY` — hanya untuk emulasi cloud DDNS (non-tujuan). Pasangan yang kosong otomatis dilewati `patch.py`.

## Perilaku yang perlu diketahui

- Pasangan dengan sisi kosong **dibuang** dari tabel (`{k: v for k, v in … if k and v}`), jadi aman dibiarkan kosong.
- `MIKRO_*_URL` adalah string stok yang dicari; kalau salah ketik, tidak ada error — hanya tidak ada yang berubah. Periksa hasil dengan grep, jangan percaya exit code.
- `LICENCE` dieja "LICENCE" (bukan "LICENSE") di seluruh kode elseif. `LICENSE` akan diabaikan diam-diam.
- Rewrite URL hanya terjadi di `mode`/`keyman` (blok khusus) dan seluruh file lain lewat loop generik; `licupgr` punya jalur renew terpisah.

## Verifikasi wajib setelah patch

```sh
grep -rl "mikrotik\.com" sq/            # hanya boleh www/help/manual/cdn + logo.txt
grep -ra "16.79.7.181" sq/ | head       # harus muncul di sys2, net, keyman, detnet, cloud
```

`www.mikrotik.com`, `help.mikrotik.com`, `manual.mikrotik.com`, `cdn.mikrotik.com` memang tetap stok — itu tautan dokumentasi/WebFig, bukan jalur update. Jangan "membersihkan"-nya dengan substitusi buta.

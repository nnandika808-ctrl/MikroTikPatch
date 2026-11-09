#!/bin/bash
# ubah_url_iso.sh <iso-asli> <versi> <npk-di-iso> <keluaran-iso> [new_url]
# Ganti URL upgrade di net+sys2 pada squashfs paket sistem, re-pack, re-sign,
# lalu rakit ulang ISO. File asli tidak disentuh.
set -euo pipefail

SRC="${1:?iso asli}"; V="${2:?versi}"; NPKNAME="${3:?npk dalam iso}"; OUT="${4:?iso keluaran}"
NEWURL="${5:-up.nansannet.cloud}"
OLDURL="${OLDURL:-ros.nansannet.web.id}"

MTP=/root/mtp; PY=/usr/bin/python3.12
W=/root/.hermes/cache/scratch/urlfix-$V
rm -rf "$W"; mkdir -p "$W"/{iso,npk,sq}

set -a; . "$MTP/keys/env.user"; set +a
export MP="$MTP/methods/v6"

say() { echo "=== $(date +%H:%M:%S) | $*"; }

say "ekstrak ISO"
xorriso -osirrox on -indev "$SRC" -extract "/$NPKNAME" "$W/npk/r.npk" >/dev/null 2>&1
xorriso -osirrox on -indev "$SRC" -extract / "$W/iso" >/dev/null 2>&1 || true

say "bongkar squashfs"
( cd "$W/npk" && PYTHONPATH="$MP" $PY "$MTP/xnpk.py" r.npk . >/dev/null 2>&1 )
unsquashfs -q -d "$W/sq" "$W/npk"/*.sfs >/dev/null

say "ganti URL: $OLDURL -> $NEWURL"
for b in net sys2; do
  [ -f "$W/sq/nova/bin/$b" ] || { echo "  $b tidak ada, lewati"; continue; }
  $PY "$MTP/ganti_url.py" "$W/sq/nova/bin/$b" "$OLDURL" "$NEWURL" | tail -2
done

say "repack squashfs"
mksquashfs "$W/sq" "$W/npk/squashfs.sfs" -no-recovery -noappend -exit-on-error -quiet \
  -comp xz -no-xattrs -b 256k -all-root >/dev/null

say "re-sign npk"
$PY - "$W/npk/r.npk" "$W/npk/squashfs.sfs" <<'EOF'
import os, sys
sys.path.insert(0, os.environ['MP'])
from npk import NovaPackage, NpkPartID
p = NovaPackage.load(sys.argv[1])
p[NpkPartID.SQUASHFS].data = open(sys.argv[2], 'rb').read()
p.sign(bytes.fromhex(os.environ['CUSTOM_LICENSE_PRIVATE_KEY']),
       bytes.fromhex(os.environ['CUSTOM_NPK_SIGN_PRIVATE_KEY']))
p.save(sys.argv[1])
print("npk ditandatangani ulang")
EOF

say "pasang npk ke iso"
rm -f "$W/iso/$NPKNAME"
cp "$W/npk/r.npk" "$W/iso/$NPKNAME"

say "rakit ISO"
if [ -f "$W/iso/efiboot.img" ]; then
  xorriso -as mkisofs -o "$OUT" \
    -V "MikroTik $V x86" -publisher "WWW.MIKROTIK.COM" -preparer "MIKROTIK" \
    -A MIKROTIK_ROUTER -sysid "" \
    -b 'isolinux/isolinux.bin' -c 'isolinux/boot.cat' -no-emul-boot -boot-load-size 4 -boot-info-table \
    -eltorito-alt-boot -e efiboot.img -no-emul-boot -boot-load-size 2048 \
    -R -J -input-charset utf-8 -iso-level 3 "$W/iso" >/dev/null
else
  xorriso -as mkisofs -o "$OUT" \
    -V "MikroTik $V" -publisher "WWW.MIKROTIK.COM" -preparer "MIKROTIK" \
    -A MIKROTIK_ROUTER -sysid "" \
    -b 'isolinux/isolinux.bin' -c 'isolinux/boot.cat' -no-emul-boot -boot-load-size 4 -boot-info-table \
    -R -J -input-charset utf-8 -iso-level 3 "$W/iso" >/dev/null
fi

say "verifikasi"
$PY - "$OUT" "$NPKNAME" "$NEWURL" "$OLDURL" <<'EOF'
import os, subprocess, sys, tempfile
iso, npkname, new, old = sys.argv[1:5]
d = tempfile.mkdtemp()
subprocess.run(["xorriso", "-osirrox", "on", "-indev", iso, "-extract", "/" + npkname, d + "/r.npk"],
               capture_output=True)
subprocess.run(["/usr/bin/python3.12", "/root/mtp/xnpk.py", d + "/r.npk", d],
               capture_output=True, env={**os.environ, "PYTHONPATH": "/root/mtp/methods/v6"})
subprocess.run(["unsquashfs", "-q", "-d", d + "/sq", d + "/sq0.sfs"], capture_output=True)
bad = 0
for b in ("net", "sys2"):
    data = open(d + "/sq/nova/bin/" + b, "rb").read()
    n_new = data.count(new.encode())
    n_old = data.count(old.encode())
    print("  " + b + ": baru=" + str(n_new) + " lama=" + str(n_old))
    bad += n_old
print("VERIFIKASI " + ("OK" if bad == 0 else "GAGAL"))
EOF
ls -l "$OUT"

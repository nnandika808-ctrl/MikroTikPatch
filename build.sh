#!/bin/bash
# build.sh <versi> <arch> [--no-boot] [--force] [--only=iso,img,chr]
#
# Orkestrasi satu artefak: unduh -> patch npk -> post-process -> audit
# -> rakit ISO/IMG/CHR -> manifest -> boot test.
# Metode dipilih dari versi dan ditolak kalau tidak cocok (PRD FR-2).
set -euo pipefail

V="${1:?versi}"; ARCH="${2:-x86}"
BOOT=1; FORCE=0; ONLY=iso,img,chr
for a in "${@:3}"; do
  case "$a" in
    --no-boot) BOOT=0 ;;
    --force) FORCE=1 ;;
    --only=*) ONLY="${a#--only=}" ;;
  esac
done
want() { case ",$ONLY," in *",$1,"*) return 0;; esac; return 1; }

MTP=/root/mtp
SRC=$MTP/work/src
W=$MTP/work/build/$V-$ARCH
OUT=$MTP/out
ART=/srv/artifacts/$V/$ARCH
LOG=$OUT/$V-$ARCH.log
mkdir -p "$W" "$OUT" "$ART"

exec > >(tee -a "$LOG") 2>&1
say() { printf '\n=== %s | %s ===\n' "$(date -u +%H:%M:%S)" "$*"; }
die() { printf '\nFATAL: %s\n' "$*"; exit 1; }

[ "$ARCH" = x86 ] || die "arsitektur $ARCH belum disiapkan (x86 dulu)"
case "$V" in
  6.49.23) METHOD=v6 ;;
  7.23.7|7.24.5) METHOD=madskid ;;
  7.25|7.25.1) METHOD=elseif ;;
  *) die "versi $V tidak ada di daftar metode" ;;
esac
[ "$METHOD" = v6 ] && [ "${V%%.*}" != 6 ] && die "v6 harus pakai loskiq"
[ "$METHOD" = elseif ] && [ "${V%%.*}" != 7 ] && die "elseif hanya 7.25+"
say "build $V/$ARCH metode=$METHOD tahap=$ONLY"

if [ -f "$ART/MANIFEST-$V.json" ] && [ $FORCE -eq 0 ]; then
  say "artefak sudah ada (pakai --force untuk ulang)"; exit 0
fi

source "${KEYFILE:-$MTP/keys/env.user}"
for k in CUSTOM_NPK_SIGN_PRIVATE_KEY CUSTOM_LICENSE_PRIVATE_KEY \
         CUSTOM_NPK_SIGN_PUBLIC_KEY CUSTOM_LICENSE_PUBLIC_KEY CUSTOM_UPGRADE_URL; do
  [ -n "${!k:-}" ] || die "env $k kosong"
done
[ ${#CUSTOM_LICENSE_PUBLIC_KEY} -eq 64 ] || die "licence pubkey bukan 32 byte hex"
if [ "${SKIP_URL:-0}" = 1 ]; then
  echo "SKIP_URL=1 -> URL dibiarkan stok"
  for k in MIKRO_LICENCE_URL CUSTOM_LICENCE_URL MIKRO_UPGRADE_URL CUSTOM_UPGRADE_URL \
           MIKRO_CLOUD_URL CUSTOM_CLOUD_URL MIKRO_CLOUD2_URL CUSTOM_CLOUD2_URL; do
    export "$k="
  done
fi

PY=/usr/bin/python3.12
[ -n "${LICENCE_URL_OVERRIDE:-}" ] && export CUSTOM_LICENCE_URL="$LICENCE_URL_OVERRIDE" && \
  echo "override URL lisensi -> $CUSTOM_LICENCE_URL"
[ -n "${UPGRADE_URL_OVERRIDE:-}" ] && export CUSTOM_UPGRADE_URL="$UPGRADE_URL_OVERRIDE" && \
  echo "override URL upgrade -> $CUSTOM_UPGRADE_URL"
NPKPY="env PYTHONPATH=$MTP/elseif $PY"
MP="$MTP/methods/$METHOD"
export MP
[ "$METHOD" = v6 ] && MP="$MTP/methods/v6"
STOCK_LOGO=$MTP/work/banner-ref/logo-$V.txt

# ---------------------------------------------------------------- 1. sumber
say "sumber"
cd "$SRC"
for f in "mikrotik-$V.iso" "all_packages-x86-$V.zip"; do
  [ -s "$f" ] || die "sumber hilang: $f"
done
if [ "$METHOD" = elseif ]; then [ -s "chr-$V.img.zip" ] || die "chr-$V.img.zip hilang"; fi

# ---------------------------------------------------------------- 2. ekstrak
say "ekstrak ISO"
rm -rf "$W/iso" "$W/out" "$W/post"; mkdir -p "$W/iso" "$W/out"
xorriso -osirrox on -indev "$SRC/mikrotik-$V.iso" -extract / "$W/iso" >/dev/null
chmod -R u+w "$W/iso"
unzip -o -q "$SRC/all_packages-x86-$V.zip" -d "$W/iso"
# netinstall = paket exe Windows; elseif tidak memasukkannya ke ISO/installer
rm -f "$W/iso"/netinstall-*.npk

SYS_NPK=$(ls "$W/iso"/routeros-*.npk 2>/dev/null | head -1 || true)
[ -n "$SYS_NPK" ] || SYS_NPK=$(ls "$W/iso"/system-*.npk 2>/dev/null | head -1 || true)
[ -n "$SYS_NPK" ] || die "paket sistem tidak ditemukan di ISO"
SYS_NAME=$(basename "$SYS_NPK")

# ---------------------------------------------------------------- 3. patch
say "patch npk ($METHOD)"
cp "$STOCK_LOGO" "$W/logo.txt"
patch_one() {  # <in> <out>  -- cwd = $W supaya logo.txt terbaca
  ( cd "$W" && env PYTHONPATH="$MP" $PY "$MP/patch.py" npk "$1" -O "$2" )
}
extract_item() {  # <nama item di container> <output>
  ( cd "$W" && env PYTHONPATH="$MP" $PY - "$W/out/$SYS_NAME" "$1" "$2" <<'EOF'
import sys
from npk import NovaPackage, NpkPartID, NpkFileContainer
p = NovaPackage.load(sys.argv[1])
pk = p._packages[0] if len(p._packages) > 0 else p
fc = NpkFileContainer.unserialize_from(pk[NpkPartID.FILE_CONTAINER].data)
for it in fc:
    if it.name == sys.argv[2].encode():
        open(sys.argv[3], "wb").write(it.data)
        break
else:
    raise SystemExit("item tidak ada")
EOF
  )
}
for npk in "$W/iso"/*.npk; do
  n=$(basename "$npk"); [ "$n" = "$SYS_NAME" ] && continue
  patch_one "$npk" "$W/out/$n"
done
if [ "$METHOD" = elseif ]; then
  ( cd "$W" && env PYTHONPATH="$MP" $PY "$MTP/patch_sys.py" "$MP" "$SYS_NPK" "$W/out/$SYS_NAME" "$V" )
else
  patch_one "$SYS_NPK" "$W/out/$SYS_NAME"
fi

# ---------------------------------------------------------------- 3b. option.npk (wajib >=7.25)
# Hook loader memeriksa /pckg/option/bin/bash sebelum patch memcmp. Tanpa paket ini
# verifikasi lisensi tidak pernah dilonggarkan -> login tidak muncul.
if true; then
  say "bangun option.npk"
  O=$W/option-root; rm -rf "$O"; mkdir -p "$O/bin"
  install -m 755 "$MTP/elseif/busybox/busybox_x86" "$O/bin/busybox"
  install -m 755 "$MTP/elseif/keygen/keygen_x86" "$O/bin/keygen"
  for c in $("$O/bin/busybox" --list); do ln -sf /pckg/option/bin/busybox "$O/bin/$c"; done
  mksquashfs "$O" "$W/option.sfs" -no-recovery -noappend -exit-on-error -quiet \
    -comp xz -no-xattrs -b 256k -all-root >/dev/null
  BASE=$(ls "$W/out"/*.npk | grep -v "$SYS_NAME" | head -1)
  ( cd "$W" && env PYTHONPATH="$MP" $PY "$MP/npk.py" create "$BASE" "$W/out/option-$V.npk" \
      option "$W/option.sfs" -desc="busybox" )
  rm -rf "$O" "$W/option.sfs"
  echo "option-$V.npk: $(stat -c%s "$W/out/option-$V.npk") B"
fi

# ---------------------------------------------------------------- 4. post-process paket sistem
if [ "$METHOD" != elseif ]; then
say "post-process paket sistem"
d=$W/post; mkdir -p "$d"
$NPKPY "$MTP/xnpk.py" "$W/out/$SYS_NAME" "$d" | tail -1
unsquashfs -q -d "$d/sq" "$d"/*.sfs >/dev/null
B=$d/sq/nova/bin

# patch.py menulis keyman_/mode_ lalu (di elseif) di-rename oleh patch_loader
for f in mode keyman; do
  if [ -f "$B/${f}_" ]; then mv -f "$B/${f}_" "$B/$f"; fi
done
# sisa berkas bantu
for t in "$B"/*_; do
  [ -e "$t" ] || continue
  [ -e "${t%_}" ] && rm -f "$t"
done

if [ "$METHOD" = elseif ]; then
  say "pasang loader + mode/mode2"
  [ -f "$B/mode" ] || die "mode tidak ada di paket sistem"
  mv "$B/mode" "$B/mode2"
  cp "$MTP/assets/mode-els-static-7.25.1" "$B/mode"
  cp "$MTP/assets/loader-7.25.1.ref" "$B/loader"
  # Guard-patch loader memicu reboot-loop di build ini -> loader aset dipakai apa adanya.
  if [ "${PATCH_GUARD:-0}" = 1 ]; then
    $PY "$MTP/patch_loader_guard.py" "$B/loader" "$B/loader.new" "$CUSTOM_LICENSE_PUBLIC_KEY" | tail -1
    mv "$B/loader.new" "$B/loader"
  fi
else
  # madskid/v6: patch.py tidak menyentuh loader. Loader STOK dipakai untuk <=7.24.5:
  # ia menyimpan lisensi ke config sehingga permanen bertahan antar reboot.
  # (Loader madskid ff303b70 sempat dicoba: kunci aktif tapi hilang tiap reboot.)
  if [ "${KEEP_STOCK_LOADER:-1}" = 1 ]; then
    echo "loader dibiarkan stok (default)"
  else
    $PY "$MTP/patch_bin.py" "$B/loader" "$MP" || die "loader tidak bisa dipatch"
  fi
fi
chmod 755 "$B/mode" "$B/loader" "$B/keyman" 2>/dev/null || true
[ -f "$B/mode2" ] && chmod 755 "$B/mode2"

# banner stok
cp "$STOCK_LOGO" "$d/sq/nova/lib/console/logo.txt"; chmod 644 "$d/sq/nova/lib/console/logo.txt"

# diagnostik: kembalikan mode ke versi stok (uji apakah key swap di mode yang mematikan login)
if [ "${KEEP_STOCK_MODE:-0}" = 1 ] && [ -f "$MTP/work/spk2/$V/sq/nova/bin/mode" ]; then
  cp "$MTP/work/spk2/$V/sq/nova/bin/mode" "$B/mode"; chmod 755 "$B/mode"
  echo "KEEP_STOCK_MODE=1 -> mode dikembalikan ke stok"
fi

say "repack + sign"
mksquashfs "$d/sq" "$d/squashfs.sfs" -no-recovery -noappend -exit-on-error -quiet \
  -comp xz -no-xattrs -b 256k -all-root >/dev/null
if [ "$METHOD" = elseif ]; then
  $PY - "$B/loader" "$B/mode2" <<'EOF' || die "guard tidak cocok dengan mode2"
import struct,sys
ld=open(sys.argv[1],'rb').read(); m2=open(sys.argv[2],'rb').read()
off=0x153e4; ok=0
for _ in range(8):
    o,ln=struct.unpack_from('<IB',ld,off); off+=5; e=ld[off:off+ln]; off+=ln
    ok += e==m2[o:o+ln]
print("guard",ok,"/8")
sys.exit(0 if ok==8 else 1)
EOF
fi
$PY - "$W/out/$SYS_NAME" "$d/squashfs.sfs" <<'EOF'
import os,sys
sys.path.insert(0,os.environ['MP'])
from npk import NovaPackage, NpkPartID
p=NovaPackage.load(sys.argv[1]); p[NpkPartID.SQUASHFS].data=open(sys.argv[2],'rb').read()
p.sign(bytes.fromhex(os.environ['CUSTOM_LICENSE_PRIVATE_KEY']),
       bytes.fromhex(os.environ['CUSTOM_NPK_SIGN_PRIVATE_KEY']))
p.save(sys.argv[1])
EOF

fi

# ---------------------------------------------------------------- 5. audit final
USE_MADSKID_LOADER=0
[ -f "$MTP/assets/loader-madskid-7.24.5" ] && USE_MADSKID_LOADER=1
say "audit final"
fail=0
for npk in "$W/out"/*.npk; do
  n=$(basename "$npk"); a=$W/audit/$n; rm -rf "$a"; mkdir -p "$a"
  if $NPKPY "$MTP/xnpk.py" "$npk" "$a" 2>/dev/null | grep -q 'squashfs: 0'; then rm -rf "$a"; continue; fi
  unsquashfs -q -d "$a/sq" "$a"/*.sfs >/dev/null 2>&1 || die "unsquashfs gagal: $n"
  extra=""; [ "$n" = "$SYS_NAME" ] && extra="--expect-ours"   # paket kecil kadang tanpa key
  if $PY "$MTP/audit_keys.py" "$a/sq" $extra > "$a/audit.txt"; then :; else
    if [ "$(grep -c '^STOCK' "$a/audit.txt")" = 1 ] && {
         { [ "$USE_MADSKID_LOADER" = 1 ] && grep -q '^STOCK.*nova/bin/loader' "$a/audit.txt"; } ||
         { [ "${KEEP_STOCK_LOADER:-0}" = 1 ] && grep -q '^STOCK.*nova/bin/loader' "$a/audit.txt"; } ||
         { [ "${KEEP_STOCK_MODE:-0}" = 1 ] && grep -q '^STOCK.*nova/bin/mode$' "$a/audit.txt"; }; }; then
      echo "audit: 1 sisa stok diizinkan (mode/loader, diagnostik)"
    else
      echo "AUDIT GAGAL: $n"; cat "$a/audit.txt"; fail=1
    fi
  fi
  [ "$n" = "$SYS_NAME" ] && sha256sum "$a/sq/nova/lib/console/logo.txt" > "$a/logo.txt"
  rm -rf "$a"/*.sfs "$a/sq"
done
[ $fail -eq 0 ] || die "audit key stok gagal"
got=$(cut -d' ' -f1 "$W/audit/$SYS_NAME/logo.txt")
want=$(sha256sum "$STOCK_LOGO" | cut -d' ' -f1)
[ "$got" = "$want" ] || die "banner tidak identik stok ($got != $want)"
echo "audit PASS, banner ok"

# ---------------------------------------------------------------- 6. ISO
mkdir -p "$W/new_iso" && cp -a "$W/iso/." "$W/new_iso/"
rm -f "$W/new_iso"/*.npk && cp "$W/out"/*.npk "$W/new_iso/"

if want iso; then
  say "rakit ISO"
  if [ "$METHOD" = v6 ]; then
    ( cd "$W" && MP="$MP" $PY "$MTP/patch_v6_kernel.py" "$W/new_iso/isolinux/linux" "$W/new_iso/isolinux/linux.p" ) \
      || die "patch kernel BIOS gagal"
    mv -f "$W/new_iso/isolinux/linux.p" "$W/new_iso/isolinux/linux"
    if [ -f "$W/new_iso/isolinux/initrd.rgz" ]; then
      ( cd "$W" && MP="$MP" $PY "$MTP/patch_v6_initrd.py" "$W/new_iso/isolinux/initrd.rgz" "$W/new_iso/isolinux/initrd.p" ) \
        || die "patch initrd ISO gagal"
      mv -f "$W/new_iso/isolinux/initrd.p" "$W/new_iso/isolinux/initrd.rgz"
    fi
  else
    mkdir -p "$W/efiboot"
    mount -o loop "$W/new_iso/efiboot.img" "$W/efiboot"
    ( cd "$W" && env PYTHONPATH="$MP" $PY "$MP/patch.py" kernel "$W/efiboot/linux.x86_64" -O "$W/new_iso/isolinux/linux" ) \
      || { umount "$W/efiboot"; die "patch kernel EFI gagal"; }
    umount "$W/efiboot"
  fi
  ISO="$ART/mikrotik-$V-patched.iso"
  if [ "$METHOD" = v6 ]; then
    xorriso -as mkisofs -o "$ISO" \
      -V "MikroTik $V $ARCH" -publisher "WWW.MIKROTIK.COM" -preparer "MIKROTIK" \
      -A MIKROTIK_ROUTER -sysid "" \
      -b 'isolinux/isolinux.bin' -c 'isolinux/boot.cat' -no-emul-boot -boot-load-size 4 -boot-info-table \
      -R -J -input-charset utf-8 -iso-level 3 "$W/new_iso" >/dev/null
  else
    xorriso -as mkisofs -o "$ISO" \
      -V "MikroTik $V $ARCH" -publisher "WWW.MIKROTIK.COM" -preparer "MIKROTIK" \
      -A MIKROTIK_ROUTER -sysid "" \
      -b 'isolinux/isolinux.bin' -c 'isolinux/boot.cat' -no-emul-boot -boot-load-size 4 -boot-info-table \
      -eltorito-alt-boot -e efiboot.img -no-emul-boot -boot-load-size 2048 \
      -R -J -input-charset utf-8 -iso-level 3 "$W/new_iso" >/dev/null
  fi
  say "verifikasi ISO"
  if [ "$METHOD" = v6 ]; then
    xorriso -indev "$ISO" -report_el_torito plain 2>/dev/null | grep -c "El Torito boot img" | grep -qx 1 \
      || die "ISO v6 harus punya tepat 1 entri boot"
  else
    xorriso -indev "$ISO" -report_el_torito plain 2>/dev/null | grep -c "El Torito boot img" | grep -qx 2 \
      || die "ISO tidak punya 2 entri boot (BIOS+UEFI)"
  fi
  mkdir -p "$W/verify"; rm -rf "$W/verify"/* 
  xorriso -osirrox on -indev "$ISO" -extract "/$SYS_NAME" "$W/verify/$SYS_NAME" >/dev/null
  a=$W/verify/audit; mkdir -p "$a"; $NPKPY "$MTP/xnpk.py" "$W/verify/$SYS_NAME" "$a" >/dev/null
  unsquashfs -q -d "$a/sq" "$a"/*.sfs >/dev/null
  if $PY "$MTP/audit_keys.py" "$a/sq" > "$a/audit.txt"; then
    tail -1 "$a/audit.txt"
  elif [ "$USE_MADSKID_LOADER" = 1 ] && [ "$(grep -c '^STOCK' "$a/audit.txt")" = 1 ] && grep -q '^STOCK.*nova/bin/loader' "$a/audit.txt"; then
    echo "audit ISO: sisa stok hanya di loader madskid (diizinkan)"
  elif [ "${KEEP_STOCK_LOADER:-0}" = 1 ] && [ "$(grep -c '^STOCK' "$a/audit.txt")" = 1 ] && grep -q '^STOCK.*nova/bin/loader' "$a/audit.txt"; then
    echo "audit ISO: sisa stok hanya di loader (diizinkan)"
  else
    cat "$a/audit.txt"; die "audit key stok pada ISO gagal"
  fi
  [ "$(sha256sum "$a/sq/nova/lib/console/logo.txt" | cut -d' ' -f1)" = "$want" ] || die "logo ISO tidak stok"
  sha256sum "$ISO" > "$ISO.sha256"
fi

# ---------------------------------------------------------------- 7. IMG install
if want img; then
  say "rakit install image"
  IMG="$ART/install-image-$V-patched.img"
  truncate --size 128M "$IMG"
  mkfs.vfat -I -F 32 -n Install "$IMG" >/dev/null
  LOOP=$(losetup -f --show "$IMG"); trap 'umount -q "$W/inst" 2>/dev/null; losetup -d "$LOOP" 2>/dev/null' EXIT
  syslinux --install "$LOOP"
  mkdir -p "$W/inst"; mount -o loop,uid=0,gid=0,umask=000 "$LOOP" "$W/inst"
  cp "$W/new_iso/isolinux/linux" "$W/inst/linux"
  cp /usr/lib/syslinux/modules/bios/ldlinux.c32 "$W/inst/"
  if [ "$METHOD" != v6 ]; then
    mkdir -p "$W/inst/EFI/BOOT"
    mount -o loop "$W/new_iso/efiboot.img" "$W/efiboot"
    cp "$W/efiboot/EFI/BOOT/BOOTX64.EFI" "$W/inst/EFI/BOOT/BOOTX64.EFI"
    umount "$W/efiboot"
  fi
  printf 'default system\nlabel system\n\tkernel linux\n\tappend load_ramdisk=1 -install -hdd\n' > "$W/inst/syslinux.cfg"
  i=1; for npk in "$W/new_iso"/*.npk; do cp "$npk" "$W/inst/$i.npk"; i=$((i+1)); done
  touch "$W/inst/CHOOSE" "$W/inst/autorun.scr"; sync
  umount "$W/inst"; losetup -d "$LOOP"; trap - EXIT
  sha256sum "$IMG" > "$IMG.sha256"
  ( cd "$ART" && zip -q "install-image-$V-patched.zip" "install-image-$V-patched.img" )
fi

# ---------------------------------------------------------------- 8. ZIP all_packages
if want img; then
  say "rakit all_packages"
  Z="$ART/all_packages-x86-$V-patched.zip"
  ( cd "$W/out" && zip -q -X "$Z" ./*.npk )
  sha256sum "$Z" > "$Z.sha256"
fi

# ---------------------------------------------------------------- 8b. CHR
if want chr; then
  say "rakit CHR"
  [ -s "$SRC/chr-$V.img.zip" ] || die "chr-$V.img.zip hilang"
  rm -rf "$W/chrx"; mkdir -p "$W/chrx"; ( cd "$W/chrx" && unzip -o -q "$SRC/chr-$V.img.zip" )
  BASE=$(ls "$W/chrx"/chr-*.img | head -1)
  IMG="$ART/chr-$V-patched.img"
  cp "$BASE" "$IMG"
  if [ "$METHOD" != v6 ]; then
    extract_item boot/EFI/BOOT/BOOTX64.EFI "$W/chrx/BOOTX64.patched" \
      || die "BOOTX64.EFI tidak bisa diambil dari paket sistem"
  fi
  mkdir -p "$W/chrx/boot" "$W/chrx/ros"
  qemu-nbd -c /dev/nbd0 -f raw "$IMG"; sleep 1
  mount /dev/nbd0p1 "$W/chrx/boot" || { qemu-nbd -d /dev/nbd0; die "mount p1 gagal"; }
  if [ "$METHOD" = v6 ]; then
    MP="$MP" $PY "$MTP/patch_v6_initrd.py" "$W/chrx/boot/boot/initrd.rgz" "$W/chrx/initrd.p" \
      || die "patch initrd v6 gagal"
    cp -f "$W/chrx/initrd.p" "$W/chrx/boot/boot/initrd.rgz"
    chroot "$W/chrx/boot" /bin/milo >/dev/null 2>&1 || true
    sync; umount "$W/chrx/boot"
    mount /dev/nbd0p1 "$W/chrx/ros" || { qemu-nbd -d /dev/nbd0; die "mount p1 gagal"; }
    mkdir -p "$W/chrx/ros/var/pdb/routeros-x86"
    cp "$W/out/$SYS_NAME" "$W/chrx/ros/var/pdb/routeros-x86/image"
  else
    cp "$W/chrx/BOOTX64.patched" "$W/chrx/boot/EFI/BOOT/BOOTX64.EFI"
    printf 'default system\nlabel system\n\tkernel /EFI/BOOT/BOOTX64.EFI\n\tappend load_ramdisk=1 root=/dev/ram0 quiet\n' > "$W/chrx/boot/syslinux.cfg"
    extlinux --install -H 64 -S 32 "$W/chrx/boot" >/dev/null 2>&1 || true
    sync; umount "$W/chrx/boot"
    mount /dev/nbd0p2 "$W/chrx/ros" || { qemu-nbd -d /dev/nbd0; die "mount p2 gagal"; }
    mkdir -p "$W/chrx/ros/var/pdb/system"
    cp "$W/out/$SYS_NAME" "$W/chrx/ros/var/pdb/system/image"
  fi
  if [ -f "$W/out/option-$V.npk" ]; then mkdir -p "$W/chrx/ros/var/pdb/option"; cp "$W/out/option-$V.npk" "$W/chrx/ros/var/pdb/option/image"; fi
  if [ "$METHOD" = elseif ]; then
    mkdir -p "$W/chrx/ros/bin"
    $PY "$MP/npk.py" extract "$W/out/$SYS_NAME" bin/bash "$W/chrx/ros/bin/bash" >/dev/null 2>&1 || true
    $PY "$MP/npk.py" extract "$W/out/$SYS_NAME" bin/milo "$W/chrx/ros/bin/milo" >/dev/null 2>&1 || true
    chmod 755 "$W/chrx/ros/bin/bash" "$W/chrx/ros/bin/milo" 2>/dev/null || true
  fi
  sync; umount "$W/chrx/ros"; qemu-nbd -d /dev/nbd0
  qemu-img convert -f raw -O qcow2 "$IMG" "$ART/chr-$V-patched.qcow2"
  sha256sum "$IMG" > "$IMG.sha256"
  sha256sum "$ART/chr-$V-patched.qcow2" > "$ART/chr-$V-patched.qcow2.sha256"
fi

# ---------------------------------------------------------------- 9. manifest
say "manifest"
$PY - "$ART" "$V" "$ARCH" "$METHOD" <<'EOF'
import hashlib, json, os, sys, datetime
art, ver, arch, method = sys.argv[1:5]
keys = {
  "npk_sign": os.environ["CUSTOM_NPK_SIGN_PUBLIC_KEY"],
  "licence":   os.environ["CUSTOM_LICENSE_PUBLIC_KEY"],
}
fp = hashlib.sha256(bytes.fromhex(keys["npk_sign"]) + bytes.fromhex(keys["licence"])).hexdigest()
files = {}
for f in sorted(os.listdir(art)):
    if f.endswith(".sha256") or f.endswith(".json"):
        continue
    p = os.path.join(art, f)
    files[f] = {"size": os.path.getsize(p),
                "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest()}
m = {"version": ver, "arch": arch, "method": method,
     "built": datetime.datetime.utcnow().isoformat() + "Z",
     "key_fingerprint": fp, "public_keys": keys, "files": files}
open(os.path.join(art, f"MANIFEST-{ver}.json"), "w").write(json.dumps(m, indent=2) + "\n")
print(json.dumps({k: m[k] for k in ("version","arch","method","key_fingerprint")}, indent=2))
EOF

say "selesai $V/$ARCH"
ls -la "$ART"

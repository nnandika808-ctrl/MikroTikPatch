#!/usr/bin/env python3
"""patch_sys.py <meth-dir> <npk-in> <npk-out> <ver>

Satu lintasan untuk paket sistem: kernel/EFI + squashfs + loader/wrapper +
banner, lalu repack SEKALI dan sign. Menggantikan pola patch.py lalu
ekstrak-repack ulang, yang membuat paket sistem di-repack dua kali.
"""
import os
import subprocess
import sys
import tempfile

METH, SRC, OUT, VER = sys.argv[1:5]
sys.path.insert(0, METH)
import patch as P                                    # noqa: E402
from npk import NovaPackage, NpkPartID, NpkFileContainer  # noqa: E402

MTP = "/root/mtp"
KEYS = {
    bytes.fromhex(os.environ["MIKRO_LICENSE_PUBLIC_KEY"]): bytes.fromhex(os.environ["CUSTOM_LICENSE_PUBLIC_KEY"]),
    bytes.fromhex(os.environ["MIKRO_NPK_SIGN_PUBLIC_KEY"]): bytes.fromhex(os.environ["CUSTOM_NPK_SIGN_PUBLIC_KEY"]),
}

npk = NovaPackage.load(SRC)
pkg = npk if not npk._packages else npk._packages[0]

# 1. kernel / EFI di dalam container
fc = NpkFileContainer.unserialize_from(pkg[NpkPartID.FILE_CONTAINER].data)
for item in fc:
    if item.name in (b"boot/EFI/BOOT/BOOTX64.EFI", b"boot/kernel", b"boot/initrd.rgz"):
        print(f"patch container {item.name.decode()}")
        item.data = P.patch_kernel(item.data, KEYS)
pkg[NpkPartID.FILE_CONTAINER].data = fc.serialize()

# 2. squashfs: key + URL, sekali ekstrak
tmp = tempfile.mkdtemp()
sfs = os.path.join(tmp, "sq.sfs")
root = os.path.join(tmp, "root")
with open(sfs, "wb") as f:
    f.write(pkg[NpkPartID.SQUASHFS].data)
subprocess.run(["unsquashfs", "-d", root, sfs], check=True, capture_output=True)
P.patch_squashfs(root, KEYS)

# 3. loader + mode/mode2 + banner, sebelum repack
B = os.path.join(root, "nova/bin")
for f in ("mode", "keyman"):
    if os.path.exists(os.path.join(B, f + "_")):
        os.replace(os.path.join(B, f + "_"), os.path.join(B, f))
if os.path.exists(os.path.join(B, "mode")):
    os.replace(os.path.join(B, "mode"), os.path.join(B, "mode2"))
    subprocess.run(["cp", f"{MTP}/assets/mode-els-static-7.25.1", os.path.join(B, "mode")], check=True)
    subprocess.run(["cp", f"{MTP}/assets/loader-7.25.1.ref", os.path.join(B, "loader")], check=True)
    if os.environ.get("PATCH_GUARD", "0") == "1":
        subprocess.run([sys.executable, f"{MTP}/patch_loader_guard.py",
                        os.path.join(B, "loader"), os.path.join(B, "loader.n"),
                        os.environ["CUSTOM_LICENSE_PUBLIC_KEY"]], check=True, capture_output=True)
        os.replace(os.path.join(B, "loader.n"), os.path.join(B, "loader"))
for f in ("mode", "mode2", "loader", "keyman"):
    p = os.path.join(B, f)
    if os.path.exists(p):
        os.chmod(p, 0o755)
logo = os.path.join(root, "nova/lib/console/logo.txt")
subprocess.run(["cp", f"{MTP}/work/banner-ref/logo-7.25.1.txt", logo], check=True)

# 4. satu repack
subprocess.run(["mksquashfs", root, sfs, "-no-recovery", "-noappend", "-exit-on-error",
                "-quiet", "-comp", "xz", "-no-xattrs", "-b", "256k", "-all-root"],
               check=True, capture_output=True)
with open(sfs, "rb") as f:
    pkg[NpkPartID.SQUASHFS].data = f.read()

# 5. guard harus cocok dengan mode2 yang dikirim
import struct
ld = open(os.path.join(B, "loader"), "rb").read()
m2 = open(os.path.join(B, "mode2"), "rb").read()
off, ok = 0x153E4, 0
for _ in range(8):
    o, ln = struct.unpack_from("<IB", ld, off)
    off += 5
    ok += ld[off:off + ln] == m2[o:o + ln]
    off += ln
print(f"guard {ok}/8")
if ok != 8:
    sys.exit("guard tidak cocok")

npk.sign(bytes.fromhex(os.environ["CUSTOM_LICENSE_PRIVATE_KEY"]),
         bytes.fromhex(os.environ["CUSTOM_NPK_SIGN_PRIVATE_KEY"]))
npk.save(OUT)
print("ok")

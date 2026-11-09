#!/usr/bin/env python3
"""Patch initrd.rgz v6 (xz): timpa key npk stok di dalam initramfs."""
import lzma
import os
import sys

sys.path.insert(0, os.environ["MP"])
from patch import replace_key  # noqa: E402

kd = {
    bytes.fromhex(os.environ["MIKRO_LICENSE_PUBLIC_KEY"]): bytes.fromhex(os.environ["CUSTOM_LICENSE_PUBLIC_KEY"]),
    bytes.fromhex(os.environ["MIKRO_NPK_SIGN_PUBLIC_KEY"]): bytes.fromhex(os.environ["CUSTOM_NPK_SIGN_PUBLIC_KEY"]),
}
src, dst = sys.argv[1], sys.argv[2]
raw = open(src, "rb").read()
data = lzma.decompress(raw)
new = data
for old_key, new_key in kd.items():
    new = replace_key(old_key, new_key, new, "initrd")
if new == data:
    print("initrd v6 tanpa key stok -> disalin apa adanya")
    open(dst, "wb").write(raw)
    sys.exit(0)

preset = 6
while True:
    out = lzma.compress(new, check=lzma.CHECK_CRC32,
                        filters=[{"id": lzma.FILTER_LZMA2, "preset": preset | lzma.PRESET_EXTREME}])
    preset += 1
    if len(out) <= len(raw) or preset > 9:
        break
assert len(out) <= len(raw), f"initrd baru terlalu besar ({len(out)} > {len(raw)})"
open(dst, "wb").write(out.ljust(len(raw), b"\x00"))
print(f"initrd v6 dipatch: {len(raw)} B (tetap)")

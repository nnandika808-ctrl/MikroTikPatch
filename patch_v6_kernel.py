#!/usr/bin/env python3
"""Patch kernel bzImage v6: offset setup-header klasik (0x248/0x24C), bukan PE (414/584)."""
import lzma
import os
import struct
import sys

sys.path.insert(0, os.environ["MP"])
from patch import replace_key  # noqa: E402

kd = {
    bytes.fromhex(os.environ["MIKRO_LICENSE_PUBLIC_KEY"]): bytes.fromhex(os.environ["CUSTOM_LICENSE_PUBLIC_KEY"]),
    bytes.fromhex(os.environ["MIKRO_NPK_SIGN_PUBLIC_KEY"]): bytes.fromhex(os.environ["CUSTOM_NPK_SIGN_PUBLIC_KEY"]),
}
src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
assert data[0x202:0x206] == b"HdrS", "bukan bzImage (HdrS tidak ada)"

setup_size = (data[0x1F1] + 1) * 512
payload_offset = struct.unpack_from("<I", data, 0x248)[0]
payload_length = struct.unpack_from("<I", data, 0x24C)[0]
start = setup_size + payload_offset
assert data[start:start + 6] == b"\xfd7zXZ\x00", "payload bukan xz"

z_output_len = struct.unpack_from("<I", data, start + payload_length - 4)[0]
vmlinux = lzma.decompress(data[start:start + payload_length - 4])
assert len(vmlinux) == z_output_len, "ukuran vmlinux tidak cocok"

CPIO_MAGIC = b"07070100"
CPIO_FOOTER = b"TRAILER!!!\x00\x00\x00\x00"
i1 = vmlinux.index(CPIO_MAGIC)
i2 = vmlinux.index(CPIO_FOOTER) + len(CPIO_FOOTER)
initramfs = vmlinux[i1:i2]

new_initramfs = initramfs
for old_key, new_key in kd.items():
    new_initramfs = replace_key(old_key, new_key, new_initramfs, "initramfs")
if new_initramfs == initramfs:
    print("initramfs v6 tanpa key stok -> kernel disalin apa adanya")
    open(dst, "wb").write(data)
    sys.exit(0)

new_vmlinux = vmlinux.replace(initramfs, new_initramfs)
new_xz = lzma.compress(new_vmlinux, check=lzma.CHECK_CRC32, filters=[
    {"id": lzma.FILTER_X86},
    {"id": lzma.FILTER_LZMA2, "preset": 9 | lzma.PRESET_EXTREME,
     "dict_size": 32 * 1024 * 1024, "lc": 4, "lp": 0, "pb": 0},
])
assert len(new_xz) <= payload_length - 4, f"payload baru terlalu besar ({len(new_xz)} > {payload_length - 4})"

old_region = data[start:start + payload_length]
new_region = (new_xz + struct.pack("<I", z_output_len)).ljust(len(old_region), b"\x00")

out = bytearray(data)
struct.pack_into("<I", out, 0x24C, len(new_xz) + 4)
out[start:start + len(old_region)] = new_region
open(dst, "wb").write(out)
print(f"kernel v6 dipatch: {len(data)} -> {len(out)} B (payload {len(new_xz)})")

#!/usr/bin/env python3
"""ganti_url.py <binary> <old_url> <new_url>
Ganti kemunculan byte-old_url dengan new_url (harus len(new)<=len(old)),
sisa byte diisi NUL agar tidak ada sisa string lama. Verifikasi sebelum & sesudah.
"""
import sys

old = sys.argv[2].encode()
new = sys.argv[3].encode()
assert len(new) <= len(old), f"new ({len(new)}) lebih panjang dari old ({len(old)})"
path = sys.argv[1]
data = open(path, "rb").read()
n = data.count(old)
print(f"{path}: {n} kemunculan '{sys.argv[2]}'")
if n == 0:
    sys.exit(1)
data = data.replace(old, new + b"\x00" * (len(old) - len(new)))
open(path, "wb").write(data)
# verifikasi
d2 = open(path, "rb").read()
print("  setelah:", d2.count(new), "kemunculan baru; sisa old:", d2.count(old))
assert d2.count(old) == 0

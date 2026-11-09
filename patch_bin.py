#!/usr/bin/env python3
"""Apply replace_key() to one binary: patch_bin.py <file> <method-dir>

Used for binaries patch.py leaves alone (notably nova/bin/loader on the
madskid path, where patch_loader is commented out). Exits non-zero when no
stock key was found, so a silent no-op fails the build.
"""
import os
import sys

sys.path.insert(0, sys.argv[2])
import patch as P  # noqa: E402

path = sys.argv[1]
data = open(path, "rb").read()
key_dict = {
    bytes.fromhex(os.environ["MIKRO_LICENSE_PUBLIC_KEY"]): bytes.fromhex(os.environ["CUSTOM_LICENSE_PUBLIC_KEY"]),
    bytes.fromhex(os.environ["MIKRO_NPK_SIGN_PUBLIC_KEY"]): bytes.fromhex(os.environ["CUSTOM_NPK_SIGN_PUBLIC_KEY"]),
}
hits = 0
for old, new in key_dict.items():
    new_data = P.replace_key(old, new, data, path)
    if new_data != data:
        hits += 1
        data = new_data
if not hits:
    print(f"NO STOCK KEY in {path}")
    sys.exit(1)
open(path, "wb").write(data)
print(f"patched {path} ({hits} key type)")

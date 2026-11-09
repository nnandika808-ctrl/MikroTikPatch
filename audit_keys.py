#!/usr/bin/env python3
"""Audit: does a stock MikroTik public key survive in a patched tree?

MikroTik does not store public keys contiguously. patch.py (madskid/elseif)
rewrites them in three scrambled encodings, so a naive `key in data` search
finds *nothing* — neither stock nor replacement — and looks like a clean tree.

This script rebuilds the same three encodings from replace_key() and reports:
  STOCK  a stock-key encoding still present  -> fail
  OURS   our-key encoding present            -> expected in patched binaries

Usage: audit_keys.py <dir> [--expect-ours]
Exit 1 if any STOCK hit (or if --expect-ours and a file with OURS is missing).
"""
import os
import re
import sys

KEY_MAP = [28, 19, 25, 16, 14, 3, 24, 15, 22, 8, 6, 17, 11, 7, 9, 23,
           18, 13, 10, 0, 26, 21, 2, 5, 20, 30, 31, 4, 27, 29, 1, 12]
CHUNK_MAP = [0, 1, 2, 3, 4, 6, 5, 7]


def patterns(key: bytes):
    """The three encodings replace_key() writes, as regexes."""
    out = []
    # 1) 4-byte chunks, <=8 arbitrary bytes between (gap_size default 8)
    out.append(_pat([key[i:i + 4] for i in range(0, 32, 4)], 8))
    # 2) single bytes permuted by KEY_MAP, gap 8
    out.append(_pat([bytes([key[i]]) for i in KEY_MAP], 8))
    # 3) 4-byte chunks permuted by CHUNK_MAP, gap 20
    chunks = [key[i:i + 4] for i in range(0, 32, 4)]
    out.append(_pat([chunks[i] for i in CHUNK_MAP], 20))
    return [re.compile(p, re.DOTALL) for p in out]


def _pat(chunks, gap):
    parts = [re.escape(c) + b"(.{0,%d})" % gap for c in chunks[:-1]]
    parts.append(re.escape(chunks[-1]))
    return b"".join(parts)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    expect_ours = "--expect-ours" in sys.argv
    if len(args) != 1:
        print(__doc__)
        return 2
    stock_hex = [os.environ.get("MIKRO_LICENSE_PUBLIC_KEY", ""),
                 os.environ.get("MIKRO_NPK_SIGN_PUBLIC_KEY", "")]
    ours_hex = [os.environ.get("CUSTOM_LICENSE_PUBLIC_KEY", ""),
                os.environ.get("CUSTOM_NPK_SIGN_PUBLIC_KEY", "")]
    if not all(stock_hex):
        print("set MIKRO_*_PUBLIC_KEY first")
        return 2
    stock = [(name, patterns(bytes.fromhex(k))) for name, k in
             zip(("license", "npk-sign"), stock_hex)]
    ours = [(name, patterns(bytes.fromhex(k))) for name, k in
            zip(("license", "npk-sign"), ours_hex) if k]

    files = stock_hits = ours_files = 0
    for root, _dirs, names in os.walk(args[0]):
        for name in names:
            path = os.path.join(root, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            try:
                data = open(path, "rb").read()
            except OSError:
                continue
            files += 1
            for tag, pats in stock:
                n = sum(len(p.findall(data)) for p in pats)
                if n:
                    stock_hits += 1
                    print(f"STOCK  {tag:<8} x{n}  {path}")
            if any(p.search(data) for _, pats in ours for p in pats):
                ours_files += 1

    print(f"\nfiles={files} stock_key_files={stock_hits} our_key_files={ours_files}")
    if stock_hits:
        print("FAIL: stock key survives")
        return 1
    if expect_ours and ours_files == 0:
        print("FAIL: our key found in no file")
        return 1
    print("PASS: no stock key encoding present")
    return 0


if __name__ == "__main__":
    sys.exit(main())

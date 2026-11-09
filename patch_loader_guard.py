#!/usr/bin/env python3
"""Point elseif's loader guard at OUR licence key.

The loader carries the expected licence-key dwords in TWO places:
  * the guard table  (records {off:u32 LE, len:u8, bytes}, file 0x153e4)
  * the code that builds the same buffer with `movl $imm32,-0xNN(%ebp)`
    (file ~0x83ac, reached only by the hook)
The historical recipe patched the table only, so the stock key stayed in .text
and any byte audit flagged the loader — while the guard table said "patched".

Both copies hold the key's 4-byte chunks in CHUNK_MAP order and must agree.
Usage:
  patch_loader_guard.py <loader-in> <loader-out> <licence-pubkey-hex>
  patch_loader_guard.py --check <loader> <licence-pubkey-hex>
Locating the code copy needs the key currently in it; set MIKRO_LICENSE_PUBLIC_KEY
(stock) and/or CUSTOM_LICENSE_PUBLIC_KEY so both can be tried.
Exit 0 = every copy holds the key, 1 = mismatch/missing.
"""
import os
import re
import sys

CHUNK_MAP = [0, 1, 2, 3, 4, 6, 5, 7]
TABLE_OFF = 0x153E4
N_REC = 8


def ordered(key: bytes) -> list:
    ch = [key[i:i + 4] for i in range(0, 32, 4)]
    return [ch[i] for i in CHUNK_MAP]


def pattern(chunks: list, gap: int = 20) -> bytes:
    parts = [re.escape(c) + b"(.{0,%d})" % gap for c in chunks[:-1]]
    parts.append(re.escape(chunks[-1]))
    return b"".join(parts)


def table_slots(ld: bytes):
    """(byte_offset, old4) for the 8 guard records."""
    out, off = [], TABLE_OFF
    for _ in range(N_REC):
        ln = ld[off + 4]
        out.append((off + 5, bytes(ld[off + 5:off + 5 + ln])))
        off += 5 + ln
    if int.from_bytes(ld[off:off + 4], "little") != 0:
        raise SystemExit("guard table not terminated by zero offset")
    return out


def _imm_ok(ld: bytes, off: int) -> bool:
    # `movl $imm32,-0xNN(%ebp)` is c7 85 dd ff ff ff (imm at +6) or c7 45 dd (imm at +3)
    return bytes(ld[off - 6:off - 4]) == b"\xc7\x85" or bytes(ld[off - 3:off - 1]) == b"\xc7\x45"


def code_slots(ld: bytes, candidates):
    """imm offsets of the 8 `movl $imm32` holding one of the candidate keys."""
    tried = []
    for name, chunks in candidates:
        for m in re.finditer(pattern(chunks), bytes(ld), re.DOTALL):
            if m.end() >= TABLE_OFF:
                continue
            slots = [m.start()] + [m.end(i) for i in range(1, N_REC)]
            if all(_imm_ok(ld, s) for s in slots):
                return slots, name
            tried.append(name)
    raise SystemExit(f"no code copy found (tried: {sorted(set(tried)) or 'none'})")


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--check"]
    check = "--check" in sys.argv
    if len(args) not in (2, 3):
        print(__doc__)
        return 2
    key = bytes.fromhex(args[-1])
    if len(key) != 32:
        raise SystemExit("licence public key must be 32 bytes")
    ld = bytearray(open(args[0], "rb").read())
    want = ordered(key)

    tslots = table_slots(ld)
    cands = []
    for env in ("MIKRO_LICENSE_PUBLIC_KEY", "CUSTOM_LICENSE_PUBLIC_KEY"):
        v = os.environ.get(env, "")
        if v:
            cands.append((env, ordered(bytes.fromhex(v))))
    cands.append(("table", [old for _, old in tslots]))
    cands.append(("target", want))
    try:
        cslots, src = code_slots(ld, cands)
    except SystemExit as e:
        print(f"code copy: {e}")
        cslots, src = [], "-"

    bad = 0
    for idx, (toff, _old) in enumerate(tslots):
        ok = bytes(ld[toff:toff + 4]) == want[idx]
        if not check:
            ld[toff:toff + 4] = want[idx]
        bad += not ok
        print(f"table rec{idx} @0x{toff:x} {'OK' if ok else 'STALE'}")
    for idx, coff in enumerate(cslots):
        ok = bytes(ld[coff:coff + 4]) == want[idx]
        if not check:
            ld[coff:coff + 4] = want[idx]
        bad += not ok
        print(f"code imm{idx} @0x{coff:x} {'OK' if ok else 'STALE'}")

    print(f"code copy located via: {src}")
    if check:
        good = bad == 0 and len(cslots) == N_REC
        print("PASS" if good else f"FAIL ({bad} stale)")
        return 0 if good else 1
    open(args[1], "wb").write(bytes(ld))
    print(f"wrote {args[1]} ({len(ld)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

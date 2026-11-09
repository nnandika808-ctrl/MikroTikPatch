#!/usr/bin/env python3
"""Kirim ketikan ke konsol QEMU lewat socket monitor.

Pakai: keys.py <socket> "<teks>"        -> ketik teks lalu Enter
       keys.py <socket> --raw "ret"     -> kirim nama key mentah QEMU
"""
import socket
import sys
import time

MAP = {
    " ": "spc", "/": "slash", ".": "dot", "-": "minus", "_": "shift-minus",
    "=": "equal", ":": "shift-semicolon", ",": "comma", "!": "shift-1",
    "@": "shift-2", "#": "shift-3", "+": "shift-equal", "*": "shift-8",
    '"': "shift-apostrophe",
}


def keyname(ch):
    if ch in MAP:
        return MAP[ch]
    if ch.isalnum():
        return ch.lower()
    raise ValueError(f"tak dikenal: {ch!r}")


def main():
    sock_path = sys.argv[1]
    raw = len(sys.argv) > 3 and sys.argv[2] == "--raw"
    text = sys.argv[3] if raw else sys.argv[2]
    delay = float(sys.argv[4]) if len(sys.argv) > 4 else 0.06

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(sock_path)
    try:
        s.recv(4096)
    except socket.timeout:
        pass

    keys = [text] if raw else [keyname(c) for c in text] + ["ret"]
    for k in keys:
        s.sendall(f"sendkey {k}\n".encode())
        time.sleep(delay)
        try:
            s.recv(4096)
        except socket.timeout:
            pass
    time.sleep(0.5)
    s.close()
    print(f"terkirim: {text!r}")


if __name__ == "__main__":
    main()

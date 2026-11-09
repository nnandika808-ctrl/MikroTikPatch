#!/usr/bin/env python3
"""Klien API RouterOS minimal: ros_api.py <host> <port> <user> <pass> <cmd> [k=v ...]"""
import hashlib
import socket
import sys


def enc_len(n):
    if n < 0x80:
        return bytes([n])
    if n < 0x4000:
        n |= 0x8000
        return n.to_bytes(2, "big")
    if n < 0x200000:
        n |= 0xC00000
        return n.to_bytes(3, "big")
    n |= 0xE0000000
    return n.to_bytes(4, "big")


def enc_word(w):
    b = w.encode()
    return enc_len(len(b)) + b


def sentence(words):
    return b"".join(enc_word(w) for w in words) + b"\x00"


def read_len(sock):
    b = sock.recv(1)
    if not b:
        raise EOFError
    n = b[0]
    if n < 0x80:
        return n
    if n < 0xC0:
        return ((n & 0x3F) << 8) + sock.recv(1)[0]
    if n < 0xE0:
        r = sock.recv(2)
        return ((n & 0x1F) << 16) + (r[0] << 8) + r[1]
    r = sock.recv(3)
    return ((n & 0x0F) << 24) + (r[0] << 16) + (r[1] << 8) + r[2]


def read_sentence(sock):
    words = []
    while True:
        n = read_len(sock)
        if n == 0:
            return words
        words.append(sock.recv(n).decode(errors="replace"))


def main():
    host, port, user, pw, cmd = sys.argv[1:6]
    args = sys.argv[6:]
    s = socket.create_connection((host, int(port)), timeout=20)
    s.sendall(sentence(["/login", f"=name={user}", f"=password={pw}"]))
    resp = read_sentence(s)
    if "=ret" in resp:
        tok = [w for w in resp if w.startswith("=ret=")][0][5:]
        chal = hashlib.md5(("\x00" + pw + tok).encode()).hexdigest()
        s.sendall(sentence(["/login", f"=name={user}", f"=response=00{chal}"]))
        read_sentence(s)
    s.sendall(sentence([cmd] + [a if a.startswith("=") else f"={a}" for a in args]))
    while True:
        words = read_sentence(s)
        if not words:
            break
        print(" ".join(words))
        if "!done" in words or "!trap" in words:
            break
    s.close()


if __name__ == "__main__":
    main()

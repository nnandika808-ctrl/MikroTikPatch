#!/usr/bin/env python3
"""Pasang lisensi RouterOS jarak jauh tanpa /system/shell.

Jalan: SSH (bila box punya ssh + pass kosong) ATAU HTTP fetch (bila box punya
akses internet). Dipakai bot Telegram /apply <host> <port> <x86|chr> [user].

Kunci ditaruh di /rw/disk/<id-dash>.key lalu keyman --find-key dipanggil via
scheduler startup (berlaku untuk 7.24.5 & 7.23.7 yang tidak punya /system/import).
"""
import os
import subprocess
import sys

MTP = "/root/mtp"
PY = "/usr/bin/python3.12"


def ssh(host, port, user, cmd, timeout=60):
    full = ["sshpass", "-p", "", "ssh", "-T",
            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=10", "-p", str(port), f"{user}@{host}", cmd]
    r = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
    return r.stdout + r.stderr


def main():
    host, port, kind = sys.argv[1], sys.argv[2], sys.argv[3]
    user = sys.argv[4] if len(sys.argv) > 4 else "admin"

    set_a = ". /root/mtp/keys/env.user && set +a"
    if kind == "chr":
        mode, field = "licgenchr", "system-id"
    else:
        mode, field = "licgenros", "software-id"

    out = ssh(host, port, user, f"/system/license/print")
    ident = ""
    for line in out.splitlines():
        line = line.replace("\r", "")
        if line.strip().startswith(field + ":"):
            ident = line.split(":", 1)[1].strip()
            break
    if not ident:
        print(f"tidak bisa baca {field} dari {host}"); sys.exit(1)

    key = subprocess.run(
        [PY, f"{MTP}/methods/v6/license.py", mode, ident,
         subprocess.run(f"set -a; . {MTP}/keys/env.user; set +a; echo $CUSTOM_LICENSE_PRIVATE_KEY",
                        capture_output=True, text=True, shell=True).stdout.strip()],
        capture_output=True, text=True, timeout=30).stdout

    fid = ident.replace("/", "-")
    content = "\n".join(key.strip().splitlines())
    # tulis lewat pita: scp ke /flash lalu pindahkan (scheduler tak perlu shell)
    tmp = f"/{fid}.key"
    with open("/tmp/_key", "w") as f:
        f.write(content)
    r = subprocess.run(["sshpass", "-p", "", "scp", "-O", "-o", "StrictHostKeyChecking=no",
                        "-o", "UserKnownHostsFile=/dev/null", "-P", str(port),
                        "/tmp/_key", f"{user}@{host}:{tmp}"],
                       capture_output=True, text=True, timeout=40)
    print(f"scp rc={r.returncode}")
    # pindahkan kunci ke /rw/disk (lokasi yang dipindai keyman)
    out = ssh(host, port, user, f'/file copy {fid}.key rw/disk/{fid}.key')
    print("-> copy:", out.strip().replace("\r", " ")[-120:] or "ok")
    # aktifkan tiap boot: scheduler startup (perintah dikirim satu per satu,
    # RouterOS menolak beberapa perintah sekaligus lewat SSH)
    ssh(host, port, user, '/system scheduler remove [find name=lickey]')
    out = ssh(host, port, user,
              '/system scheduler add name=lickey start-time=startup '
              'on-event=":execute {/nova/bin/keyman}"')
    print("-> scheduler:", out.strip().replace("\r", " ")[-120:] or "ok")
    print(ssh(host, port, user, "/system/license/print").replace("\r", ""))


if __name__ == "__main__":
    main()

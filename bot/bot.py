#!/usr/bin/env python3
"""Bot Telegram penerbit lisensi offline RouterOS (x86 / CHR).

Token: /root/mtp/bot/token   (0600, dari @BotFather)
Allowlist: /root/mtp/bot/allow  (satu chat_id per baris; kosong = semua boleh)
Log: /root/mtp/bot/licenses.log (JSONL)

Perintah:
  /start            bantuan
  /chr <system-id>  lisensi CHR (11 karakter)
  /ros <software-id> lisensi RouterOS x86 (format XXXX-XXXX)
  /id               cek format id yang dikirim
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
MTP = "/root/mtp"
PY = "/usr/bin/python3.12"
LICGEN = os.path.join(MTP, "methods", "v6", "license.py")
LOG = os.path.join(BASE, "licenses.log")

ROS_CHARS = set("TN0BYX18S5HZ4IA67DGF3LPCJQRUK9MW2VE")
CHR_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")


def read_file(name, default=""):
    try:
        with open(os.path.join(BASE, name), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return default


TOKEN = read_file("token")
ALLOW = {x.strip() for x in read_file("allow").splitlines() if x.strip()}


def load_env():
    env = {}
    with open(os.path.join(MTP, "keys", "env.user"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("export ") and "=" in line:
                k, v = line[7:].split("=", 1)
                env[k] = v.strip().strip('"')
    return env


ENV = load_env()
PRIV = ENV["CUSTOM_LICENSE_PRIVATE_KEY"]


def api(method, **params):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=70) as r:
        return json.load(r)


def send(chat_id, text, reply_to=None):
    params = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    if reply_to:
        params["reply_to_message_id"] = reply_to
    try:
        api("sendMessage", **params)
    except Exception as e:  # noqa: BLE001
        print(f"send gagal: {e}", file=sys.stderr)


def valid_ros(sid):
    s = sid.replace("-", "")
    return len(sid) == 9 and sid[4] == "-" and all(c in ROS_CHARS for c in s)


def valid_chr(sid):
    return len(sid) == 11 and all(c in CHR_CHARS for c in sid)


def generate(kind, ident):
    mode = "licgenchr" if kind == "chr" else "licgenros"
    import subprocess

    out = subprocess.run(
        [PY, LICGEN, mode, ident, PRIV],
        capture_output=True, text=True, timeout=60,
        cwd=os.path.dirname(LICGEN),
    )
    key = out.stdout.strip()
    if "BEGIN MIKROTIK SOFTWARE KEY" not in key:
        raise RuntimeError(out.stderr.strip() or "gagal membuat kunci")
    return key


def log(chat_id, kind, ident, key):
    rec = {"ts": int(time.time()), "chat": chat_id, "kind": kind, "id": ident,
           "key": key.replace("\n", "|")}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


HELP = (
    "<b>Generator lisensi RouterOS</b>\n\n"
    "Kirim salah satu:\n"
    "<code>/chr 1a2B3c4D5eF</code> — system-id CHR (11 karakter)\n"
    "<code>/ros 04S0-0M99</code> — software-id x86 (format XXXX-XXXX)\n\n"
    "ID CHR: <code>/system/license/print</code> di box CHR.\n"
    "ID x86: <code>/system/license/print</code> (software-id).\n\n"
    "Kunci bersifat offline — pasang dengan "
    "<code>/system/shell cmd=\"/nova/bin/keyman --find-key\"</code> "
    "setelah file ditaruh di <code>/var/pckg/&lt;id&gt;.key</code>."
)


def handle(chat_id, text, msg_id):
    parts = text.strip().split()
    if not parts:
        return
    cmd = parts[0].split("@")[0].lower()

    if cmd in ("/start", "/help"):
        send(chat_id, HELP, msg_id)
        return

    if cmd == "/id":
        ident = parts[1] if len(parts) > 1 else ""
        kind = "chr" if valid_chr(ident) else "ros" if valid_ros(ident) else None
        send(chat_id, f"<code>{ident or '-'}</code>\njenis: <b>{kind or 'tidak dikenali'}</b>", msg_id)
        return

    if cmd not in ("/chr", "/ros"):
        send(chat_id, "Perintah tidak dikenal. " + HELP, msg_id)
        return

    if len(parts) < 2:
        send(chat_id, f"Format: <code>{cmd} &lt;id&gt;</code>", msg_id)
        return

    kind = cmd[1:]
    ident = parts[1]
    if kind == "chr" and not valid_chr(ident):
        send(chat_id, "System-id CHR harus 11 karakter base64.", msg_id)
        return
    if kind == "ros" and not valid_ros(ident):
        send(chat_id, "Software-id harus format <code>XXXX-XXXX</code> dan hanya memakai "
                      "karakter TN0BYX18S5HZ4IA67DGF3LPCJQRUK9MW2VE.", msg_id)
        return

    try:
        key = generate(kind, ident)
    except Exception as e:  # noqa: BLE001
        send(chat_id, f"Gagal: <code>{e}</code>", msg_id)
        return

    log(chat_id, kind, ident, key)
    send(chat_id, f"<b>{kind.upper()} {ident}</b>\n<pre>{key}</pre>", msg_id)


def main():
    if not TOKEN:
        sys.exit("token kosong: taruh token BotFather di /root/mtp/bot/token")
    offset = 0
    print("bot jalan", flush=True)
    while True:
        try:
            res = api("getUpdates", offset=offset, timeout=50,
                      allowed_updates=json.dumps(["message"]))
        except Exception as e:  # noqa: BLE001
            print(f"poll gagal: {e}", file=sys.stderr)
            time.sleep(5)
            continue
        for upd in res.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or {}
            chat = msg.get("chat", {})
            chat_id = chat.get("id")
            text = msg.get("text", "")
            if not chat_id or not text:
                continue
            if ALLOW and str(chat_id) not in ALLOW:
                send(chat_id, "Belum diizinkan. chat_id kamu: "
                              f"<code>{chat_id}</code>", msg.get("message_id"))
                continue
            try:
                handle(chat_id, text, msg.get("message_id"))
            except Exception as e:  # noqa: BLE001
                print(f"handler gagal: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()

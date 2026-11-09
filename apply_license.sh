#!/bin/bash
# apply_license.sh <host> <port> <x86|chr> [user]
# Terbitkan lisensi offline untuk satu box lalu pasang lewat keyman --find-key.
# Syarat: ssh ke box aktif, /var/pckg bisa dibuat, keypair ada di keys/env.user.
set -euo pipefail

HOST="${1:?host}"; PORT="${2:?port}"; KIND="${3:?x86|chr}"; USER="${4:-admin}"
MTP=/root/mtp
PY=/usr/bin/python3.12
SSH=(sshpass -p '' ssh -T -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p "$PORT" "$USER@$HOST")

set -a; . "$MTP/keys/env.user"; set +a

case "$KIND" in
  chr) MODE=licgenchr ;;
  x86) MODE=licgenros ;;
  *) echo "kind harus x86 atau chr"; exit 2 ;;
esac

ID=$("${SSH[@]}" "/system/license/print" | sed 's/\r//' | awk -F': ' "/$([ "$KIND" = chr ] && echo system-id || echo software-id)/{gsub(/ /,\"\",\$2); print \$2}")
[ -n "$ID" ] || { echo "tidak bisa membaca id dari box"; exit 1; }
echo "id=$ID"

KEY=$("$PY" "$MTP/methods/v6/license.py" "$MODE" "$ID" "$CUSTOM_LICENSE_PRIVATE_KEY" 2>/dev/null)
[ -n "$KEY" ] || { echo "gagal membuat kunci"; exit 1; }

# tulis kunci ke /rw/disk lalu salin ke /var/pckg/<id>.key
CONTENT=$(printf '%s' "$KEY" | awk 'NR==1{a=$0} NR==2{b=$0} NR==3{c=$0} END{printf "%s\\n%s\\n%s", a,b,c}')
"${SSH[@]}" "/file/remove key.tmp; /file/add name=key.tmp contents=\"$CONTENT\"" >/dev/null
"${SSH[@]}" "/system/shell cmd=\"/pckg/option/bin/busybox mkdir -p /var/pckg; /pckg/option/bin/busybox cp /rw/disk/key.tmp /var/pckg/$ID.key; /nova/bin/keyman --find-key\"" | sed 's/\r//'
"${SSH[@]}" "/file/remove key.tmp" >/dev/null

"${SSH[@]}" "/system/license/print" | sed 's/\r//'

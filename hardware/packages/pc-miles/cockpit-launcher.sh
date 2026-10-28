#!/usr/bin/env bash
# Lancer le cockpit web local (8787) — paquet pc-miles.
# Rien n'est exposé hors 127.0.0.1.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 -m http.server 8787 --bind 127.0.0.1 --directory ./cockpit

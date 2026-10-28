#!/usr/bin/env bash
# Lancer le cockpit web local (127.0.0.1:8787) — paquet pc-miles.
#
# Le cockpit n'est pas un dossier statique du paquet : c'est `assets/web`,
# servi par le serveur Companion du dépôt sous `/cockpit/` (DEC-015 : une
# seule implémentation, une seule source de vérité). Servir un `./cockpit`
# local reviendrait à publier une copie non authentifiée.
#
# Rien n'est exposé hors de 127.0.0.1 : le serveur refuse toute autre adresse.
set -euo pipefail

MILES_DIR="${MILES_DIR:-/opt/Milescorp}"

if [ ! -f "$MILES_DIR/app/interface/companion/server.py" ]; then
    echo "ERREUR : dépôt MILES introuvable dans $MILES_DIR" >&2
    echo "Renseignez MILES_DIR ou lancez install.sh d'abord." >&2
    exit 1
fi

PYTHON="$MILES_DIR/.venv/bin/python3"
if [ ! -x "$PYTHON" ]; then
    PYTHON="$(command -v python3 || true)"
fi
if [ -z "$PYTHON" ]; then
    echo "ERREUR : python3 introuvable." >&2
    exit 1
fi

cd "$MILES_DIR"
exec "$PYTHON" app/interface/companion/server.py --port 8787 --host 127.0.0.1

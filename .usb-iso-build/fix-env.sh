#!/usr/bin/env bash
ROOTFS="/root/live-rootfs"
ENVF="$ROOTFS/opt/Milescorp/.env"
echo "=== cles du .env (valeurs masquees si sensibles) ==="
while IFS='=' read -r k v; do
  case "$k" in
    ''|\#*) continue ;;
  esac
  kl=$(printf '%s' "$k" | tr '[:upper:]' '[:lower:]')
  case "$kl" in
    *key*|*token*|*secret*|*pass*|*password*) echo "  $k=<masqué>" ;;
    *) echo "  $k=$v" ;;
  esac
done < "$ENVF"

echo "=== valeurs acceptees par miles.py ==="
grep -rn "remote\|local" "$ROOTFS/opt/Milescorp/miles.py" | grep -i "fournisseur\|provider" | head -5
grep -rn "Fournisseur inconnu" "$ROOTFS/opt/Milescorp"/*.py 2>/dev/null | head -3

echo "=== correction MILES_PROVIDER ==="
sed -i 's/^MILES_PROVIDER=.*/MILES_PROVIDER=local/' "$ENVF"
grep "^MILES_PROVIDER" "$ENVF"

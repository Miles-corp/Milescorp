#!/usr/bin/env bash
# MILES — fabrique l'ISO d'installation AUTOMATIQUE Debian 13 + provision MILES.
#
# À lancer SOUS WSL (Ubuntu) depuis le dépôt :
#   bash hardware/packages/usb-installer/build-iso.sh
#
# Ce que fait ce script :
#   1. télécharge l'ISO netinst Debian 13 officielle (si absente) ;
#   2. VÉRIFIE son SHA256 contre le fichier officiel SHA256SUMS ;
#   3. te demande root/user mot de passe (hash SHA-512 sur place, JAMAIS
#      écrit en clair ni commité) ;
#   4. construit la payload source MILES (sans .git, .env, données, vidéos) ;
#   5. injecte preseed.cfg dans l'initrd + /files (payload, provision) ;
#   6. coupe les délais des menus de démarrage (BIOS + UEFI) ;
#   7. regénère l'ISO hybride dans releases/ + SHA256SUMS.
#
# Sécurité : aucun secret dans l'ISO (clé API MILES = saisie après, --setup).
set -euo pipefail

# ---------------------------------------------------------------- CONFIG
DEBIAN_DIR="${DEBIAN_DIR:-https://cdimage.debian.org/debian-cd/current/amd64/iso-cd}"
NETINST_PATTERN='debian-[0-9.]+-amd64-netinst\.iso'
WORK="${WORK:-$PWD/.usb-iso-build}"
OUTDIR="$PWD/releases"
ISA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$ISA_DIR/../../.." && pwd)"

command -v xorriso  >/dev/null 2>&1 || { echo "ERREUR : xorriso absent. sudo apt install xorriso"; exit 1; }
command -v cpio     >/dev/null 2>&1 || { echo "ERREUR : cpio absent. sudo apt install cpio"; exit 1; }
command -v curl     >/dev/null 2>&1 || { echo "ERREUR : curl absent."; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "ERREUR : sha256sum absent."; exit 1; }
command -v openssl  >/dev/null 2>&1 || { echo "ERREUR : openssl absent (hash des mots de passe)."; exit 1; }
command -v tar      >/dev/null 2>&1 || { echo "ERREUR : tar absent."; exit 1; }

mkdir -p "$WORK" "$OUTDIR"

# ------------------------------------------------- 1-2. ISO + VÉRIFICATION
echo "=== 1/6 — Recuperation de l'ISO Debian 13 officielle ==="
( cd "$WORK"
  if [ ! -f SHA256SUMS ]; then
    echo "Telechargement de SHA256SUMS ..."
    curl -fsSL -o SHA256SUMS.tmp "$DEBIAN_DIR/SHA256SUMS"
    mv SHA256SUMS.tmp SHA256SUMS
  fi
  ISO_NAME=$(grep -oE "$NETINST_PATTERN" SHA256SUMS | head -n1)
  [ -n "$ISO_NAME" ] || { echo "ERREUR : nom d'ISO introuvable dans SHA256SUMS (miroir change ?)"; exit 1; }
  echo "ISO cible : $ISO_NAME"
  if [ ! -f "$ISO_NAME" ]; then
    echo "Telechargement (~756 Mo, depends de ta connexion) ..."
    curl -fL --progress-bar -o "$ISO_NAME.part" "$DEBIAN_DIR/$ISO_NAME"
    mv "$ISO_NAME.part" "$ISO_NAME"
  else
    echo "Deja presente : $ISO_NAME"
  fi
  echo "Verification du SHA256 (obligatoire) ..."
  if grep " $ISO_NAME\$" SHA256SUMS | sha256sum -c -; then
    echo "SHA256 : OK"
  else
    echo "ERREUR : SHA256 NON CONFORME — ISO refusee, suppression."
    rm -f "$ISO_NAME"; exit 1
  fi
)
ISO="$(ls -1 "$WORK"/debian-*-amd64-netinst.iso | head -n1)"

# ------------------------------------------------- 3. MOTS DE PASSES (interactif)
echo
echo "=== 2/6 — Mots de passe de l'installation ==="
echo "Ils sont hashes en SHA-512 puis ECRITS UNIQUEMENT dans le preseed genere"
echo "(dossier temporaire de build, jamais dans Git). Root n'aura PAS de login."
if [ -n "${MILES_USER_HASH:-}" ] && [ -n "${MILES_ROOT_HASH:-}" ]; then
    # Mode non-interactif : les hashes sont fournis par l'environnement
    # (jamais de mot de passe en clair dans la commande / les journaux).
    USER_HASH="$MILES_USER_HASH"
    ROOT_HASH="$MILES_ROOT_HASH"
    echo "Hashes fournis via MILES_USER_HASH / MILES_ROOT_HASH (mode automatique)."
else
    while true; do
        read -r -s -p "Mot de passe du compte 'miles' : " UPW; echo
        read -r -s -p "Confirmation                       : " UPW2; echo
        [ "$UPW" = "$UPW2" ] && [ -n "$UPW" ] && break
        echo "Les mots de passe ne correspondent pas (ou sont vides). Recommence."
    done
    if [ "${MILES_SAME_PASSWORD:-0}" = "1" ]; then
        RPW="$UPW"
    else
        read -r -s -p "Mot de passe de secours root (admin hors connexion, jamais expose) : " RPW; echo
    fi
    USER_HASH="$(printf '%s' "$UPW" | openssl passwd -6 -salt miles1 2>/dev/null)"
    ROOT_HASH="$(printf '%s' "$RPW" | openssl passwd -6 -salt miles2 2>/dev/null)"
    unset UPW UPW2 RPW
    [ -n "$USER_HASH" ] && [ -n "$ROOT_HASH" ] || { echo "ERREUR : hashage impossible (openssl)."; exit 1; }
fi
case "$USER_HASH$ROOT_HASH" in
    *'$6$'*) : ;;
    *) echo "ERREUR : les hashes fournis ne sont pas des SHA-512 crypt (\$6\$)."; exit 1 ;;
esac
echo "Hashes SHA-512 presents."

# ------------------------------------------------- 4. PAYLOAD SOURCE MILES
echo "=== 3/6 — Construction de la payload MILES ==="
PAYLOAD="$WORK/miles-source.tar.gz"
LISTE="$WORK/payload-files.txt"
# Une LISTE de fichiers (et non un tar lancé sur le dépôt) : le dossier de
# build contient l'ISO de 792 Mo et vit DANS le dépôt — un exclude mal
# apparié l'aurait archivée dans la payload (run precedent : blocage).
( cd "$REPO_ROOT"
  find . \
    \( -path './.git' -o -path './.usb-iso-build' -o -path './data' \
       -o -path './logs' -o -path './releases' -o -path './experiments' \
       -o -path './docs/marketing' -o -path './brag-output-*' \
       -o -path '*/__pycache__' -o -path '*/.venv' -o -path '*/node_modules' \) \
    -prune -o -type f \
    ! -name '*.pyc' ! -name '*.mp4' ! -name '*.wav' ! -name '*.mkv' \
    -print | sed 's|^\./||' > "$LISTE"
)
# Filtres de secrets : .env reels, cles, JSON de config reel (les .example
# restent, ils sont voulus dans la payload).
grep -vE '(^|/)(\.env$|\.env\.(local|prod|production|dev|test|backup|bak|old)$|auth\.json$|[^/]+\.pem$|[^/]+\.key$|config/config\.json$)' \
    "$LISTE" > "$LISTE.f"
grep -E '(^|/)(\.env\.example|config\.json\.example)$' "$LISTE" >> "$LISTE.f" 2>/dev/null || true
sort -u "$LISTE.f" > "$LISTE"
rm -f "$LISTE.f"

# Garde-fous avant archivage.
if grep -qE '(^|/)(\.env$|auth\.json$)' "$LISTE" \
   || grep -qE 'docs/marketing|brag-output|\.usb-iso-build|^\.git/' "$LISTE"; then
    echo "ERREUR : la liste de la payload contient un element interdit :"
    grep -E '(^|/)(\.env$|auth\.json$)|docs/marketing|brag-output|\.usb-iso-build' "$LISTE" | head -5
    exit 1
fi
NB_FILES=$(wc -l < "$LISTE")
echo "Fichiers retenus : $NB_FILES"
[ "$NB_FILES" -ge 100 ] || { echo "ERREUR : liste anormalement courte ($NB_FILES)."; exit 1; }

tar -czf "$PAYLOAD" -C "$REPO_ROOT" -T "$LISTE"
[ -s "$PAYLOAD" ] || { echo "ERREUR : payload vide ($PAYLOAD)."; exit 1; }
TAILLE_PAYLOAD=$(stat -c%s "$PAYLOAD")
if [ "$TAILLE_PAYLOAD" -gt 41943040 ]; then   # 40 Mo max : anomalie evidente
    echo "ERREUR : payload de $((TAILLE_PAYLOAD / 1024 / 1024)) Mo (attendu < 40 Mo)."
    exit 1
fi
echo "Payload : $((TAILLE_PAYLOAD / 1024)) Ko ($PAYLOAD)"

# ------------------------------------------------- 5. PRESEED INSTANCIÉ
echo "=== 4/6 — Generation du preseed ==="
PRESED="$WORK/preseed.cfg"
sed -e "s|@@MILES_USER_HASH@@|$USER_HASH|" \
    -e "s|@@MILES_ROOT_HASH@@|$ROOT_HASH|" \
    "$ISA_DIR/preseed.cfg" > "$PRESED"
if grep -qE '@@MILES_(USER|ROOT)_HASH@@' "$PRESED"; then
    echo "ERREUR : jeton de hash non remplace dans le preseed."
    exit 1
fi
echo "Preseed genere (hashes substitutes)."

mkdir -p "$WORK/files"
cp "$PAYLOAD"                       "$WORK/files/miles-source.tar.gz"
cp "$ISA_DIR/miles-provision.sh"     "$WORK/files/miles-provision.sh"
cp "$ISA_DIR/miles-provision.service" "$WORK/files/miles-provision.service"

# ------------------------------------------------- 6. INITRD + MENUS
echo "=== 5/6 — Injection dans l'initrd et coupes des delais ==="
INITRD="$WORK/initrd.gz"
xorriso -osirrox on -indev "$ISO" -extract /install.amd/initrd.gz "$INITRD" 2>/dev/null

mkdir -p "$WORK/initrd"
( cd "$WORK/initrd"
  gzip -dc "$INITRD" > initrd.cpio 2>/dev/null || { echo "ERREUR : initrd non gzip (zstd ?) — verifier la version Debian."; exit 1; }
  cpio -idm --quiet < initrd.cpio
  rm -f initrd.cpio
  cp "$PRESED" ./preseed.cfg
  find . -print0 | cpio -o --null --format=newc --quiet 2>/dev/null | gzip -9 > "$WORK/initrd-new.gz"
)
echo "preseed.cfg injecte dans l'initrd."

# Menus : BIOS (isolinux) + UEFI (grub) → aucune touche a appuyer.
GRUB_ARGS="auto=true priority=critical"

# BIOS : le contenu des menus vit dans PLUSIEURS fichiers inclus
# (isolinux.cfg → menu.cfg → adtxt.cfg / gtk.cfg / ...). On extrait tout
# /isolinux et on reecrit toutes les lignes `append` de TOUS les .cfg.
rm -rf "$WORK/isolinux"
xorriso -osirrox on -indev "$ISO" -extract /isolinux "$WORK/isolinux" 2>/dev/null || true
MAP_ISOLINUX=()
if [ -d "$WORK/isolinux" ]; then
    for CFG in "$WORK/isolinux"/*.cfg; do
        [ -f "$CFG" ] || continue
        AVANT=$(md5sum "$CFG" | cut -d' ' -f1)
        sed -i -E "s/^([[:space:]]*append[[:space:]]+.*)$/\1 $GRUB_ARGS/; s/^timeout .*/timeout 1/; s/^prompt .*/prompt 0/" "$CFG"
        APRES=$(md5sum "$CFG" | cut -d' ' -f1)
        if [ "$AVANT" != "$APRES" ]; then
            MAP_ISOLINUX+=( -map "$CFG" "/isolinux/$(basename "$CFG")" )
        fi
    done
fi

# UEFI : GRUB. Debian n'ecrit AUCUN "set timeout" dans grub.cfg — sans lui
# le menu peut attendre indefiniment : on l'injecte si absent.
xorriso -osirrox on -indev "$ISO" -extract /boot/grub/grub.cfg "$WORK/grub.cfg" 2>/dev/null || true
if [ -f "$WORK/grub.cfg" ]; then
    sed -i -E "s/^(\s*linux(16|efi)?\s.*)$/\1 $GRUB_ARGS/" "$WORK/grub.cfg"
    if grep -q '^set timeout=' "$WORK/grub.cfg"; then
        sed -i -E "s/^set timeout=.*/set timeout=0/; s/^set timeout_style=.*/set timeout_style=hidden/" "$WORK/grub.cfg"
    else
        { printf 'set timeout=0\nset timeout_style=hidden\n'; cat "$WORK/grub.cfg"; } > "$WORK/grub.cfg.new"
        mv "$WORK/grub.cfg.new" "$WORK/grub.cfg"
    fi
fi
echo "Menus coupes + arguments automatiques injectes (BIOS + UEFI)."

# ------------------------------------------------- 7. REGENERATION ISO
echo "=== 6/6 — Regeneration de l'ISO hybride ==="
OUTISO="$OUTDIR/miles-debian13-autoinstall-$(date +%Y%m%d).iso"
rm -f "$OUTISO"

XORRISO_ARGS=(
  -indev "$ISO"
  -outdev "$OUTISO"
  -boot_image any replay
  -map "$WORK/initrd-new.gz" /install.amd/initrd.gz
  -map "$WORK/files" /files
  -map "$PRESED" /preseed.cfg
)
if [ "${#MAP_ISOLINUX[@]}" -gt 0 ]; then
    XORRISO_ARGS+=( "${MAP_ISOLINUX[@]}" )
fi
[ -f "$WORK/grub.cfg" ]     && XORRISO_ARGS+=( -map "$WORK/grub.cfg" /boot/grub/grub.cfg )
# Journal COMPLET de xorriso (un `tail` precedent avait avalé le detail
# d'un SORRI) ; pas d'operande parasite apres les options.
xorriso "${XORRISO_ARGS[@]}" 2>&1 | tee "$WORK/xorriso.log"

[ -s "$OUTISO" ] || { echo "ERREUR : ISO de sortie absente."; exit 1; }

# Vérification finale : l'ISO de sortie est bien amorçable et contient tout.
echo "Verification de l'ISO produite ..."
xorriso -indev "$OUTISO" -find / -name preseed.cfg 2>/dev/null | grep -q preseed.cfg \
    || { echo "ERREUR : preseed.cfg absent de l'ISO de sortie."; exit 1; }
xorriso -indev "$OUTISO" -find / -name miles-source.tar.gz 2>/dev/null | grep -q miles-source.tar.gz \
    || { echo "ERREUR : payload absente de l'ISO de sortie."; exit 1; }

( cd "$OUTDIR" && sha256sum "$(basename "$OUTISO")" > SHA256-ISO-SUMS )
echo
echo "=============================================================="
echo "ISO PRETE : $OUTISO"
echo "Taille    : $(du -h "$OUTISO" | cut -f1)"
echo "SHA256    : $(cut -d' ' -f1 "$OUTDIR/SHA256-ISO-SUMS")"
echo "--------------------------------------------------------------"
echo "Suite : ecrire sur la cle USB avec Rufus (voir README.md),"
echo "puis TEST VirtualBox AVANT de la brancher sur le mini-PC."
echo "=============================================================="

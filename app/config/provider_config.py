"""Configuration multi-fournisseurs de MILES (S6/mission multi-IA, L1).

Conventions (harmonisées avec `--setup` déjà livré, MI-008) :
- ``MILES_API_KEY_<PROVIDER>`` : clé par fournisseur (GROQ, OPENAI,
  ANTHROPIC, GEMINI) ;
- ``MILES_MODEL_<PROVIDER>`` : modèle choisi par fournisseur ;
- ``MILES_REMOTE_PROVIDER`` : fournisseur distant actif ;
- rétrocompatibilité stricte : ``MILES_REMOTE_API_KEY`` et
  ``MILES_REMOTE_MODEL`` restent **le fournisseur actif** (le pipeline
  historique RemoteProvider fonctionne sans modification) ;
- priorité **environnement > .env** : si une variable du fournisseur est
  déjà définie dans l'environnement du processus, l'écriture dans `.env`
  n'aurait aucun effet visible avant redémarrage — l'opération le signale.

Sécurité (invariants) :
- **aucune clé** dans un retour, une exception ou un journal ;
- état d'une clé = « configuree (n=X) » ou None ;
- écriture **atomique** et préservation de tous les paramètres non
  concernés (réutilisation de `app.config.setup.write_env`).
"""

from __future__ import annotations

import os
from typing import Any

from app.config.setup import write_env

#: Fournisseurs pris en charge par la mission (étendre ici pour ajouter).
PROVIDERS_SUPPORTES: tuple[str, ...] = ("groq", "openai", "anthropic", "gemini")

#: Caractères interdits dans une clé ou un identifiant de modèle (MI-008).
_CARACTERES_INTERDITS = ("\"", "'", "\\", "\n", "\r")


def _env_path(env_path: str | None) -> str:
    return env_path or os.environ.get("MILES_ENV_FILE", ".env")


def _lire_env(env_path: str) -> dict[str, str]:
    """Lire le .env en dictionnaire local (jamais retourné au clair)."""
    valeurs: dict[str, str] = {}
    chemin = _env_path(env_path)
    if not os.path.isfile(chemin):
        return valeurs
    try:
        with open(chemin, "r", encoding="utf-8") as fh:
            for ligne in fh:
                ligne = ligne.strip()
                if not ligne or ligne.startswith("#") or "=" not in ligne:
                    continue
                cle, valeur = ligne.split("=", 1)
                valeurs[cle.strip()] = valeur.strip()
    except OSError:
        return valeurs
    return valeurs


def _content(chemin: str) -> str:
    """Contenu brut du .env pour la fusion (écriture préservante)."""
    if not os.path.isfile(chemin):
        return ""
    try:
        with open(chemin, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _key_name(provider: str) -> str:
    return f"MILES_API_KEY_{provider.upper()}"


def _model_name(provider: str) -> str:
    return f"MILES_MODEL_{provider.upper()}"


def _valider_provider(provider: str) -> str:
    p = (provider or "").strip().lower()
    if p not in PROVIDERS_SUPPORTES:
        raise ValueError(
            f"Fournisseur inconnu : {provider!r} "
            f"(supportes : {', '.join(PROVIDERS_SUPPORTES)})"
        )
    return p


def _valider_cle(api_key: str) -> str:
    key = str(api_key or "")
    if (
        not key
        or len(key) > 512
        or any(c in key for c in _CARACTERES_INTERDITS)
        # Caracteres de controle (NUL, tabulation, retour arriere) : acceptes
        # jusqu'ici, ils etaient ecrits tels quels dans le `.env` et le
        # corrompaient pour tout consommateur autre que ce module. Un jeton
        # machine n'en contient jamais ; une cle avec espace est une erreur
        # de copier-coller, on la refuse plutot que de la stocker telle quelle.
        or any(c.isspace() or not c.isprintable() for c in key)
    ):
        raise ValueError("Cle API invalide (vide ou caracteres interdits).")
    return key


def statut(env_path: str | None = None) -> list[dict[str, Any]]:
    """Etat de chaque fournisseur, SANS reveler aucun secret.

    Chaque entree : {provider, cle, modele, actif} avec
    cle = "configuree (n=X)" ou None.
    """
    valeurs = _lire_env(env_path)
    actif = (os.environ.get("MILES_REMOTE_PROVIDER")
             or valeurs.get("MILES_REMOTE_PROVIDER", "groq")).lower()
    resultat = []
    for provider in PROVIDERS_SUPPORTES:
        key = os.environ.get(_key_name(provider)) or valeurs.get(_key_name(provider))
        modele = (os.environ.get(_model_name(provider))
                  or valeurs.get(_model_name(provider)))
        resultat.append({
            "provider": provider,
            "cle": f"configuree (n={len(key)})" if key else None,
            "modele": modele or None,
            "actif": provider == actif,
        })
    return resultat


def set_key(provider: str, api_key: str, env_path: str | None = None) -> str:
    """Ajouter ou remplacer la cle d'un fournisseur (retour sans secret).

    Returns:
        "nouvelle" ou "remplacee".
    Raises:
        ValueError: fournisseur ou cle invalide (message sans secret).
    """
    provider = _valider_provider(provider)
    api_key = _valider_cle(api_key)
    chemin = _env_path(env_path)
    valeurs = _lire_env(env_path)
    existait = bool(valeurs.get(_key_name(provider)))
    write_env(chemin, {_key_name(provider): api_key}, _content(chemin))
    return "remplacee" if existait else "nouvelle"


def set_model(provider: str, model: str, env_path: str | None = None) -> None:
    """Definir le modele d'un fournisseur (identifiant saisi, jamais invenie)."""
    provider = _valider_provider(provider)
    modele = str(model or "").strip()
    if not modele or any(c in modele for c in _CARACTERES_INTERDITS):
        raise ValueError("Modele invalide (vide ou caracteres interdits).")
    chemin = _env_path(env_path)
    write_env(chemin, {_model_name(provider): modele}, _content(chemin))


def remove_key(provider: str, env_path: str | None = None) -> bool:
    """Supprimer la cle d'un fournisseur (parametres non concernes preserves).

    Si le fournisseur etait l'actif, la ligne MILES_REMOTE_API_KEY est aussi
    retiree : une ancienne cle ne doit jamais continuer a servir silencieusement.
    Retourne False si aucune cle n'etait enregistree.
    """
    provider = _valider_provider(provider)
    chemin = _env_path(env_path)
    valeurs = _lire_env(env_path)
    present = bool(valeurs.get(_key_name(provider))
                   or os.environ.get(_key_name(provider)))
    if not present:
        return False
    cibles = [_key_name(provider)]
    if valeurs.get("MILES_REMOTE_PROVIDER", "").lower() == provider:
        cibles.append("MILES_REMOTE_API_KEY")
    contenu = _content(chemin)
    lignes = [
        l for l in contenu.splitlines()
        if not any(l.strip().startswith(c + "=") for c in cibles)
    ]
    _ecrire(chemin, "\n".join(lignes) + ("\n" if lignes else ""))
    return True


def _ecrire(chemin: str, contenu: str) -> None:
    """Ecriture atomique locale (retraits geres par remove_key)."""
    import tempfile
    dossier = os.path.dirname(os.path.abspath(chemin)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".miles-cfg-", suffix=".tmp", dir=dossier)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(contenu)
        os.replace(tmp, chemin)
    except OSError:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def activate(provider: str, env_path: str | None = None) -> dict[str, Any]:
    """Activer un fournisseur distant : configuration suffisante exigee.

    Ecrit MILES_REMOTE_PROVIDER et recopie MILES_API_KEY_<P> vers
    MILES_REMOTE_API_KEY + MILES_MODEL_<P> vers MILES_REMOTE_MODEL : le
    pipeline historique reste inchange (retrocompatibilite).

    Returns:
        dict sans secret {provider, modele, active_sur}.
    Raises:
        ValueError: fournisseur inconnu ou cle absente — la configuration
        PRECEDENTE est preservee (echec = aucun changement).
    """
    provider = _valider_provider(provider)
    chemin = _env_path(env_path)
    valeurs = _lire_env(env_path)
    cle = os.environ.get(_key_name(provider)) or valeurs.get(_key_name(provider))
    if not cle:
        raise ValueError(
            f"Configuration insuffisante : aucune cle pour {provider} "
            f"(utilisez /api add {provider}). La configuration precedente est conservee."
        )
    modele = (os.environ.get(_model_name(provider))
              or valeurs.get(_model_name(provider)) or "")
    maj = {
        "MILES_REMOTE_PROVIDER": provider,
        "MILES_REMOTE_API_KEY": cle,
        "MILES_REMOTE_MODEL": modele or valeurs.get("MILES_REMOTE_MODEL", ""),
    }
    write_env(chemin, maj, _content(chemin))
    return {"provider": provider, "modele": modele or None, "active_sur": "MILES_REMOTE_*"}


def environnement_prioritaire(provider: str) -> list[str]:
    """Variables de ce fournisseur deja definies dans l'ENVIRONNEMENT.

    Priorite environnement > .env : ces variables masquent l'ecriture du
    `.env` tant que le processus vit — l'interface doit le signaler.
    """
    return [
        cle for cle in (_key_name(provider), _model_name(provider),
                        "MILES_REMOTE_PROVIDER", "MILES_REMOTE_API_KEY")
        if os.environ.get(cle)
    ]


def modele_fournisseur(provider: str, env_path: str | None = None) -> str | None:
    """Modele enregistre pour ce fournisseur (env puis .env), ou None."""
    provider = _valider_provider(provider)
    valeurs = _lire_env(env_path)
    return (os.environ.get(_model_name(provider))
            or valeurs.get(_model_name(provider))) or None


def cle_pour(provider: str, env_path: str | None = None) -> str | None:
    """Cle interne au processus pour construire un adaptateur.

    USAGE INTERNE UNIQUE : ce retour n'est jamais affiche, journalise ni
    transmis — seuls les appelsants qui construisent un adaptateur
    l'utilisent (la couche interface n'imprime jamais cette valeur).
    """
    provider = _valider_provider(provider)
    valeurs = _lire_env(env_path)
    return (os.environ.get(_key_name(provider))
            or valeurs.get(_key_name(provider))) or None


def fournisseur_actif(env_path: str | None = None,
                      defaut: str | None = "groq") -> str | None:
    """Fournisseur distant actif (environnement puis .env).

    Args:
        defaut: valeur retournée si rien n'est defini — None pour le
            routage (miles.py) qui doit alors suivre la voie
            retrocompatible historique, "groq" pour l'affichage.
    """
    valeurs = _lire_env(env_path)
    return (os.environ.get("MILES_REMOTE_PROVIDER")
            or valeurs.get("MILES_REMOTE_PROVIDER") or defaut)


def modele_actif(env_path: str | None = None) -> str | None:
    """Modele distant actif (environnement puis .env), ou None si absent."""
    valeurs = _lire_env(env_path)
    return (os.environ.get("MILES_REMOTE_MODEL")
            or valeurs.get("MILES_REMOTE_MODEL")) or None

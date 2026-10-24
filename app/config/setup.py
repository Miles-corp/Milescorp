"""Assistant de première configuration des fournisseurs IA (S6 minimal).

Principe (décisions validées du 2026-10-24, fiche MI-008) :
- les clés sont stockées uniquement dans le fichier `.env` local, ignoré par Git ;
- la clé n'est jamais affichée, journalisée ou consignée de quelconque façon ;
- l'écriture du `.env` est atomique (fichier temporaire + os.replace) ;
- portée initiale minimal : un seul fournisseur configuré à la fois.
"""

from __future__ import annotations

import getpass
import os
import tempfile
from pathlib import Path
from typing import Callable

#: Catalogue connu : nom affichable -> (base_url, modèle par défaut).
PROVIDERS: dict[str, tuple[str, str]] = {
    "groq": ("https://api.groq.com/openai/v1", "llama-3.1-8b-instant"),
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "gemini-2.0-flash",
    ),
    "mistral": ("https://api.mistral.ai/v1", "mistral-small-latest"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "claude": ("https://api.anthropic.com/v1", "claude-3-5-haiku-latest"),
}

#: Variables écrites par l'assistant (le reste du `.env` est préservé).
MANAGED_KEYS = (
    "MILES_PROVIDER",
    "MILES_REMOTE_BASE_URL",
    "MILES_REMOTE_MODEL",
    "MILES_REMOTE_API_KEY",
)


def write_env(
    env_path: str,
    variables: dict[str, str],
    existing_content: str = "",
) -> str:
    """Écrire les variables dans `.env` de façon atomique.

    Renvoie le chemin écrit. Les lignes des variables gérées sont
    remplacées si présentes, ajoutées sinon. Les autres lignes et les
    commentaires du contenu existant sont conservés tels quels.
    """
    lines = existing_content.splitlines()
    out: list[str] = []
    remaining = dict(variables)
    for line in lines:
        stripped = line.strip()
        handled = False
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                out.append(f"{key}={remaining.pop(key)}")
                handled = True
        if not handled:
            out.append(line)
    for key, value in remaining.items():
        out.append(f"{key}={value}")
    content = "\n".join(out) + "\n"

    directory = os.path.dirname(os.path.abspath(env_path)) or "."
    fd, tmp_path = tempfile.mkstemp(
        prefix=".miles-setup-", suffix=".tmp", dir=directory
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        os.replace(tmp_path, env_path)
    except OSError:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    return env_path


def run_setup(
    env_path: str = ".env",
    ask: Callable[[str], str] = getpass.getpass,
    show: Callable[[str], None] = print,
    pick: Callable[[str], str] | None = None,
) -> int:
    """Assistant interactif : choisir un fournisseur et enregistrer sa clé.

    `ask` est utilisée pour la saisie masquée de la clé (getpass par
    défaut) ; `pick` pour les entrées non secrètes (fournisseur, modèle)
    et est remplacée par `input` en exécution réelle. La clé ne figure
    jamais à l'écran ni dans un journal. Aucune requête réseau n'est
    effectuée ici ; la connexion réelle reste un test séparé (S1),
    désormais conditionné au plafond de coût autorisé.
    """
    pick = pick or input
    show("Assistant de configuration de MILES (portée minimale).")
    show("Fournisseurs disponibles : " + ", ".join(PROVIDERS))
    show("Réutilisation du lien d'identité (comptes partagés) : à venir.")
    choice = pick("Fournisseur (nom exact) : ").strip().lower()
    if choice not in PROVIDERS:
        show(f"Fournisseur inconnu : {choice}. Aucun fichier modifié.")
        return 1

    base_url, default_model = PROVIDERS[choice]
    model = pick(f"Modèle [{default_model}] : ").strip() or default_model
    api_key = ask(f"Clé API {choice} (saisie masquée) : ").strip()
    if not api_key:
        show("Clé vide : configuration abandonnée, aucun fichier modifié.")
        return 1
    if any(ch in api_key for ch in ("\"", "'", "\\", "\n")):
        show("Clé inattendue : configuration abandonnée, aucun fichier modifié.")
        return 1

    existing = ""
    env_path = env_path or ENV_NAME
    if os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as fh:
                existing = fh.read()
        except OSError as exc:
            show(f"Impossible de lire le `.env` existant : {exc}")
            return 1

    variables = {
        "MILES_PROVIDER": "remote",
        "MILES_REMOTE_BASE_URL": base_url,
        "MILES_REMOTE_MODEL": model,
        "MILES_REMOTE_API_KEY": api_key,
    }
    path = write_env(env_path, variables, existing)
    show(f"Configuration enregistrée dans {path}.")
    show(
        f"Fournisseur : {choice} (mode remote). "
        "Test réel de connexion à exécuter séparément, après autorisation du coût."
    )
    return 0


ENV_NAME = ".env"

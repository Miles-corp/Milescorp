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
from typing import Callable, Optional

from app.config.oauth import linked_providers, OAUTH_PROVIDERS
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

#: Groupes de fournisseurs partageant un même fournisseur d'identité (S6.2).
#:
#: Exemple d'usage : le groupe `google` regroupe les services joignables
#: avec un compte Google (ex. Gemini) : après en avoir configuré un, les
#: autres du groupe sont proposés avec le MINIMUM de questions (clé seule).
#: Le raccourci OAuth réel (connexion navigateur) n'est PAS implémenté ici :
#: il exigerait un flux réseau/navigateur hors périmètre local.
IDENTITY_GROUPS: dict[str, tuple[str, ...]] = {
    "google": ("gemini", "mistral"),
    "groq": ("groq",),
    "openai": ("openai",),
    "claude": ("claude",),
}


def _identity_of(provider_name: str) -> str | None:
    """Retourner le groupe d'identité d'un fournisseur, ou None."""
    for group, members in IDENTITY_GROUPS.items():
        if provider_name in members:
            return group
    return None


def _siblings_of(provider_name: str, already: set[str]) -> list[str]:
    """Retourner les services du même groupe d'identité pas encore configurés."""
    group = _identity_of(provider_name)
    if not group:
        return []
    return [p for p in IDENTITY_GROUPS[group] if p not in already]


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
    yes = ("o", "oui", "y", "yes")
    show("Assistant de configuration de MILES (S6 : comptes liés).")
    show("Fournisseurs disponibles : " + ", ".join(PROVIDERS))

    linked = linked_providers(env_path)
    if linked:
        show("Comptes déjà liés (OAuth) : " + ", ".join(linked))
        show("Les services de ces comptes seront configurés avec le minimum d'étapes.")

    env_path = env_path or ENV_NAME
    existing = ""
    if os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as fh:
                existing = fh.read()
        except OSError as exc:
            show(f"Impossible de lire le `.env` existant : {exc}")
            return 1

    configured: set[str] = set()
    variables: dict[str, str] = {}
    active = ""

    def _collect(name: str, quick: bool, set_active: bool) -> dict[str, str] | None:
        """Collecter la configuration d'un fournisseur.

        `quick=True` : étapes réduites — modèle par défaut, **clé seule**.
        `set_active=True` : ce fournisseur devient le bloc actif
        (`MILES_REMOTE_*`) ; sinon seule sa clé par fournisseur est stockée.
        """
        base_url, default_model = PROVIDERS[name]
        if quick:
            model = default_model
            show(f"[étapes réduites] {name} : modèle par défaut {model}.")
        else:
            model = pick(f"Modèle [{default_model}] : ").strip() or default_model
        api_key = ask(f"Clé API {name} (saisie masquée) : ").strip()
        if not api_key:
            show(f"Clé vide : {name} ignoré.")
            return None
        if any(ch in api_key for ch in ("\"", "'", "\\", "\n")):
            show(f"Clé inattendue : {name} ignoré.")
            return None
        block = {f"MILES_API_KEY_{name.upper()}": api_key}
        if set_active:
            block.update(
                {
                    "MILES_PROVIDER": "remote",
                    "MILES_REMOTE_BASE_URL": base_url,
                    "MILES_REMOTE_MODEL": model,
                    "MILES_REMOTE_API_KEY": api_key,
                }
            )
        return block

    # 1. Premier fournisseur : questions complètes (ou réduites si compte lié).
    choice = pick("Fournisseur (nom exact) : ").strip().lower()
    if choice not in PROVIDERS:
        show(f"Fournisseur inconnu : {choice}. Aucun fichier modifié.")
        return 1
    is_linked = choice in linked
    if is_linked:
        show(f"[compte lié] {choice} : étapes réduites (clé seule).")
    block = _collect(choice, quick=is_linked, set_active=True)
    if block is None:
        show("Configuration abandonnée, aucun fichier modifié.")
        return 1
    variables.update(block)
    configured.add(choice)
    active = choice

    # 2. Suite : services du même compte (clé seule) puis autres fournisseurs.
    while True:
        siblings = _siblings_of(choice, configured)
        if siblings:
            answer = pick(
                "Services du même compte ("
                + ", ".join(siblings)
                + ") : configurer ? [o/N] : "
            ).strip().lower()
            if answer in yes:
                for sibling in siblings:
                    block = _collect(sibling, quick=True, set_active=False)
                    if block is not None:
                        variables.update(block)
                        configured.add(sibling)
                continue
        answer = pick("Configurer un autre fournisseur ? [o/N] : ").strip().lower()
        if answer not in yes:
            break
        choice = pick("Fournisseur (nom exact) : ").strip().lower()
        if choice not in PROVIDERS:
            show(f"Fournisseur inconnu : {choice}. Ignoré.")
            continue
        is_linked = choice in linked
        if is_linked:
            show(f"[compte lié] {choice} : étapes réduites (clé seule).")
        block = _collect(choice, quick=is_linked, set_active=False)
        if block is not None:
            variables.update(block)
            configured.add(choice)

    if not variables:
        show("Aucune configuration enregistrée.")
        return 1
    path = write_env(env_path, variables, existing)
    show(f"Configuration enregistrée dans {path} ({len(configured)} fournisseur(s)).")
    show(
        f"Fournisseur actif : {active} (mode remote). Les clés sont stockées "
        "par fournisseur (MILES_API_KEY_<NOM>) ; le test réel de connexion "
        "reste à exécuter après autorisation du coût."
    )
    return 0


ENV_NAME = ".env"

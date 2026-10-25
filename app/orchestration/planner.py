"""Planification des missions MILES.

Deux planificateurs sont proposés :

- :class:`DeterministicPlanner` : plan déterministe, sans IA, qui sert de
  référence et de repli. Il implémente la mission pilote d'analyse en
  lecture seule ;
- :class:`ProviderPlanner` : plan proposé par le fournisseur IA configuré.
  **Toute** sortie du modèle est validée avant exécution : outil
  enregistré, outil autorisé, paramètres déclarés et typés, nombre
  d'étapes borné. En cas de réponse invalide ou de fournisseur
  indisponible, le plan déterministe est utilisé et la mission conserve
  la trace factuelle du repli.

La sortie d'un modèle est une **donnée** : elle ne peut ni accorder une
permission, ni élargir le périmètre des outils, ni modifier les règles de
l'orchestrateur.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from app.orchestration.models import (
    ExecutionLimits,
    Plan,
    PlanStep,
    SourceRef,
)
from app.tools.registry import ToolRegistry

logger = logging.getLogger("miles.orchestration")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())


class ClarificationRequired(Exception):
    """Une information manque pour poursuivre la mission.

    La question posée est destinée à l'utilisateur, pas au modèle.
    """

    def __init__(self, question: str) -> None:
        super().__init__(question)
        self.question = question


class PlanRejected(Exception):
    """Un plan proposé a été refusé par les contrôles de validation."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ProviderUnavailable(Exception):
    """Le fournisseur IA n'est pas disponible pour planifier."""


@dataclass
class PlanContext:
    """Contexte de planification.

    Attributs :
        registry : registre des outils disponibles.
        allowed_tool_ids : outils que la mission a le droit d'utiliser.
        limits : bornes d'exécution.
        target_path : chemin cible de la mission (si connu).
        mission_id : identifiant de la mission planifiée.
    """

    registry: ToolRegistry
    allowed_tool_ids: List[str] = field(default_factory=list)
    limits: ExecutionLimits = field(default_factory=ExecutionLimits)
    target_path: str = ""
    mission_id: str = ""

    def tool_allowed(self, tool_id: str) -> bool:
        """Indiquer si un outil est utilisable par la mission."""
        return tool_id in self.allowed_tool_ids


class Planner(Protocol):
    """Contrat minimal d'un planificateur."""

    name: str

    def plan(self, objective: str, context: PlanContext) -> Plan:
        """Produire un plan pour un objectif donné."""


# --- Outils de lecture sealing -------------------------------------------------

#: Marqueurs désignant le dossier courant ou le projet sans nom explicite.
_GENERIC_TARGET_MARKERS = (
    "ce dossier",
    "le dossier",
    "ce projet",
    "le projet",
    "ce repertoire",
    "le repertoire",
    "ce dépôt",
    "le dépôt",
    "ce depot",
    "le depot",
    "cette arborescence",
    "cette arborescence",
    "ce repertoire de travail",
)

#: Mots outils qui ne sont jamais un chemin.
_STOPWORDS = {
    "ce", "cette", "le", "la", "les", "un", "une", "des", "du", "de", "du",
    "dossier", "repertoire", "répertoire", "projet", "depot", "dépôt",
    "fichiers", "fichier", "organisation", "ameliore", "améliorations",
    "ameliorations", "possibles", "sans", "modifier", "aucun", "analyse",
    "analyser", "ceci", "cela", "tous", "toutes", "lesquels", "lesquelles",
    "and", "or", "the", "of", "to", "in", "for", "with", "this", "that",
}

#: Expressions suivis d'un nom de dossier potentiel.
_TARGET_AFTER_MARKER = re.compile(
    r"(?:dossier|repertoire|répertoire|projet|depot|dépôt|folder|directory)"
    r"\s+([A-Za-z0-9_.\-]+)",
    re.IGNORECASE,
)

#: Caractères autorisés dans un segment de chemin (hors séparateur).
_SEGMENT_CHARS = r"A-Za-z0-9_.~-"

#: Jeton contenant un séparateur de chemin.
#:
#: L'extraction conserve fidèlement ce que l'utilisateur a écrit, et en
#: particulier la lettre de lecteur Windows (« C:/Windows », « D:\\donnees »)
#: : la perdre désignait un **autre** répertoire (défaut D2).
_PATH_LIKE = re.compile(
    r"(?<![A-Za-z0-9_.~-])"  # début de jeton (pas de milieu de mot)
    r"(?:[A-Za-z]:)?"  # lettre de lecteur Windows (« C: »)
    rf"[{_SEGMENT_CHARS}]*"  # premier segment
    rf"(?:[\\/][{_SEGMENT_CHARS}]*)+"  # segments suivants
)

#: Chemin délimité par des guillemets : les espaces y font partie du chemin.
#:
#: C'est la forme non ambiguë d'un chemin contenant des espaces :
#: « Analyse "C:\\Users\\Jean\\Mes Documents" ».
_QUOTED_PATH = re.compile(r"[\"'«]([^\"'»]+)[\"'»]")

#: Mot suivant dans le texte, avec son début.
_NEXT_WORD = re.compile(r"\s+(\S+)")

#: Chemin Windows absolu (lettre de lecteur).
_WINDOWS_ABSOLUTE = re.compile(r"[A-Za-z]:[\\/]")

#: Une lettre de lecteur seule (« C: ») ne désigne pas un dossier.
_DRIVE_ONLY = re.compile(r"[A-Za-z]:")


def _word_continues_path(word: str, token: str) -> bool:
    """Indiquer si un mot prolonge le chemin déjà reconnu.

    Un mot qui contient lui-même un séparateur prolonge le chemin
    (« C:\\Program Files\\MonDossier »). Un mot capitalisé le prolonge
    également quand le chemin est un chemin ABSOLU (Windows « C:\\… » ou
    POSIX « /… »), car les noms de dossiers contiennent souvent des
    espaces (« C:\\Users\\Jean\\Mes Documents », « /home/jean/Mes
    Documents ») ; cette seconde règle est volontairement limitée aux
    chemins absolus pour ne pas avaler la prose qui suit un chemin relatif.

    Les chemins relatifs ne sont jamais prolongés par un mot capitalisé :
    « docs/ identifie son organisation » doit rester « docs/ ».
    """
    if "/" in word or "\\" in word:
        return True
    if word[:1].isupper() and (
        _WINDOWS_ABSOLUTE.match(token) or token.startswith("/")
    ):
        return True
    return False


def _extend_with_following_words(
    objective: str, end: int, token: str
) -> tuple[str, int]:
    """Prolonger un chemin avec les mots qui lui appartiennent.

    Args:
        objective : objectif complet.
        end : position juste après le jeton reconnu.
        token : jeton reconnu.

    Returns:
        Le chemin prolongé et la position atteinte.
    """
    while True:
        match = _NEXT_WORD.match(objective, end)
        if match is None:
            return token, end
        word = match.group(1).strip(".,;:!?\"'«»")
        if not word or not _word_continues_path(word, token):
            return token, end
        token = f"{token} {word}"
        end = match.end()


def extract_target_path(objective: str) -> Optional[str]:
    """Déduire le chemin cible d'un objectif en langage naturel.

    Retourne None si aucun chemin ne peut être déduit avec certitude : dans
    ce cas, l'orchestrateur doit demander une clarification.

    Heuristiques (volontairement conservatrices) :
    - un jeton contenant un séparateur de chemin (``docs/``, ``C:\\x``) est
      un candidat ;
    - un chemin entre guillemets (« "C:\\Users\\Jean\\Mes Documents" ») est
      un candidat dont les espaces font partie du chemin ;
    - ``dossier <nom>`` / ``projet <nom>`` désigne le nom donné ;
    - « ce dossier », « le projet »… désignent la racine du projet ;
    - plusieurs candidats distincts => aucune déduction (clarification).
    """
    text = objective.lower()
    candidates: List[str] = []
    #: Zones du texte déjà couvertes par un chemin reconnu : un marqueur
    #: (« dossier … ») qui s'y trouve ne désigne pas une autre cible.
    covered: List[tuple[int, int]] = []

    consumed_until = 0
    for match in _PATH_LIKE.finditer(objective):
        if match.start() < consumed_until:
            # Jeton déjà absorbé par le prolongement du chemin précédent
            # (« C:\Program Files\MonDossier » est un seul chemin).
            continue
        token = match.group(0)
        consumed_until = match.end()
        if token.lower() in _STOPWORDS:
            continue
        token, consumed_until = _extend_with_following_words(
            objective, consumed_until, token
        )
        covered.append((match.start(), consumed_until))
        candidates.append(token)

    for match in _QUOTED_PATH.finditer(objective):
        # Un chemin entre guillemets est pris tel quel : c'est la forme
        # non ambiguë d'un chemin contenant des espaces.
        token = match.group(1).strip()
        if "/" not in token and "\\" not in token:
            continue
        if token.lower() in _STOPWORDS:
            continue
        covered.append((match.start(), match.end()))
        candidates.append(token)

    for match in _TARGET_AFTER_MARKER.finditer(objective):
        token = match.group(1)
        if token.lower() in _STOPWORDS:
            continue
        # Le marqueur est situé à l'intérieur d'un chemin déjà reconnu
        # (« C:\...\Dossier Avec Espace ») : il ne désigne pas une autre
        # cible.
        if any(start <= match.start() < end for start, end in covered):
            continue
        # Le marqueur (« dossier … ») peut ne capturer qu'un *préfixe* d'un
        # chemin : « dossier C:/Windows » capture « C », « dossier
        # docs/coordination » capture « docs ». Dans ce cas, le chemin
        # complet est déjà un candidat : le préfixe est ignoré, sinon deux
        # cibles distinctes seraient déduites et la mission demanderait une
        # clarification inutile.
        end = match.end(1)
        if end < len(objective) and objective[end] in ":/\\":
            continue
        if not any(candidate.endswith(token) for candidate in candidates):
            candidates.append(token)

    distinct = []
    for candidate in candidates:
        # Les séparateurs de fin ne portent pas d'information : « docs/ »
        # et « docs » désignent la même cible.
        cleaned = candidate.rstrip("/\\ ")
        if not cleaned:
            continue
        # « C: » seul ne désigne pas un dossier : la cible reste inconnue
        # et l'orchestrateur demandera une clarification.
        if _DRIVE_ONLY.fullmatch(cleaned):
            continue
        # Deduplication par prefixe (diagnostic WSL 2026-10-25, cas #6) :
        # si un candidat est un prefixe strict d'un autre ("Dossier" et
        # "Dossier Avec Espace"), on garde le plus long. Cela evite qu'un
        # chemin tronque et le chemin complet soient comptes comme deux
        # cibles distinctes, ce qui forcerait une clarification inutile.
        replaced = False
        for i, existing in enumerate(distinct):
            if cleaned == existing:
                replaced = True
                break
            if existing.startswith(cleaned + " ") or existing.startswith(cleaned + "/") or existing.startswith(cleaned + chr(92)):
                # cleaned est un prefixe de existing : on garde existing.
                replaced = True
                break
            if cleaned.startswith(existing + " ") or cleaned.startswith(existing + "/") or cleaned.startswith(existing + chr(92)):
                # existing est un prefixe de cleaned : on le remplace.
                distinct[i] = cleaned
                replaced = True
                break
        if not replaced:
            distinct.append(cleaned)

    if len(distinct) == 1:
        return distinct[0]

    if not distinct:
        if any(marker in text for marker in _GENERIC_TARGET_MARKERS):
            return "."
        return None

    return None


def _describe_allowed_tools(context: PlanContext) -> str:
    """Décrire les outils utilisables, pour la consigne au fournisseur IA."""
    lines = []
    for tool_id in context.allowed_tool_ids:
        tool = context.registry.get_tool(tool_id)
        if tool is None:
            continue
        params = ", ".join(
            f"{p.name}:{p.type.__name__}{'' if p.required else '?'}"
            for p in tool.parameters
        )
        lines.append(
            f"- {tool_id} (risque {tool.risk_level}) "
            f"paramètres: {params or 'aucun'} — {tool.description}"
        )
    return "\n".join(lines)


def validate_plan_payload(
    payload: Any,
    context: PlanContext,
    mission_id: str,
) -> Plan:
    """Valider un plan proposé par un modèle avant toute exécution.

    Refuse :
    - un payload qui n'est pas un objet JSON avec une liste ``steps`` ;
    - un plan vide ou plus long que la limite d'étapes ;
    - un outil inconnu, non enregistré ou non autorisé par la mission ;
    - un paramètre non déclaré, mal typé ou interdit ;
    - un paramètre requis manquant (sauf s'il est injecté à l'exécution).

    Returns:
        Le plan validé.

    Raises:
        PlanRejected: si le plan ne respecte pas les règles.
    """
    if not isinstance(payload, dict):
        raise PlanRejected("Le plan doit être un objet JSON.")
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list):
        raise PlanRejected("Le champ 'steps' doit être une liste.")
    if not raw_steps:
        raise PlanRejected("Le plan ne contient aucune étape.")
    if len(raw_steps) > context.limits.max_steps:
        raise PlanRejected(
            f"Plan trop long : {len(raw_steps)} étapes "
            f"(maximum {context.limits.max_steps})."
        )

    steps: List[PlanStep] = []
    for index, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            raise PlanRejected(f"Étape {index + 1} : structure invalide.")
        objective = raw.get("objective")
        tool_id = raw.get("tool")
        parameters = raw.get("parameters", {})
        if not isinstance(objective, str) or not objective.strip():
            raise PlanRejected(f"Étape {index + 1} : objectif manquant.")
        if not isinstance(tool_id, str) or not tool_id.strip():
            raise PlanRejected(f"Étape {index + 1} : outil manquant.")
        if not isinstance(parameters, dict):
            raise PlanRejected(
                f"Étape {index + 1} : les paramètres doivent être un objet."
            )

        tool = context.registry.get_tool(tool_id)
        if tool is None:
            raise PlanRejected(
                f"Étape {index + 1} : outil inconnu ou non enregistré : {tool_id!r}."
            )
        if not context.tool_allowed(tool_id):
            raise PlanRejected(
                f"Étape {index + 1} : outil non autorisé pour cette mission : "
                f"{tool_id!r}."
            )

        declared = {p.name: p for p in tool.parameters}
        for key, value in parameters.items():
            if key not in declared:
                raise PlanRejected(
                    f"Étape {index + 1} : paramètre non déclaré pour "
                    f"{tool_id!r} : {key!r}."
                )
            expected = declared[key].type
            if expected is float:
                valid = isinstance(value, (int, float)) and not isinstance(value, bool)
            elif expected is int:
                valid = isinstance(value, int) and not isinstance(value, bool)
            else:
                valid = isinstance(value, expected)
            if not valid:
                raise PlanRejected(
                    f"Étape {index + 1} : paramètre {key!r} de type invalide "
                    f"(attendu {expected.__name__})."
                )
            if isinstance(value, str) and any(
                forbidden in value.lower()
                for forbidden in ("shell", "rm -rf", "cmd /c", "powershell -")
            ):
                raise PlanRejected(
                    f"Étape {index + 1} : paramètre {key!r} contient une "
                    "commande interdite."
                )

        for param in tool.parameters:
            if (
                param.required
                and param.name not in parameters
                and not raw.get("source_step")
            ):
                raise PlanRejected(
                    f"Étape {index + 1} : paramètre requis manquant "
                    f"{param.name!r} pour {tool_id!r}."
                )

        steps.append(
            PlanStep(
                step_id=f"s{index + 1}",
                objective=objective.strip(),
                tool_id=tool_id,
                parameters=dict(parameters),
            )
        )

    return Plan(mission_id=mission_id, steps=steps, planner="ia")


class DeterministicPlanner:
    """Planificateur déterministe : aucun appel IA, comportement stable.

    Implémente la mission pilote d'analyse en lecture seule : recenser un
    dossier, puis examiner les fichiers texte qu'il contient.
    """

    name = "deterministe"

    #: Nombre de fichiers examinés au maximum.
    MAX_FILES_READ = 3

    def plan(self, objective: str, context: PlanContext) -> Plan:
        """Produire le plan d'analyse en lecture seule.

        Raises:
            ClarificationRequired: si le dossier à analyser est ambigu.
            PlanRejected: si le chemin demandé est hors périmètre autorisé.
        """
        target = context.target_path or extract_target_path(objective)
        if not target:
            raise ClarificationRequired(
                "Quel dossier dois-je analyser ? Indiquez un chemin "
                "(ex. « app/ » ou « docs/coordination »)."
            )

        from app.security.paths import PathSecurityError, resolve_authorized_path

        try:
            resolved = resolve_authorized_path(target)
        except PathSecurityError as exc:
            raise PlanRejected(
                f"Chemin hors périmètre autorisé : {target} ({exc})."
            ) from exc

        target = str(resolved)
        steps: List[PlanStep] = []
        allowed = set(context.allowed_tool_ids)

        if "action_workdir" in allowed:
            steps.append(
                PlanStep(
                    step_id="s1",
                    objective="Situer le répertoire de travail courant",
                    tool_id="action_workdir",
                    parameters={},
                )
            )

        listing_index = ""
        if "action_list_files" in allowed:
            listing_index = f"s{len(steps) + 1}"
            steps.append(
                PlanStep(
                    step_id=listing_index,
                    objective=f"Recenser les fichiers de {target}",
                    tool_id="action_list_files",
                    # Profondeur 2 : le dossier et un niveau de
                    # sous-dossiers, pour ne pas s'arrêter à une racine vide.
                    parameters={"path": target, "depth": 2},
                )
            )

        if listing_index and "action_read_file" in allowed:
            read_budget = max(
                0, min(self.MAX_FILES_READ, context.limits.max_steps - len(steps))
            )
            for index in range(read_budget):
                steps.append(
                    PlanStep(
                        step_id=f"s{len(steps) + 1}",
                        objective=(
                            f"Examiner le contenu du fichier texte n°{index + 1} "
                            f"de {target}"
                        ),
                        tool_id="action_read_file",
                        parameters={},
                        source=SourceRef(
                            step_id=listing_index, key="entries", index=index
                        ),
                        target_parameter="path",
                        depends_on=[listing_index],
                    )
                )

        if not steps:
            raise PlanRejected(
                "Aucun outil autorisé ne permet d'observer le dossier demandé."
            )

        return Plan(
            mission_id=context.mission_id,
            steps=steps,
            planner=self.name,
            note=(
                "Plan déterministe d'analyse en lecture seule : contexte, "
                "recensement, puis examen des fichiers texte."
            ),
        )


class ProviderPlanner:
    """Planificateur utilisant le fournisseur IA configuré.

    La sortie du modèle est validée par :func:`validate_plan_payload`
    avant toute exécution. Le planificateur ne lève pas d'exception en cas
    d'échec : il retourne None et laisse l'appelant décider du repli, qui
    reste tracé dans la mission.
    """

    name = "ia"

    def __init__(self, provider: Any, fallback: Optional[Planner] = None) -> None:
        self._provider = provider
        self._fallback = fallback

    def plan(self, objective: str, context: PlanContext) -> Plan:
        """Demander un plan au fournisseur puis le valider.

        Returns:
            Le plan validé, ou le plan de repli si le fournisseur est
            indisponible ou si sa réponse est refusée.
        """
        if self._provider is None:
            return self._fallback_plan(objective, context, "fournisseur IA absent")
        try:
            if not self._provider.is_available():
                return self._fallback_plan(
                    objective, context, "fournisseur IA indisponible"
                )
        except Exception:  # noqa: BLE001 — un fournisseur instable vaut « indisponible »
            return self._fallback_plan(
                objective, context, "fournisseur IA instable"
            )

        messages = self._build_messages(objective, context)
        try:
            raw_response = self._provider.chat(messages)
        except Exception as exc:  # noqa: BLE001 — échec provider, pas d'IA simulée
            logger.warning("Fournisseur IA indisponible pour la planification.")
            return self._fallback_plan(
                objective, context, f"échec de l'appel au fournisseur IA ({type(exc).__name__})"
            )

        try:
            payload = self._parse_response(raw_response)
            plan = validate_plan_payload(payload, context, context.mission_id)
        except PlanRejected as exc:
            return self._fallback_plan(
                objective, context, f"plan IA rejeté : {exc.reason}"
            )

        plan.note = (
            "Plan proposé par le fournisseur IA puis validé "
            "(outils enregistrés, autorisés, paramètres typés)."
        )
        return plan

    def _fallback_plan(
        self, objective: str, context: PlanContext, reason: str
    ) -> Plan:
        """Produire le plan de repli, en conservant la raison du repli."""
        if self._fallback is None:
            raise PlanRejected(f"Aucun plan disponible ({reason}).")
        plan = self._fallback.plan(objective, context)
        plan.note = f"{plan.note} Repli : {reason}."
        plan.planner = f"{plan.planner}+repli"
        return plan

    def _build_messages(self, objective: str, context: PlanContext) -> list[dict[str, str]]:
        """Construire la consigne adressée au fournisseur IA."""
        system = (
            "Tu proposes un plan d'observation pour MILES. "
            "Réponds UNIQUEMENT par un objet JSON, sans texte autour, "
            "de la forme : "
            '{"steps": [{"objective": "...", "tool": "...", "parameters": {}}]}. '
            "Règles : n'utilise que les outils listés, n'invente aucun "
            "paramètre, n'en propose aucun qui ne soit pas déclaré, "
            "n'écris aucun fichier, n'exécute aucune commande. "
            "Les outils listés sont :\n"
            f"{_describe_allowed_tools(context)}"
        )
        user = f"Objectif de la mission : {objective}"
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    @staticmethod
    def _parse_response(raw_response: Any) -> Any:
        """Extraire l'objet JSON d'une réponse textuelle du fournisseur.

        Raises:
            PlanRejected: si la réponse ne contient pas de JSON exploitable.
        """
        if isinstance(raw_response, dict):
            return raw_response
        if not isinstance(raw_response, str) or not raw_response.strip():
            raise PlanRejected("réponse vide du fournisseur IA")
        text = raw_response.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise PlanRejected("réponse du fournisseur IA sans objet JSON")
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise PlanRejected(f"JSON invalide : {exc.msg}") from exc


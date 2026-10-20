"""Observation des résultats d'outils.

L'observateur transforme un résultat d'étape en **faits** vérifiables et
détecte les situations où la mission ne progresse plus.

RègleAbsolute : le contenu retourné par un outil est une donnée. Il n'est
jamais exécuté, jamais interprété comme une instruction et ne peut ni
modifier les autorisations, ni le plan, ni les règles de l'orchestrateur.
Un fichier contenant « ignore les règles précédentes » est donc traité
comme du texte à rapporter, pas comme un ordre.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.orchestration.executor import StepOutcome
from app.orchestration.models import PlanStep, StepStatus


@dataclass
class Observation:
    """Analyse d'une étape après exécution.

    Attributs :
        status : statut observé.
        facts : faits vérifiables déduits du résultat.
        summary : résumé court et factuel.
        progressed : False si l'étape n'a apporté aucune information.
        signature : empreinte du résultat (détection de répétition).
    """

    status: StepStatus = StepStatus.PENDING
    facts: List[str] = field(default_factory=list)
    summary: str = ""
    progressed: bool = True
    signature: str = ""


class Observer:
    """Analyse les résultats d'outils et produit des faits exploitables."""

    #: Nombre maximal de noms de fichiers cités dans un fait.
    MAX_NAMES_IN_FACT = 12

    def observe(self, step: PlanStep, outcome: StepOutcome) -> Observation:
        """Produire l'observation d'une étape."""
        if outcome.status == StepStatus.SUCCEEDED:
            return self._observe_success(step, outcome)
        if outcome.status == StepStatus.SKIPPED:
            return Observation(
                status=StepStatus.SKIPPED,
                facts=[f"Étape {step.step_id} sautée : {outcome.skipped_reason}"],
                summary=outcome.skipped_reason,
                progressed=False,
            )
        if outcome.status == StepStatus.BLOCKED:
            return Observation(
                status=StepStatus.BLOCKED,
                facts=[
                    f"Étape {step.step_id} non exécutée : autorisation humaine "
                    "requise."
                ],
                summary=outcome.error,
                progressed=False,
            )
        return Observation(
            status=StepStatus.FAILED,
            facts=[f"Étape {step.step_id} en échec : {outcome.error}"],
            summary=outcome.error,
            progressed=False,
        )

    def _observe_success(self, step: PlanStep, outcome: StepOutcome) -> Observation:
        """Produire l'observation d'une étape réussie."""
        data = outcome.result
        facts: List[str] = []
        summary = ""

        if isinstance(data, dict) and "entries" in data:
            entries = data.get("entries") or []
            path = str(data.get("path", ""))
            depth = data.get("depth", 1)
            directories = [e for e in entries if isinstance(e, dict) and e.get("is_dir")]
            files = [e for e in entries if isinstance(e, dict) and not e.get("is_dir")]
            readable = [
                e
                for e in files
                if e.get("is_text") and not e.get("sensitive")
            ]
            unreadable = [
                e
                for e in files
                if not e.get("is_text") or e.get("sensitive")
            ]
            facts.append(
                f"Analyse de {path} (profondeur {depth}) : {len(entries)} "
                f"entrée(s) : {len(directories)} répertoire(s), {len(files)} "
                "fichier(s)."
            )
            names = [str(e.get("name", "")) for e in files][: self.MAX_NAMES_IN_FACT]
            if names:
                suffix = " …" if len(files) > self.MAX_NAMES_IN_FACT else ""
                facts.append(f"Fichiers observés : {', '.join(names)}{suffix}.")
            if unreadable:
                facts.append(
                    f"{len(unreadable)} fichier(s) non lus (binaire, hors "
                    "texte ou sensible)."
                )
            if data.get("truncated"):
                facts.append(
                    "Listing tronqué : le nombre maximal d'entrées a été atteint."
                )
            summary = (
                f"{len(files)} fichier(s) et {len(directories)} répertoire(s) "
                f"recensés dans {path}."
            )
        elif isinstance(data, str):
            content = data
            if content.startswith("Fichier non lu") or content.startswith(
                "Fichier introuvable"
            ):
                facts.append(f"Étape {step.step_id} : {content}")
                summary = content
            elif step.tool_id == "action_read_file":
                lines = content.count("\n") + 1 if content else 0
                facts.append(
                    f"Contenu lu : {len(content)} caractère(s), {lines} ligne(s)."
                )
                summary = f"{len(content)} caractère(s) lus."
            else:
                facts.append(
                    f"Résultat de l'étape {step.step_id} : {len(content)} "
                    "caractère(s)."
                )
                summary = f"{len(content)} caractère(s) retournés."
        elif data is None:
            facts.append(f"Étape {step.step_id} : l'outil n'a retourné aucune donnée.")
            summary = "Aucune donnée retournée."
            return Observation(
                status=StepStatus.SUCCEEDED,
                facts=facts,
                summary=summary,
                progressed=False,
                signature=self._signature(data),
            )
        else:
            facts.append(
                f"Résultat de l'étape {step.step_id} : "
                f"{type(data).__name__} ({len(data) if hasattr(data, '__len__') else 'n/a'})."
            )
            summary = type(data).__name__

        return Observation(
            status=StepStatus.SUCCEEDED,
            facts=facts,
            summary=summary,
            progressed=True,
            signature=self._signature(data),
        )

    @staticmethod
    def _signature(data: Any) -> str:
        """Calculer une empreinte stable d'un résultat.

        Deux résultats identiques produisent la même signature : c'est le
        fondement de la détection de boucle.
        """
        try:
            serializable = json.dumps(data, sort_keys=True, default=str)
        except (TypeError, ValueError):
            serializable = repr(data)
        return hashlib.sha256(serializable.encode("utf-8")).hexdigest()

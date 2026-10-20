"""Génération du compte rendu d'une mission.

Le compte rendu distingue explicitement trois catégories :

1. les **faits observés** : uniquement ce qui a été constaté par un outil
   (chaque fait est rattaché à une étape) ;
2. les **erreurs** : ce qui a échoué, avec la raison ;
3. les **étapes non terminées** : ce qui n'a pas été exécuté ou n'a pas
   abouti.

Une section « analyse » peut être ajoutée : elle est produite par le
fournisseur IA à partir des faits observés et est **explicitement étiquetée
comme non vérifiée**. Elle ne peut jamais remplacer un fait observé.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from app.orchestration.models import ExecutionLimits, Mission, StepStatus


class ReportBuilder:
    """Construit le compte rendu textuel d'une mission."""

    def __init__(self, limits: Optional[ExecutionLimits] = None) -> None:
        self._limits = limits or ExecutionLimits()

    def build(
        self,
        mission: Mission,
        analyst: Optional[Callable[[Mission], str]] = None,
    ) -> str:
        """Construire le compte rendu de la mission.

        Args:
            mission : mission concerned.
            analyst : fonction optionnelle produisant une analyse
                qualitative à partir des faits observés.
        """
        lines: List[str] = []
        lines.append(f"Mission {mission.mission_id} — état : {mission.state.value}")
        lines.append(f"Objectif : {mission.objective}")
        if mission.planner:
            lines.append(f"Planificateur : {mission.planner}")
        if mission.planner_note:
            lines.append(f"Note du planificateur : {mission.planner_note}")
        lines.append("")

        lines.append("== Faits observés ==")
        if mission.facts:
            lines.extend(f"- {fact}" for fact in mission.facts)
        else:
            lines.append("- Aucun fait observé : aucune étape n'a produit de donnée.")
        lines.append("")

        lines.append("== Erreurs ==")
        if mission.errors:
            lines.extend(f"- {error}" for error in mission.errors)
        else:
            lines.append("- Aucune erreur.")
        lines.append("")

        lines.append("== Étapes non terminées ==")
        if mission.unfinished:
            lines.extend(f"- {item}" for item in mission.unfinished)
        else:
            lines.append("- Aucune : toutes les étapes prévues sont terminées.")
        lines.append("")

        if mission.plan is not None:
            lines.append("== Détail des étapes ==")
            for step in mission.plan.steps:
                status = step.status.value
                detail = step.error or step.note
                suffix = f" — {detail}" if detail else ""
                lines.append(
                    f"- {step.step_id} [{step.tool_id}] {status} : "
                    f"{step.objective}{suffix}"
                )
            lines.append("")

        analysis = ""
        if analyst is not None:
            try:
                analysis = (analyst(mission) or "").strip()
            except Exception:  # noqa: BLE001 — l'analyse ne doit pas faire échouer la mission
                analysis = ""
        if analysis:
            lines.append("== Analyse qualitative (fournisseur IA, non vérifiée) ==")
            lines.extend(f"- {line}" for line in analysis.splitlines())
            lines.append("")
        elif analyst is not None:
            lines.append("== Analyse qualitative ==")
            lines.append(
                "- Non produite : aucun fournisseur IA disponible ou réponse "
                "vide. Les faits ci-dessus suffisent."
            )
            lines.append("")

        if mission.pending is not None:
            lines.append("== Demande en attente ==")
            lines.append(f"- {mission.pending.kind} : {mission.pending.question}")
            lines.append("")

        report = "\n".join(lines)
        limit = self._limits.max_report_bytes
        if limit and len(report) > limit:
            report = report[:limit] + "\n[compte rendu tronqué]"
        return report

    @staticmethod
    def summarize_steps(mission: Mission) -> dict[str, int]:
        """Compter les étapes par statut (utile pour l'interface web)."""
        counts: dict[str, int] = {}
        if mission.plan is None:
            return counts
        for step in mission.plan.steps:
            key = step.status.value if isinstance(step.status, StepStatus) else str(step.status)
            counts[key] = counts.get(key, 0) + 1
        return counts

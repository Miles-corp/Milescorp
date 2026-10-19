"""Journal d'audit des demandes d'outils MILES.

Enregistre l'outil demandé, la décision d'autorisation et le résultat.
Ne stocke jamais de secrets, de clés API, de mots de passe ni de données
personnelles inutiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List


@dataclass
class AuditEntry:
    """Entrée unique du journal d'audit."""

    timestamp: str
    tool_id: str
    user_confirmed: bool
    permission_granted: bool
    result: str  # "success", "refused", "error", "timeout"
    error_message: str = ""
    parameters_hash: str = ""  # empreinte des paramètres (pas le contenu brut)


@dataclass
class AuditLogger:
    """Journal des demandes d'outils.

    Les entrées sont ajoutées en ordre chronologique. Le journal peut être
    vidé, mais les entrées ne sont jamais modifiées a posteriori.
    """

    entries: List[AuditEntry] = field(default_factory=list)

    def record(
        self,
        tool_id: str,
        user_confirmed: bool,
        permission_granted: bool,
        result: str,
        error_message: str = "",
        parameters_hash: str = "",
    ) -> None:
        """Ajouter une entrée au journal."""
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool_id=tool_id,
            user_confirmed=user_confirmed,
            permission_granted=permission_granted,
            result=result,
            error_message=error_message,
            parameters_hash=parameters_hash,
        )
        self.entries.append(entry)

    def get_entries(self) -> List[AuditEntry]:
        """Retourner une copie de toutes les entrées du journal."""
        return list(self.entries)

    def clear(self) -> None:
        """Vider le journal d'audit."""
        self.entries.clear()

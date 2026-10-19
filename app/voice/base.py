"""Package vocal optionnel de MILES.

Ce composant est isolé : s'il n'est pas disponible, le programme fonctionne
normalement en mode texte. Aucune dépendance vocale n'est requise pour démarrer.
"""

from __future__ import annotations


class VoiceUnavailableError(Exception):
    """Le composant vocal n'est pas disponible."""


class VoiceInterface:
    """Interface vocale optionnelle (reconnaissance + synthèse).

    Dans cette première version, la voix est documentée mais non activée
    par défaut. Les méthodes lèvent VoiceUnavailableError si les
    dépendances ne sont pas installées.
    """

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled and self._check_dependencies()
        if enabled and not self.enabled:
            raise VoiceUnavailableError(
                "Dépendances vocales non installées. "
                "Le programme fonctionne en mode texte uniquement."
            )

    def _check_dependencies(self) -> bool:
        """Vérifier si les dépendances vocales sont importables."""
        try:
            import pyttsx3  # noqa: F401 — vérification de présence uniquement
            import speech_recognition  # noqa: F401 — vérification de présence uniquement
            return True
        except ImportError:
            return False

    def speak(self, text: str) -> None:
        """Synthétiser le texte en parole (si disponible)."""
        if not self.enabled:
            raise VoiceUnavailableError("Interface vocale non activée.")
        # Implémentation réelle à ajouter quand pyttsx3 est disponible
        raise VoiceUnavailableError("Synthèse vocale non encore implémentée.")

    def listen(self) -> str:
        """Écouter et retourner le texte reconnu (si disponible)."""
        if not self.enabled:
            raise VoiceUnavailableError("Interface vocale non activée.")
        raise VoiceUnavailableError("Reconnaissance vocale non encore implémentée.")

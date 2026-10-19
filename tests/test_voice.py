"""Tests de l'interface vocale optionnelle (VoiceInterface).

Ces tests vérifient que :
- VoiceInterface désactivée ne lève pas d'erreur à l'instanciation.
- VoiceInterface activée sans dépendances lève VoiceUnavailableError.
- speak() et listen() lèvent VoiceUnavailableError quand la voix est désactivée.
- Aucune dépendance vocale n'est requise pour le mode texte.
"""

from __future__ import annotations

import unittest

from app.voice.base import VoiceInterface, VoiceUnavailableError


class TestVoiceInterfaceDisabled(unittest.TestCase):
    """VoiceInterface avec enabled=False (mode texte par défaut)."""

    def test_voice_disabled_no_error(self) -> None:
        voice = VoiceInterface(enabled=False)
        self.assertEqual(voice.enabled, False)

    def test_speak_raises_when_disabled(self) -> None:
        voice = VoiceInterface(enabled=False)
        with self.assertRaises(VoiceUnavailableError):
            voice.speak("Bonjour")

    def test_listen_raises_when_disabled(self) -> None:
        voice = VoiceInterface(enabled=False)
        with self.assertRaises(VoiceUnavailableError):
            voice.listen()


class TestVoiceInterfaceEnabledWithoutDeps(unittest.TestCase):
    """VoiceInterface avec enabled=True mais sans dépendances installées."""

    def test_voice_enabled_raises_when_deps_missing(self) -> None:
        """Sur ce poste, pyttsx3 et speech_recognition ne sont pas installés."""
        with self.assertRaises(VoiceUnavailableError):
            VoiceInterface(enabled=True)


class TestVoiceUnavailableError(unittest.TestCase):
    """Vérifier que VoiceUnavailableError est bien une Exception."""

    def test_is_exception(self) -> None:
        self.assertTrue(issubclass(VoiceUnavailableError, Exception))

    def test_can_catch(self) -> None:
        try:
            raise VoiceUnavailableError("test")
        except VoiceUnavailableError:
            pass  # attendu


if __name__ == "__main__":
    unittest.main()

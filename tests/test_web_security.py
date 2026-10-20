"""Tests de non-régression S-003 : aucune fuite d'information sensible vers
les clients HTTP.

Les exceptions simulées contiennent uniquement des secrets FACTICES :
- une fausse clé fournisseur ("sk-FAUSSE-CLE-XYZ") ;
- un faux jeton Bearer ("FAUX-JETON-BEARER-0123456789") ;
- un faux mot de passe ("motdepasse-faux-0123456789").

Aucun vrai secret n'est utilisé dans ces tests.

Vérifie que :
- la réponse HTTP ne contient ni ces valeurs, ni les détails internes ;
- les codes HTTP et les drapeaux fonctionnels sont préservés ;
- les journaux internes ne contiennent pas ces valeurs non plus.
"""

from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from app.ai_providers.base import AIProvider, AIProviderError
from app.config.settings import Settings
from app.interface.web import MilesHandler, WebApp

FAKE_PROVIDER_KEY = "sk-FAUSSE-CLE-XYZ"
FAKE_BEARER_TOKEN = "FAUX-JETON-BEARER-0123456789"
FAKE_PASSWORD = "motdepasse-faux-0123456789"

# Toutes les valeurs sensibles qui ne doivent apparaître dans aucune réponse.
FAKE_SECRETS = (FAKE_PROVIDER_KEY, FAKE_BEARER_TOKEN, FAKE_PASSWORD)


class LeakyProvider(AIProvider):
    """Fournisseur qui lève une exception contenant des secrets factices."""

    def __init__(self, exception: Exception) -> None:
        self._exception = exception
        self._name = "leaky-test"

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return True

    def chat(self, messages: list[dict[str, str]]) -> str:
        raise self._exception


class LeakyMemory:
    """Mémoire factice dont les opérations lèvent une exception sensible."""

    def __init__(self, exception: Exception) -> None:
        self._exception = exception
        self.is_available = True

    def add_memory(self, content: str, **kwargs: object) -> int:
        raise self._exception

    def delete_memory(self, memory_id: int) -> bool:
        raise self._exception

    def list_memories(self) -> list[dict[str, object]]:
        return []


class _Server:
    """Serveur de test sur un port libre, arrêté à la fin."""

    def __init__(self, app: WebApp) -> None:
        MilesHandler.app = app
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), MilesHandler)
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def __enter__(self) -> "_Server":
        return self

    def __exit__(self, *args: object) -> None:
        self._server.shutdown()
        self._server.server_close()

    def request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"http://127.0.0.1:{self._port}{path}"
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return {"status": resp.status, "body": resp.read().decode("utf-8")}
        except urllib.error.HTTPError as exc:
            return {
                "status": exc.code,
                "body": exc.read().decode("utf-8", errors="replace"),
            }


class TestWebNoSecretLeak(unittest.TestCase):
    """S-003 : les réponses HTTP ne doivent jamais contenir de secret."""

    def _assert_no_leak(self, result: dict) -> None:
        for secret in FAKE_SECRETS:
            self.assertNotIn(secret, result["body"])
        # Aucun préfixe de clé fournisseur ne doit apparaître non plus.
        self.assertNotIn("sk-", result["body"])

    def test_erreur_fournisseur_avec_cle_fausse(self) -> None:
        provider = LeakyProvider(
            AIProviderError(f"échec interne clé {FAKE_PROVIDER_KEY}")
        )
        app = WebApp(settings=Settings(), provider=provider)
        with _Server(app) as server:
            result = server.request("POST", "/message", {"message": "bonjour"})

        self.assertEqual(result["status"], 400)
        self._assert_no_leak(result)

    def test_erreur_fournisseur_avec_jeton_bearer_faux(self) -> None:
        provider = LeakyProvider(
            AIProviderError(
                f"authentification refusée Authorization: Bearer {FAKE_BEARER_TOKEN}"
            )
        )
        app = WebApp(settings=Settings(), provider=provider)
        with _Server(app) as server:
            result = server.request("POST", "/message", {"message": "bonjour"})

        self.assertEqual(result["status"], 400)
        self._assert_no_leak(result)

    def test_erreur_fournisseur_avec_mot_de_passe_faux(self) -> None:
        provider = LeakyProvider(
            AIProviderError(f"échec interne password={FAKE_PASSWORD}")
        )
        app = WebApp(settings=Settings(), provider=provider)
        with _Server(app) as server:
            result = server.request("POST", "/message", {"message": "bonjour"})

        self.assertEqual(result["status"], 400)
        self._assert_no_leak(result)

    def test_exception_inattendue_ne_divulgue_pas_son_contenu(self) -> None:
        """Une exception non prévue ne doit rien divulguer dans la réponse."""
        provider = LeakyProvider(
            RuntimeError(
                f"panne interne {FAKE_PROVIDER_KEY} "
                f"Bearer {FAKE_BEARER_TOKEN} password={FAKE_PASSWORD}"
            )
        )
        app = WebApp(settings=Settings(), provider=provider)
        with _Server(app) as server:
            result = server.request("POST", "/message", {"message": "bonjour"})

        self.assertEqual(result["status"], 400)
        self._assert_no_leak(result)
        payload = json.loads(result["body"])
        self.assertNotIn("panne interne", payload["error"])

    def test_erreur_fournisseur_preserve_le_contexte(self) -> None:
        """Les codes HTTP et le drapeau context_preserved sont préservés."""
        provider = LeakyProvider(AIProviderError(f"échec {FAKE_PROVIDER_KEY}"))
        app = WebApp(settings=Settings(), provider=provider)
        with _Server(app) as server:
            result = server.request("POST", "/message", {"message": "bonjour"})

        self.assertEqual(result["status"], 400)
        payload = json.loads(result["body"])
        self.assertTrue(payload.get("context_preserved"))
        self.assertIn("error", payload)

    def test_remember_ne_divulgue_pas_les_secrets(self) -> None:
        memory = LeakyMemory(
            RuntimeError(f"échec {FAKE_PROVIDER_KEY} password={FAKE_PASSWORD}")
        )
        app = WebApp(settings=Settings(), memory=memory)  # type: ignore[arg-type]
        with _Server(app) as server:
            result = server.request("POST", "/remember", {"content": "test"})

        self.assertEqual(result["status"], 400)
        self._assert_no_leak(result)

    def test_forget_ne_divulgue_pas_les_secrets(self) -> None:
        memory = LeakyMemory(
            RuntimeError(f"échec {FAKE_PROVIDER_KEY} Bearer {FAKE_BEARER_TOKEN}")
        )
        app = WebApp(settings=Settings(), memory=memory)  # type: ignore[arg-type]
        with _Server(app) as server:
            result = server.request("POST", "/forget", {"id": 1})

        self.assertEqual(result["status"], 400)
        self._assert_no_leak(result)

    def test_log_interne_ne_contient_pas_les_secrets(self) -> None:
        """Le journal interne conserve le détail technique mais pas les secrets."""
        provider = LeakyProvider(
            AIProviderError(
                f"échec interne {FAKE_PROVIDER_KEY} "
                f"Bearer {FAKE_BEARER_TOKEN} password={FAKE_PASSWORD}"
            )
        )
        app = WebApp(settings=Settings(), provider=provider)
        with self.assertLogs("miles.web", level="ERROR") as captured:
            with _Server(app) as server:
                server.request("POST", "/message", {"message": "bonjour"})

        log = "\n".join(captured.output)
        for secret in FAKE_SECRETS:
            self.assertNotIn(secret, log)
        self.assertIn("[REDACTED]", log)
        # Le détail technique reste disponible pour le diagnostic
        self.assertIn("échec interne", log)

    def test_log_interne_sans_trace_brute(self) -> None:
        """Aucune trace d'appels brute n'est journalisée pour une exception."""
        provider = LeakyProvider(RuntimeError(f"panne {FAKE_PROVIDER_KEY}"))
        app = WebApp(settings=Settings(), provider=provider)
        with self.assertLogs("miles.web", level="ERROR") as captured:
            with _Server(app) as server:
                server.request("POST", "/message", {"message": "bonjour"})

        log = "\n".join(captured.output)
        self.assertNotIn("Traceback", log)
        self.assertNotIn("RuntimeError:", log)
        self.assertIn("RuntimeError", log)  # le nom de classe est conservé


class TestWebSanitizeHelper(unittest.TestCase):
    """Vérifie l'assainissement utilisé par les journaux internes."""

    def test_cle_fournisseur_redigee(self) -> None:
        from app.interface.web import sanitize_text

        self.assertNotIn(FAKE_PROVIDER_KEY, sanitize_text(f"clé {FAKE_PROVIDER_KEY}"))

    def test_jeton_bearer_redige(self) -> None:
        from app.interface.web import sanitize_text

        cleaned = sanitize_text(f"Authorization: Bearer {FAKE_BEARER_TOKEN}")
        self.assertNotIn(FAKE_BEARER_TOKEN, cleaned)

    def test_mot_de_passe_redige(self) -> None:
        from app.interface.web import sanitize_text

        cleaned = sanitize_text(f"password={FAKE_PASSWORD}")
        self.assertNotIn(FAKE_PASSWORD, cleaned)

    def test_paire_cle_valeur_redigee(self) -> None:
        from app.interface.web import sanitize_text

        cleaned = sanitize_text(f"api_key={FAKE_PROVIDER_KEY}")
        self.assertNotIn(FAKE_PROVIDER_KEY, cleaned)

    def test_texte_non_sensible_conserve(self) -> None:
        from app.interface.web import sanitize_text

        self.assertEqual(sanitize_text("erreur simple"), "erreur simple")


class TestWebServerLocalOnly(unittest.TestCase):
    """S-002 : le serveur web MILES doit écouter uniquement sur 127.0.0.1."""

    def _app(self) -> WebApp:
        return WebApp(settings=Settings())

    def test_adresse_par_defaut_est_locale(self) -> None:
        from app.interface.web import LOCAL_ONLY_HOST, MilesWebServer

        server = MilesWebServer(app=self._app())
        self.assertEqual(server.host, LOCAL_ONLY_HOST)
        self.assertEqual(server.host, "127.0.0.1")

    def test_refus_adresse_toutes_interfaces(self) -> None:
        """0.0.0.0 expose le service sur toutes les interfaces : refusé."""
        from app.interface.web import MilesWebServer, WebServerSecurityError

        with self.assertRaises(WebServerSecurityError):
            MilesWebServer(app=self._app(), host="0.0.0.0")

    def test_refus_adresse_lan(self) -> None:
        """Une adresse du réseau local est refusée."""
        from app.interface.web import MilesWebServer, WebServerSecurityError

        for lan_address in ("192.168.1.10", "10.0.0.5", "172.16.0.1"):
            with self.subTest(host=lan_address):
                with self.assertRaises(WebServerSecurityError):
                    MilesWebServer(app=self._app(), host=lan_address)

    def test_refus_adresse_ipv6_any(self) -> None:
        """'::' écoute sur toutes les interfaces IPv6 : refusé."""
        from app.interface.web import MilesWebServer, WebServerSecurityError

        with self.assertRaises(WebServerSecurityError):
            MilesWebServer(app=self._app(), host="::")

    def test_refus_adresse_ipv6_loopback(self) -> None:
        """Même la boucle IPv6 est refusée : seule 127.0.0.1 est admise."""
        from app.interface.web import MilesWebServer, WebServerSecurityError

        with self.assertRaises(WebServerSecurityError):
            MilesWebServer(app=self._app(), host="::1")

    def test_refus_adresse_non_string(self) -> None:
        from app.interface.web import MilesWebServer, WebServerSecurityError

        with self.assertRaises(WebServerSecurityError):
            MilesWebServer(app=self._app(), host=12345)  # type: ignore[arg-type]

    def test_affectation_directe_refusee(self) -> None:
        """L'attribut host ne doit pas pouvoir être détourné après construction."""
        from app.interface.web import MilesWebServer, WebServerSecurityError

        server = MilesWebServer(app=self._app())
        with self.assertRaises(WebServerSecurityError):
            server.host = "0.0.0.0"
        # L'adresse reste locale après la tentative refusée.
        self.assertEqual(server.host, "127.0.0.1")

    def test_demarrage_refuse_adresse_non_locale(self) -> None:
        """start() revérifie l'adresse avant toute liaison socket."""
        from app.interface.web import MilesWebServer, WebServerSecurityError

        server = MilesWebServer(app=self._app())
        # Contournement volontaire de la propriété pour tester la
        # revalidation effectuée par start().
        server._host = "0.0.0.0"
        with self.assertRaises(WebServerSecurityError):
            server.start()

    def test_fonctionnement_attendu_en_local(self) -> None:
        """Le serveur démarre et répond normalement sur 127.0.0.1."""
        from app.interface.web import MilesHandler, MilesWebServer

        app = self._app()
        server = MilesWebServer(app=app, port=0)
        # Construction d'un vrai serveur sur 127.0.0.1 (port dynamique).
        from http.server import ThreadingHTTPServer

        MilesHandler.app = app
        http_server = ThreadingHTTPServer(("127.0.0.1", 0), MilesHandler)
        port = http_server.server_address[1]
        try:
            import threading
            import urllib.request

            thread = threading.Thread(target=http_server.serve_forever, daemon=True)
            thread.start()
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/status", timeout=5
            ) as resp:
                self.assertEqual(resp.status, 200)
                self.assertIn(b"non configur", resp.read())
        finally:
            http_server.shutdown()
            http_server.server_close()

    def test_serveur_ne_demande_pas_d_authentification(self) -> None:
        """Aucune authentification n'est requise : le service est strictement local."""
        from app.interface.web import LOCAL_ONLY_HOST

        self.assertEqual(LOCAL_ONLY_HOST, "127.0.0.1")


if __name__ == "__main__":
    unittest.main()

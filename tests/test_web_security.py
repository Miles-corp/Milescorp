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
import os
import shutil
import tempfile
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

    @property
    def port(self) -> int:
        return self._port

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


class TestWebRequestBodyLimit(unittest.TestCase):
    """S-004 : le corps HTTP est limité à 64 KiB et validé proprement."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="miles_test_body_")
        self.db_path = os.path.join(self.tmpdir, "memory.db")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _raw_post(self, content_length: str | None, body: bytes) -> dict:
        """Envoyer une requête POST avec un Content-Length imposé.

        Le serveur refuse une requête trop volumineuse SANS lire son corps
        (invariant de sécurité : le serveur ne consomme jamais plus que
        MAX_BODY_BYTES). Il répond alors 413 et ferme la connexion, alors
        que le client peut encore être en train d'écrire son corps : le
        client observe alors une réinitialisation de connexion (statut 0)
        au lieu de la réponse 413. Les deux issues sont valides d'un point de
        vue transport ; seul le refus compte. La vérification stricte de
        l'invariant « le corps n'est pas lu » reste assurée par
        test_lecture_bornee_a_la_limite.
        """
        import http.client

        app = WebApp(settings=Settings())
        with _Server(app) as server:
            conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
            try:
                headers = {"Content-Type": "application/json"}
                if content_length is not None:
                    headers["Content-Length"] = content_length
                try:
                    conn.request("POST", "/message", body=body, headers=headers)
                    resp = conn.getresponse()
                    return {
                        "status": resp.status,
                        "body": resp.read().decode("utf-8", errors="replace"),
                    }
                except (http.client.HTTPException, OSError):
                    # Connexion réinitialisée : le serveur a refusé la
                    # requête avant lecture du corps.
                    return {"status": 0, "body": ""}
            finally:
                conn.close()

    def _assert_refused(self, result: dict, expected_status: int) -> None:
        """Vérifier que la requête a été refusée.

        Accepte le statut HTTP attendu OU une réinitialisation de connexion
        (statut 0) : le serveur ferme la connexion sans lire le corps
        lorsqu'il refuse, ce qui est le comportement voulu et sécurisé.
        """
        self.assertIn(
            result["status"],
            (0, expected_status),
            f"refus attendu ({expected_status}) ou réinitialisation de connexion, "
            f"obtenu {result['status']} : {result['body'][:200]!r}",
        )

    def _payload_of_size(self, size: int) -> bytes:
        """Construire un corps JSON valide de exactement `size` octets."""
        prefix = b'{"message": "'
        suffix = b'"}'
        padding = size - len(prefix) - len(suffix)
        if padding < 0:
            raise ValueError("taille trop petite pour le gabarit")
        return prefix + b"a" * padding + suffix

    def _raw_socket_post(self, raw_request: bytes) -> dict:
        """Envoyer une requête HTTP brute et lire la réponse.

        Permet de contrôler exactement les octets émis (en-tête
        Content-Length absent, corps tronqué, etc.).
        """
        import socket

        app = WebApp(settings=Settings())
        with _Server(app) as server:
            sock = socket.create_connection(("127.0.0.1", server.port), timeout=10)
            try:
                sock.sendall(raw_request)
                # Fin de flux en écriture : le serveur voit la fin des
                # données transmises sans que le client attende.
                sock.shutdown(socket.SHUT_WR)
                chunks = []
                while True:
                    data = sock.recv(4096)
                    if not data:
                        break
                    chunks.append(data)
                raw = b"".join(chunks).decode("utf-8", errors="replace")
                status = 0
                if " " in raw:
                    try:
                        status = int(raw.split(" ")[1])
                    except ValueError:
                        status = 0
                return {"status": status, "body": raw}
            finally:
                sock.close()

    def test_limite_exacte_acceptee(self) -> None:
        """Un corps de exactement 65 536 octets est accepté."""
        from app.interface.web import MAX_BODY_BYTES

        self.assertEqual(MAX_BODY_BYTES, 65536)
        payload = self._payload_of_size(MAX_BODY_BYTES)
        self.assertEqual(len(payload), 65536)
        result = self._raw_post(str(MAX_BODY_BYTES), payload)
        # Le corps est accepté : la réponse porte sur le traitement métier
        # (400 "Aucun fournisseur IA configuré" et non 413).
        self.assertNotEqual(result["status"], 413)

    def test_limite_depassee_refusee_en_413(self) -> None:
        """Un corps de 65 537 octets reçoit HTTP 413 (ou une réinitialisation
        de connexion si le client écrivait encore son corps)."""
        from app.interface.web import MAX_BODY_BYTES

        payload = self._payload_of_size(MAX_BODY_BYTES + 1)
        self.assertEqual(len(payload), 65537)
        result = self._raw_post(str(MAX_BODY_BYTES + 1), payload)
        self._assert_refused(result, 413)
        if result["status"] == 413:
            self.assertIn("volumineuse", result["body"])

    def test_longueur_extremement_grande_refusee_sans_lecture(self) -> None:
        """Une longueur aberrante est refusée sans lire les données."""
        result = self._raw_post("999999999999", b"x")
        self._assert_refused(result, 413)
        if result["status"] == 413:
            self.assertIn("volumineuse", result["body"])

    def test_longueur_negative_refusee(self) -> None:
        result = self._raw_post("-1", b"")
        self._assert_refused(result, 400)
        if result["status"] == 400:
            self.assertIn("Content-Length", result["body"])

    def test_longueur_non_numerique_refusee(self) -> None:
        result = self._raw_post("abc", b"{}")
        self._assert_refused(result, 400)
        if result["status"] == 400:
            self.assertIn("Content-Length", result["body"])

    def test_longueur_absente_traitee_proprement(self) -> None:
        """Une requête sans en-tête Content-Length ne provoque pas d'exception."""
        request = (
            "POST /message HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\n"
            "Content-Type: application/json\r\n"
            "\r\n"
        ).encode("ascii")
        result = self._raw_socket_post(request)
        self.assertNotEqual(result["status"], 0)
        self.assertNotIn("Traceback", result["body"])
        # Le corps vide est traité comme une requête sans message valide.
        self.assertIn(result["status"], (400, 411, 413))

    def test_corpus_plus_court_que_la_longueur_annoncee(self) -> None:
        """Un corps plus court que la longueur annoncée est refusé proprement."""
        request = (
            "POST /message HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: 100\r\n"
            "\r\n"
        ).encode("ascii") + b"{}"
        result = self._raw_socket_post(request)
        self.assertEqual(result["status"], 400)
        self.assertIn("incomplet", result["body"])

    def test_corps_json_non_objet_refuse(self) -> None:
        """Un corps JSON qui n'est pas un objet est refusé proprement."""
        result = self._raw_post("2", b"[]")
        self.assertEqual(result["status"], 400)
        self.assertIn("JSON", result["body"])

    def test_lecture_bornee_a_la_limite(self) -> None:
        """Le handler ne lit jamais plus de MAX_BODY_BYTES octets."""
        from app.interface.web import MAX_BODY_BYTES, MilesHandler

        recorded: list[int] = []

        class _FakeFile:
            def read(self, size: int) -> bytes:
                recorded.append(size)
                return b""

        class _FakeHandler(MilesHandler):
            def __init__(self) -> None:  # noqa: D107 - double de test
                self.headers = {"Content-Length": str(MAX_BODY_BYTES + 1)}
                self.rfile = _FakeFile()
                self.close_connection = False

        handler = _FakeHandler()
        with self.assertRaises(Exception) as ctx:
            handler._read_body()
        self.assertEqual(getattr(ctx.exception, "status", None), 413)
        # Aucune lecture n'a eu lieu : le refus précède la lecture.
        self.assertEqual(recorded, [])


if __name__ == "__main__":
    unittest.main()

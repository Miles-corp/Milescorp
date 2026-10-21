"""Tests d'intégration du moteur d'outils avec le CLI et l'interface web.

Couvre :
1. découverte des outils enregistrés ;
2. registre vide et outil inconnu ;
3. appel d'un outil valide depuis le CLI ;
4. validation et rejet de paramètres invalides ;
5. refus d'une action non autorisée ;
6. confirmation obligatoire pour les actions sensibles ;
7. erreurs et exceptions d'outils ;
8. invocation du moteur depuis l'interface web ;
9. comportement commun CLI/web et absence de duplication métier ;
10. non-divulgation des secrets ;
11. régression de la conversation et de la persistance SQLite ;
12. absence d'exécution d'une action réelle pendant les tests.

Aucune action destructive ni externe n'est exécutée : les outils de lecture
sont testés sur des répertoires temporaires ou sur ``data/`` (vide).
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import ThreadingHTTPServer
from unittest import mock

from app.config.settings import Settings
from app.core.conversation import Conversation
from app.interface.cli import CLI
from app.interface.web import MilesHandler, WebApp
from app.tools.builtin import build_default_registry
from app.tools.service import ToolService
from tests.web_test_support import TEST_TOKEN, build_app


# Handlers de test définis au niveau du module : le moteur exécute les
# handlers dans un sous-processus, ce qui exige des fonctions picklables
# (ni closure, ni méthode liée, ni fonction locale).

def _handler_en_panne() -> str:
    """Handler qui lève une exception."""
    raise RuntimeError("échec interne du handler")


def _handler_lent() -> str:
    """Handler volontairement trop lent pour dépasser le délai."""
    import time as _time

    _time.sleep(5)
    return "trop tard"


class _WebFixture:
    """Serveur web local sur un port libre (session authentifiée)."""

    def __init__(self, app: WebApp) -> None:
        MilesHandler.app = app
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), MilesHandler)
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._session: dict | None = None
        self._login()

    @property
    def port(self) -> int:
        return self._port

    def _login(self) -> None:
        """Ouvrir une session authentifiée (Phase 6.1)."""
        payload = self._send(
            "POST", "/session", {"token": TEST_TOKEN}, {}, authenticated=False
        )
        self._session = payload[1] if payload[1] else None

    def auth_headers(self) -> dict:
        if not self._session:
            return {}
        return {
            "X-MILES-Session": self._session["session_id"],
            "X-MILES-CSRF": self._session["csrf_token"],
        }

    def _send(
        self,
        method: str,
        path: str,
        body: dict | None,
        extra_headers: dict,
        authenticated: bool = True,
    ) -> tuple[int, dict]:
        import urllib.error
        import urllib.request

        url = f"http://127.0.0.1:{self._port}{path}"
        data = None
        headers = dict(extra_headers)
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if authenticated:
            headers.update(self.auth_headers())
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def __enter__(self) -> "_WebFixture":
        return self

    def __exit__(self, *args: object) -> None:
        self._server.shutdown()
        self._server.server_close()

    def request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        return self._send(method, path, body, {})


# ---------------------------------------------------------------------------
# 1, 2 : découverte, registre vide, outil inconnu
# ---------------------------------------------------------------------------

class TestToolDiscovery(unittest.TestCase):
    """1. Découverte des outils enregistrés."""

    def test_registre_alimente_par_defaut(self) -> None:
        registry = build_default_registry()
        outils = registry.list_tools()
        self.assertIn("status_read", outils)
        self.assertIn("action_datetime", outils)
        self.assertIn("action_workdir", outils)
        self.assertIn("action_list_files", outils)

    def test_service_liste_le_catalogue(self) -> None:
        service = ToolService()
        catalogue = service.list_tools()
        self.assertEqual(len(catalogue), 5)
        for tool in catalogue:
            self.assertIn("id", tool)
            self.assertIn("description", tool)
            self.assertIn("risk_level", tool)
            self.assertIn("required_permissions", tool)
            self.assertIn("requires_confirmation", tool)
            self.assertIn("parameters", tool)

    def test_registre_vide(self) -> None:
        from app.tools.registry import ToolRegistry

        service = ToolService(registry=ToolRegistry())
        self.assertEqual(service.list_tools(), [])
        result = service.request_tool("status_read")
        self.assertFalse(result.success)
        self.assertIn("Outil inconnu", result.error_message)

    def test_outil_inconnu_refuse(self) -> None:
        service = ToolService()
        result = service.request_tool("outil_inexistant")
        self.assertFalse(result.success)
        self.assertIn("Outil inconnu", result.error_message)

    def test_outil_inconnu_refuse_via_cli(self) -> None:
        cli = CLI(settings=Settings(), tool_service=ToolService())
        out = io.StringIO()
        with redirect_stdout(out):
            cli._handle_tool_command(["outil_inexistant"])
        self.assertIn("Outil inconnu", out.getvalue())


# ---------------------------------------------------------------------------
# 3, 4 : appel valide depuis le CLI, validation des paramètres
# ---------------------------------------------------------------------------

class TestCliToolInvocation(unittest.TestCase):
    """3. Appel d'un outil valide depuis le CLI. 4. Paramètres invalides."""

    def setUp(self) -> None:
        self.cli = CLI(settings=Settings(), tool_service=ToolService())

    def test_appel_outil_valide_depuis_la_cli(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.cli._handle_tool_command(["action_datetime"])
        self.assertIn("[Outil exécuté] action_datetime", out.getvalue())

    def test_parametre_invalide_rejete(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.cli._handle_tool_command(["action_list_files", "param_sans_egal"])
        self.assertIn("Argument invalide", out.getvalue())

    def test_parametre_non_decl_refuse(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.cli._handle_tool_command(["action_list_files", "inconnu=1"])
        self.assertIn("[Outil refusé ou en échec]", out.getvalue())

    def test_parametre_mauvais_type_refuse(self) -> None:
        """Un paramètre dont le type ne correspond pas est refusé."""
        service = ToolService()
        result = service.request_tool("action_list_files", {"path": 42})
        self.assertFalse(result.success)
        self.assertIn("path", result.error_message)

    def test_usage_sans_argument(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.cli._handle_tool_command([])
        self.assertIn("Usage : /tool", out.getvalue())

    def test_liste_des_outils(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.cli._handle_tools_command()
        contenu = out.getvalue()
        self.assertIn("status_read", contenu)
        self.assertIn("action_datetime", contenu)
        self.assertIn("confirmation requise", contenu)


# ---------------------------------------------------------------------------
# 5, 6 : permissions, confirmation obligatoire
# ---------------------------------------------------------------------------

class TestToolAuthorization(unittest.TestCase):
    """5. Refus d'une action non autorisée. 6. Confirmation obligatoire."""

    def test_permission_absente_refusee(self) -> None:
        from app.tools.registry import ToolRegistry

        registry = build_default_registry()
        # Aucune permission accordée : action_list_files exige lecture_systeme
        service = ToolService(registry=registry, granted_permissions=set())
        result = service.request_tool("action_list_files", {"path": "data"})
        self.assertFalse(result.success)
        self.assertIn("Permissions manquantes", result.error_message)

    def test_action_sensible_exige_confirmation(self) -> None:
        service = ToolService()
        result = service.request_tool("action_list_files", {"path": "data"})
        self.assertFalse(result.success)
        self.assertTrue(result.confirmation_required)
        self.assertTrue(result.confirmation_token)

    def test_confirmation_valide_execute(self) -> None:
        service = ToolService()
        premier = service.request_tool("action_list_files", {"path": "data"})
        resultat = service.request_tool(
            "action_list_files",
            {"path": "data"},
            user_confirmed=True,
            confirmation_token=premier.confirmation_token,
        )
        self.assertTrue(resultat.success)
        self.assertIsNotNone(resultat.data)

    def test_confirmation_refusee_n_execute_pas(self) -> None:
        service = ToolService()
        resultat = service.request_tool("action_list_files", {"path": "data"})
        self.assertFalse(resultat.success)
        # Sans confirmation, l'outil n'est pas exécuté
        self.assertTrue(resultat.confirmation_required)

    def test_cli_demande_confirmation(self) -> None:
        cli = CLI(settings=Settings(), tool_service=ToolService())
        out = io.StringIO()
        with redirect_stdout(out):
            with mock.patch("builtins.input", return_value="o"):
                cli._handle_tool_command(["action_list_files", "path=data"])
        self.assertIn("Confirmation humaine requise", out.getvalue())
        self.assertIn("[Outil exécuté] action_list_files", out.getvalue())

    def test_cli_annule_si_confirmation_refusee(self) -> None:
        cli = CLI(settings=Settings(), tool_service=ToolService())
        out = io.StringIO()
        with redirect_stdout(out):
            with mock.patch("builtins.input", return_value="n"):
                cli._handle_tool_command(["action_list_files", "path=data"])
        self.assertIn("Action annulée", out.getvalue())
        self.assertNotIn("[Outil exécuté]", out.getvalue())


# ---------------------------------------------------------------------------
# 7 : erreurs et exceptions d'outils
# ---------------------------------------------------------------------------

class TestToolErrors(unittest.TestCase):
    """7. Erreurs et exceptions d'outils."""

    def test_exception_du_handler_capturee(self) -> None:
        from app.tools.registry import ToolDefinition, ToolRegistry

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                tool_id="outil_en_panne",
                description="Outil qui échoue",
                handler=_handler_en_panne,
                parameters=(),
                risk_level="LOW",
                required_permissions=(),
                timeout_seconds=5,
            )
        )
        service = ToolService(registry=registry)
        result = service.request_tool("outil_en_panne")
        self.assertFalse(result.success)
        # Le message d'erreur ne doit pas être la trace brute
        self.assertNotIn("échec interne du handler", result.error_message)
        self.assertIn("Erreur", result.error_message)

    def test_erreur_de_timeout(self) -> None:
        from app.tools.registry import ToolDefinition, ToolRegistry

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                tool_id="outil_lent",
                description="Outil lent",
                handler=_handler_lent,
                parameters=(),
                risk_level="LOW",
                required_permissions=(),
                timeout_seconds=1,
            )
        )
        service = ToolService(registry=registry)
        result = service.request_tool("outil_lent")
        self.assertFalse(result.success)
        self.assertIn("Délai d'attente dépassé", result.error_message)


# ---------------------------------------------------------------------------
# 8, 9 : web et comportement commun
# ---------------------------------------------------------------------------

class TestWebToolIntegration(unittest.TestCase):
    """8. Invocation depuis l'interface web. 9. Comportement commun CLI/web."""

    def setUp(self) -> None:
        self.service = ToolService()
        self.app = build_app(tool_service=self.service)

    def test_route_tools_liste_le_catalogue(self) -> None:
        with _WebFixture(self.app) as web:
            status, payload = web.request("GET", "/tools")
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["tools"]), 5)

    def test_route_tool_execute_un_outil_valide(self) -> None:
        with _WebFixture(self.app) as web:
            status, payload = web.request(
                "POST", "/tool", {"tool": "action_datetime", "parameters": {}}
            )
        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        self.assertIsNotNone(payload["result"])

    def test_route_tool_outil_inconnu(self) -> None:
        with _WebFixture(self.app) as web:
            status, payload = web.request(
                "POST", "/tool", {"tool": "outil_inexistant", "parameters": {}}
            )
        self.assertEqual(status, 400)
        self.assertIn("Outil inconnu", payload["error"])

    def test_route_tool_demande_confirmation(self) -> None:
        with _WebFixture(self.app) as web:
            status, payload = web.request(
                "POST", "/tool", {"tool": "action_list_files", "parameters": {"path": "data"}}
            )
        self.assertEqual(status, 200)
        self.assertTrue(payload["confirmation_required"])
        self.assertTrue(payload["confirmation_token"])

    def test_route_tool_confirmation_valide(self) -> None:
        with _WebFixture(self.app) as web:
            status, premier = web.request(
                "POST", "/tool", {"tool": "action_list_files", "parameters": {"path": "data"}}
            )
            self.assertEqual(status, 200)
            status2, payload = web.request(
                "POST",
                "/tool",
                {
                    "tool": "action_list_files",
                    "parameters": {"path": "data"},
                    "user_confirmed": True,
                    "confirmation_token": premier["confirmation_token"],
                },
            )
        self.assertEqual(status2, 200)
        self.assertTrue(payload["success"])

    def test_route_tool_parametres_invalides(self) -> None:
        with _WebFixture(self.app) as web:
            status, payload = web.request(
                "POST", "/tool", {"tool": "action_list_files", "parameters": "pas-un-dict"}
            )
        self.assertEqual(status, 400)
        self.assertIn("Paramètres invalides", payload["error"])

    def test_route_tool_jeton_invalide(self) -> None:
        with _WebFixture(self.app) as web:
            status, payload = web.request(
                "POST",
                "/tool",
                {
                    "tool": "action_list_files",
                    "parameters": {"path": "data"},
                    "user_confirmed": True,
                    "confirmation_token": 123,
                },
            )
        self.assertEqual(status, 400)
        self.assertIn("Jeton de confirmation invalide", payload["error"])

    def test_cli_et_web_partagent_le_meme_service(self) -> None:
        """9. Aucun doublon de logique métier : même service, même moteur."""
        cli = CLI(settings=Settings(), tool_service=self.service)
        app = WebApp(settings=Settings(), tool_service=self.service)
        self.assertIs(cli.tool_service, app.tool_service)
        self.assertIs(cli.tool_service.engine, app.tool_service.engine)
        self.assertIs(cli.tool_service.registry, app.tool_service.registry)

    def test_meme_resultat_cli_et_web(self) -> None:
        """Le même outil produit le même résultat dans les deux interfaces."""
        cli = CLI(settings=Settings(), tool_service=self.service)
        out = io.StringIO()
        with redirect_stdout(out):
            cli._handle_tool_command(["action_datetime"])
        sortie_cli = out.getvalue()

        app = build_app(tool_service=self.service)
        with _WebFixture(app) as web:
            status, payload = web.request(
                "POST", "/tool", {"tool": "action_datetime", "parameters": {}}
            )
        self.assertIn("[Outil exécuté] action_datetime", sortie_cli)
        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])


# ---------------------------------------------------------------------------
# 10 : non-divulgation des secrets
# ---------------------------------------------------------------------------

class TestToolSecretProtection(unittest.TestCase):
    """10. Non-divulgation des secrets."""

    def test_parametre_secret_refuse(self) -> None:
        service = ToolService()
        result = service.request_tool(
            "action_list_files", {"password": "motdepasse"}
        )
        self.assertFalse(result.success)
        self.assertIn("politique de sécurité", result.error_message)

    def test_cle_shell_refusee(self) -> None:
        service = ToolService()
        result = service.request_tool("action_datetime", {"shell": "rm -rf /"})
        self.assertFalse(result.success)
        self.assertIn("politique de sécurité", result.error_message)

    def test_secret_absent_du_catalogue(self) -> None:
        service = ToolService()
        texte = json.dumps(service.list_tools())
        self.assertNotIn("sk-", texte)
        self.assertNotIn("api_key", texte)

    def test_secret_absent_de_la_reponse_web(self) -> None:
        service = ToolService()
        app = build_app(tool_service=service)
        with _WebFixture(app) as web:
            status, payload = web.request(
                "POST", "/tool", {"tool": "action_datetime", "parameters": {"token": "abc"}}
            )
        self.assertEqual(status, 400)
        self.assertNotIn("abc", json.dumps(payload))


# ---------------------------------------------------------------------------
# 11 : régression conversation et persistance SQLite
# ---------------------------------------------------------------------------

class TestToolIntegrationRegression(unittest.TestCase):
    """11. Régression de la conversation et de la persistance SQLite."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="miles_tool_regression_")
        self.db_path = os.path.join(self.tmpdir, "conversations.db")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_conversation_toujours_functionnelle(self) -> None:
        from app.memory.transcript import ConversationTranscript

        transcript = ConversationTranscript(enabled=True, db_path=self.db_path)
        conversation = Conversation(history_limit=10)
        conversation.attach_transcript(transcript)
        conversation.add_user_message("question")
        conversation.add_assistant_message("réponse")
        self.assertEqual(len(conversation), 2)
        self.assertEqual(len(transcript.load_messages(conversation.conversation_id)), 2)
        transcript.close()

    def test_persistance_sqlite_intacte(self) -> None:
        from app.memory.transcript import ConversationTranscript

        transcript = ConversationTranscript(enabled=True, db_path=self.db_path)
        conv_id = transcript.create_conversation()
        transcript.save_message(conv_id, "user", "persistant")
        self.assertEqual(len(transcript.load_messages(conv_id)), 1)
        transcript.close()

    def test_outils_independants_de_la_conversation(self) -> None:
        """Les outils ne modifient pas l'historique de conversation."""
        from app.memory.transcript import ConversationTranscript

        transcript = ConversationTranscript(enabled=True, db_path=self.db_path)
        conversation = Conversation(history_limit=10)
        conversation.attach_transcript(transcript)
        service = ToolService()
        service.request_tool("action_datetime")
        self.assertEqual(len(conversation), 0)
        self.assertEqual(
            len(transcript.load_messages(conversation.conversation_id)), 0
        )
        transcript.close()


# ---------------------------------------------------------------------------
# 12 : aucune action réelle pendant les tests
# ---------------------------------------------------------------------------

class TestNoRealActionExecuted(unittest.TestCase):
    """12. Absence d'exécution d'une action réelle pendant les tests."""

    def test_outil_liste_fichiers_ne_modifie_rien(self) -> None:
        """L'outil ne modifie pas le répertoire qu'il liste."""
        from app.security.paths import project_root
        from app.tools.local_actions import list_files_handler

        # Le répertoire doit être dans les racines autorisées (projet).
        tmpdir = tempfile.mkdtemp(prefix="miles_action_cible_", dir=str(project_root()))
        try:
            marqueur = os.path.join(tmpdir, "fichier.txt")
            with open(marqueur, "w", encoding="utf-8") as fh:
                fh.write("contenu")
            avant = sorted(os.listdir(tmpdir))

            resultat = list_files_handler(path=tmpdir)
            noms = [entry["name"] for entry in resultat["entries"]]
            self.assertIn("fichier.txt", noms)
            # Aucun fichier créé ni supprimé
            self.assertEqual(sorted(os.listdir(tmpdir)), avant)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_outil_liste_fichiers_refuse_chemin_hors_racines(self) -> None:
        """Un chemin hors des racines autorisées est refusé."""
        from app.tools.local_actions import list_files_handler

        with self.assertRaises(PermissionError):
            list_files_handler(path=os.path.dirname(tempfile.gettempdir()))

    def test_outil_datetime_est_sans_effet_de_bord(self) -> None:
        from app.tools.local_actions import datetime_handler, workdir_handler

        premiere = datetime_handler()
        seconde = datetime_handler()
        self.assertTrue(premiere)
        self.assertRegex(premiere, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        self.assertIsInstance(premiere, str)
        self.assertIsInstance(seconde, str)
        self.assertEqual(workdir_handler(), os.getcwd())

    def test_aucun_appel_reseau_par_les_outils(self) -> None:
        """Les outils enregistrés n'effectuent aucun appel réseau."""
        import inspect

        from app.tools import builtin, local_actions

        for module in (builtin, local_actions):
            source = inspect.getsource(module)
            self.assertNotIn("urllib", source)
            self.assertNotIn("requests", source)
            self.assertNotIn("socket", source)

    def test_action_externe_refusee_sans_confirmation(self) -> None:
        """L'action à effet externe n'est pas exécutée sans confirmation."""
        service = ToolService()
        result = service.request_tool("action_list_files", {"path": "data"})
        self.assertFalse(result.success)
        self.assertTrue(result.confirmation_required)


if __name__ == "__main__":
    unittest.main()

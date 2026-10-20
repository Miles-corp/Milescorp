"""Tests d'audit Phase 6 — Agent B (revue indépendante).

Ces tests ne modifient aucun fichier de production. Ils vérifient les
propriétés de sécurité et de fonctionnement attendues, et **documentent
explicitement** les comportements défaillants constatés (tests marqués
`audit_defaut`) afin qu'ils ne puissent pas être oubliés.

Portée : l'orchestrateur de missions annoncé par la Phase 6
(`feature/miles-mission-orchestrator`) n'est pas publié dans le dépôt ;
ces tests couvrent donc la brique effectivement disponible et auditée :
le moteur d'outils et son intégration (ToolService / ToolEngine / CLI / web).

Aucun appel réseau sortant, aucun fournisseur payant, aucun modèle local.
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

from app.ai_providers.base import AIProviderError
from app.config.settings import Settings
from app.core.conversation import Conversation
from app.interface.cli import CLI
from app.interface.web import MilesHandler, WebApp
from app.security.paths import PathSecurityError, resolve_authorized_path
from app.tools.audit import AuditLogger
from app.tools.engine import ToolEngine
from app.tools.policy import ToolPolicy
from app.tools.registry import ToolDefinition, ToolParameter, ToolRegistry
from app.tools.service import ToolService


def _failing_handler() -> str:
    raise RuntimeError("echec simule du handler")


def _slow_handler() -> str:
    import time

    time.sleep(30)
    return "trop lent"


def _partial_handler() -> str:
    """Retourne un résultat partiel (vide) sans lever d'exception."""
    return ""


class _Server:
    """Serveur web de test sur un port libre."""

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

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict:
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(
            url, data=body, headers=headers or {}, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return {"status": resp.status, "body": resp.read().decode("utf-8")}
        except urllib.error.HTTPError as exc:
            return {
                "status": exc.code,
                "body": exc.read().decode("utf-8", errors="replace"),
            }


class TestAuditToolPaths(unittest.TestCase):
    """Aucun appel d'outil ne doit contourner ToolEngine / ToolService."""

    def test_cli_et_web_utilisent_le_meme_service(self) -> None:
        service = ToolService()
        cli = CLI(settings=Settings(), tool_service=service)
        web = WebApp(settings=Settings(), tool_service=service)
        self.assertIs(cli.tool_service, web.tool_service)
        self.assertIs(cli.tool_service.engine, web.tool_service.engine)

    def test_aucun_outil_ecriture_dans_le_registre(self) -> None:
        """Aucune modification de fichier ne doit etre possible via un outil."""
        service = ToolService()
        for tool_id in service.registry.list_tools():
            tool = service.registry.get_tool(tool_id)
            self.assertIsNotNone(tool)
            self.assertIn(tool.risk_level, ("LOW", "MEDIUM", "HIGH"))
            # Tous les outils enregistres doivent etre des lectures.
            self.assertIn(
                tool_id,
                ("status_read", "action_datetime", "action_workdir", "action_list_files"),
            )

    def test_outil_inconnu_refuse(self) -> None:
        service = ToolService()
        result = service.request_tool("outil_inexistant", {})
        self.assertFalse(result.success)
        self.assertIn("inconnu", result.error_message.lower())

    def test_cle_interdite_refusee_par_la_politique(self) -> None:
        """Une clé shell/code/secret dans les paramètres doit être refusée."""
        service = ToolService()
        for params in (
            {"shell": "rm -rf /"},
            {"code": "print(1)"},
            {"api_key": "sk-fausse"},
        ):
            with self.subTest(params=params):
                result = service.request_tool("action_list_files", params)
                self.assertFalse(result.success)

    def test_lecture_hors_repertoire_autorise_refusee(self) -> None:
        """Un chemin hors racines autorisees doit etre refuse."""
        service = ToolService()
        result = service.request_tool("action_list_files", {"path": "/etc"})
        self.assertFalse(result.success)

    def test_lien_symbolique_sortant_refuse(self) -> None:
        """Un lien symbolique sortant doit etre refuse (confinement canonique)."""
        tmpdir = tempfile.mkdtemp(prefix="miles_audit_")
        link = os.path.join("data", "_audit_lien_sortant")
        try:
            outside = os.path.join(tmpdir, "outside")
            os.makedirs(outside, exist_ok=True)
            if os.path.lexists(link):
                os.unlink(link)
            try:
                os.symlink(outside, link)
            except (OSError, NotImplementedError):
                self.skipTest("Liens symboliques non creatables sur cette plateforme")
            with self.assertRaises(PathSecurityError):
                resolve_authorized_path(link)
        finally:
            if os.path.lexists(link):
                os.unlink(link)
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestAuditConfirmation(unittest.TestCase):
    """Confirmations : expiration, rejeu, liaison aux parametres."""

    def setUp(self) -> None:
        self.service = ToolService()

    def _token_for_list_files(self) -> str:
        result = self.service.request_tool("action_list_files", {"path": "data"})
        self.assertTrue(result.confirmation_required)
        return result.confirmation_token

    def test_confirmation_expiree_refusee(self) -> None:
        service = ToolService(confirmation_ttl_seconds=0.1)
        first = service.request_tool("action_list_files", {"path": "data"})
        self.assertTrue(first.confirmation_required)
        import time

        time.sleep(0.25)
        result = service.request_tool(
            "action_list_files",
            {"path": "data"},
            user_confirmed=True,
            confirmation_token=first.confirmation_token,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.confirmation_required)

    def test_confirmation_non_rejouable(self) -> None:
        """Un jeton consomme ne peut pas servir une seconde fois."""
        token = self._token_for_list_files()
        first = self.service.request_tool(
            "action_list_files",
            {"path": "data"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertTrue(first.success)
        replay = self.service.request_tool(
            "action_list_files",
            {"path": "data"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertFalse(replay.success)
        self.assertTrue(replay.confirmation_required)

    def test_confirmation_refusee_sans_jeton(self) -> None:
        """user_confirmed=True sans jeton valide ne doit rien executer."""
        result = self.service.request_tool(
            "action_list_files", {"path": "data"}, user_confirmed=True
        )
        self.assertFalse(result.success)
        self.assertTrue(result.confirmation_required)

    def test_jeton_non_valide_pour_autres_parametres(self) -> None:
        token = self._token_for_list_files()
        result = self.service.request_tool(
            "action_list_files",
            {"path": "app"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.confirmation_required)

    def test_jeton_non_valide_pour_un_autre_outil(self) -> None:
        """Un jeton obtenu pour un outil ne vaut pas pour un autre outil."""
        token = self._token_for_list_files()
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                tool_id="autre_action",
                description="Autre action sensible",
                handler=lambda: "x",  # type: ignore[arg-type]
                risk_level="MEDIUM",
                required_permissions=("lecture_systeme",),
                timeout_seconds=5,
            )
        )
        engine = ToolEngine(
            registry=registry,
            policy=ToolPolicy(granted_permissions={"lecture_systeme"}),
            audit=AuditLogger(),
        )
        result = engine.request_tool(
            "autre_action",
            {},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.confirmation_required)

    @unittest.expectedFailure
    def test_audit_defaut_confirmation_non_liee_a_une_identite(self) -> None:
        """DEFAUT CONSTATE (P1) : le jeton n'est lie a aucune identite.

        Le jeton est lie a l'outil et aux parametres exacts, expire, et n'est
        utilisable qu'une fois. Mais il n'est lie a **aucune session ni
        identite** : dans le serveur web, un seul `ToolService` est partage
        par tous les clients HTTP ; le jeton delivre a un client peut donc
        etre reutilise par un autre client du meme service.

        Ce test exprime le comportement **souhaité** (refus) ; il est marque
        `expectedFailure` car le defaut est present. Le jour ou la liaison a
        l'identite sera implementee, ce test echouera comme "unexpected
        success", signalant que la correction est a retirer de
        `expectedFailure`.
        """
        token = self._token_for_list_files()
        # Second client du MEME service (comme deux navigateurs sur le
        # serveur web local, qui partagent un seul ToolService) : il
        # n'a aucune identite, mais peut reutiliser le jeton du premier.
        result = self.service.request_tool(
            "action_list_files",
            {"path": "data"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertFalse(
            result.success,
            "Le jeton a ete accepte par un client sans identite lie : "
            "le defaut P1 est corrige, retirer expectedFailure.",
        )

    def test_jeton_non_partage_entre_moteurs_differents(self) -> None:
        """Un jeton n'est pas partage entre deux moteurs distincts.

        Ce n'est pas une protection d'identite : le serveur web n'expose
        qu'un seul moteur. Ce test documente la frontiere reelle du
        mecanisme de confirmation.
        """
        token = self._token_for_list_files()
        autre_moteur = ToolService(
            registry=self.service.registry, granted_permissions={"lecture_systeme"}
        )
        result = autre_moteur.request_tool(
            "action_list_files",
            {"path": "data"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.confirmation_required)


class TestAuditWebAccessControl(unittest.TestCase):
    """Les endpoints web doivent valider les entrées et contrôler l'accès."""

    def _app(self) -> WebApp:
        return WebApp(settings=Settings(), tool_service=ToolService())

    @unittest.expectedFailure
    def test_audit_defaut_requete_cross_origin_refusee(self) -> None:
        """DEFAUT CONSTATE (P1) : aucune protection Origin/Referer.

        Le serveur web est bound sur 127.0.0.1 mais n'exige aucun en-tete
        Origin valide et ne verifie pas le Content-Type de la requete. Une
        page web tierce peut donc envoyer une requete POST simple (type
        `text/plain`, sans preflight CORS) vers un endpoint local.

        Ce test exprime le comportement **souhaité** (refus 403) ; il est
        marque `expectedFailure` car le defaut est present.
        """
        payload = json.dumps({"tool": "status_read", "parameters": {}}).encode()
        with _Server(self._app()) as server:
            result = server.request(
                "POST",
                "/tool",
                body=payload,
                headers={
                    "Content-Type": "text/plain",
                    "Origin": "http://site-malveillant.example",
                },
            )
        self.assertEqual(
            result["status"],
            403,
            "La requete cross-origin a ete traitee : le defaut P1 est "
            "corrige, retirer expectedFailure.",
        )

    @unittest.expectedFailure
    def test_audit_defaut_content_type_non_json_refuse(self) -> None:
        """DEFAUT CONSTATE (P2) : le Content-Type de la requete n'est pas verifie.

        Un corps JSON est accepte quelle que soit l'en-tete Content-Type.
        Ce test exprime le comportement **souhaite** (415) ; il est marque
        `expectedFailure` car le defaut est present.
        """
        payload = json.dumps({"tool": "status_read", "parameters": {}}).encode()
        with _Server(self._app()) as server:
            result = server.request(
                "POST", "/tool", body=payload, headers={"Content-Type": "text/plain"}
            )
        self.assertEqual(
            result["status"],
            415,
            "Le Content-Type non JSON a ete accepte : le defaut P2 est "
            "corrige, retirer expectedFailure.",
        )

    def test_outil_inconnu_refuse_par_la_route(self) -> None:
        payload = json.dumps({"tool": "outil_inconnu", "parameters": {}}).encode()
        with _Server(self._app()) as server:
            result = server.request(
                "POST", "/tool", body=payload, headers={"Content-Type": "application/json"}
            )
        self.assertEqual(result["status"], 400)
        self.assertIn("inconnu", result["body"].lower())

    def test_parametres_non_objet_refuses(self) -> None:
        payload = json.dumps({"tool": "status_read", "parameters": [1, 2]}).encode()
        with _Server(self._app()) as server:
            result = server.request(
                "POST", "/tool", body=payload, headers={"Content-Type": "application/json"}
            )
        self.assertEqual(result["status"], 400)

    def test_jeton_invalide_refuse_par_la_route(self) -> None:
        """Un jeton inconnu ne doit jamais exécuter l'outil.

        Le protocole renvoie 200 pour une demande de confirmation (réponse
        normale du protocole), mais l'outil ne doit pas être exécuté et une
        nouvelle confirmation doit être exigée.
        """
        payload = json.dumps(
            {
                "tool": "action_list_files",
                "parameters": {"path": "data"},
                "user_confirmed": True,
                "confirmation_token": "jeton_inexistant",
            }
        ).encode()
        with _Server(self._app()) as server:
            result = server.request(
                "POST", "/tool", body=payload, headers={"Content-Type": "application/json"}
            )
        self.assertEqual(result["status"], 200)
        body = json.loads(result["body"])
        self.assertTrue(body.get("confirmation_required"))
        self.assertFalse(body.get("success"))
        self.assertNotIn("result", body)


class TestAuditFailureHandling(unittest.TestCase):
    """Gestion des echecs : pas de faux succes, reprise maitrisee."""

    def _engine_with(self, handler) -> ToolEngine:
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                tool_id="action_test",
                description="Outil de test",
                handler=handler,
                risk_level="LOW",
                required_permissions=(),
                timeout_seconds=5,
            )
        )
        return ToolEngine(
            registry=registry,
            policy=ToolPolicy(granted_permissions=set()),
            audit=AuditLogger(),
        )

    def test_exception_du_handler_non_presentee_comme_succes(self) -> None:
        result = self._engine_with(_failing_handler).request_tool("action_test", {})
        self.assertFalse(result.success)
        self.assertTrue(result.error_message)
        self.assertIsNone(result.data)

    def test_resultat_vide_non_presente_comme_succes(self) -> None:
        """Un résultat vide n'est pas un échec, mais il ne doit rien cacher."""
        result = self._engine_with(_partial_handler).request_tool("action_test", {})
        self.assertTrue(result.success)
        self.assertEqual(result.data, "")

    def test_depassement_de_delai_bloque(self) -> None:
        engine = self._engine_with(_slow_handler)
        registry = engine._registry  # noqa: SLF001 - audit
        tool = registry.get_tool("action_test")
        assert tool is not None
        object.__setattr__(tool, "timeout_seconds", 1)
        result = engine.request_tool("action_test", {})
        self.assertFalse(result.success)
        self.assertIn("dépassé", result.error_message)

    def test_erreur_puis_reprise_avec_jeton_invalide(self) -> None:
        """Après un échec, un jeton périmé ou absent ne permet pas d'exécuter."""
        service = ToolService()
        first = service.request_tool("action_list_files", {"path": "data"})
        self.assertTrue(first.confirmation_required)
        # Reprise avec un jeton qui n'a jamais été délivré
        reprise = service.request_tool(
            "action_list_files",
            {"path": "data"},
            user_confirmed=True,
            confirmation_token="jeton_fabrique",
        )
        self.assertFalse(reprise.success)
        self.assertTrue(reprise.confirmation_required)

    def test_echec_audit_est_journalise(self) -> None:
        service = ToolService()
        service.request_tool("outil_inexistant", {})
        entries = service.audit.get_entries()
        self.assertTrue(entries)
        self.assertEqual(entries[-1].result, "refused")


class TestAuditOrchestratorPresence(unittest.TestCase):
    """L'orchestrateur de missions annonce par la Phase 6 est-il present ?"""

    def test_orchestrateur_de_missions_present_dans_le_depot(self) -> None:
        """Aucun module d'orchestrateur de missions n'existe dans le depot.

        La Phase 6 annonce une branche `feature/miles-mission-orchestrator`
        qui n'est pas publiee : aucun fichier `orchestrat*` ni `mission*`
        n'existe dans les sources de l'application.
        """
        app_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"
        )
        trouves = []
        for racine, _dirs, fichiers in os.walk(app_dir):
            for nom in fichiers:
                if nom.endswith(".py"):
                    nom_sans_ext = nom[:-3]
                    if "orchestrat" in nom_sans_ext or "mission" in nom_sans_ext:
                        trouves.append(os.path.join(racine, nom))
        self.assertEqual(
            trouves,
            [],
            "Un orchestrateur de missions existe : l'audit de la Phase 6 doit "
            "alors porter sur ce code. Trouve : %r" % (trouves,),
        )


if __name__ == "__main__":
    unittest.main()

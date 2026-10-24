"""Tests du correctif D3 : typage explicite des paramètres de chemin.

DÉFAUT D3 (rapport de validation Phase 6.3, §4) :

    La politique de sécurité appliquait un contrôle **par sous-chaîne** aux
    VALEURS des paramètres, y compris aux valeurs de chemin. Un répertoire
    légitime dont le nom contient « source », « code », « script » ou
    « python » était donc refusé — et avec lui, toute mission portant sur
    un tel répertoire.

    Le contrôle sur les **CLÉS** (correspondance exacte) était, lui, correct.

CORRECTIF : le type « chemin » est **déclaré** dans le schéma de l'outil
(`ToolParameter.is_path`). La politique reçoit la liste des paramètres
déclarés comme chemins et leur applique un contrôle **structurel**
(caractères de contrôle et métacaractères de commande) au lieu du contrôle
par sous-chaîne. Le contrôle sur les clés est **inchangé**.

Ces tests distinguent explicitement trois niveaux, qui ne doivent jamais
être confondus :

1. l'**acceptation par la politique** (le paramètre n'est pas refusé pour
   son contenu) ;
2. la **validation du chemin** (le chemin est-il dans les racines
   autorisées ? — `app.security.paths`) ;
3. l'**autorisation effective de l'opération** (l'outil s'exécute-t-il
   réellement ? — le moteur et le handler).

Un chemin accepté par la politique (niveau 1) ne doit **jamais** suffire à
autoriser l'accès à un fichier : le niveau 2 tranche, et il n'a pas été
modifié.

NOTE SUR LE PÉRIMÈTRE RÉEL DE LA POLITIQUE (vérifié sur le code) : le
contrôle par sous-chaîne porte sur un ensemble de **mots** interdits
(« code », « script », « python », « javascript », « shell_code »,
« source » ; « shell », « command », « cmd », « exec », « eval », « run »,
« system » ; « password », « secret », « api_key », « token »…). Il ne
détecte pas des fragments de code comme « import os » ou « print(1) » :
ce n'est pas une détection de motifs. Les tests ci-dessouscollent au
comportement réel.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from app.security.paths import (
    PathSecurityError,
    default_allowed_roots,
    project_root,
    resolve_authorized_path,
)
from app.tools.audit import AuditLogger
from app.tools.builtin import build_default_registry
from app.tools.engine import ToolEngine
from app.tools.policy import ToolPolicy
from app.tools.registry import ToolDefinition, ToolParameter, ToolRegistry


def _declared_path_parameters() -> set:
    """Retourner les noms de paramètres déclarés comme chemins."""
    registry = build_default_registry()
    return {
        param.name
        for tool_id in registry.list_tools()
        for param in registry.get_tool(tool_id).parameters
        if param.is_path
    }


#: Noms des paramètres déclarés comme chemins dans le registre réel.
PATH_PARAMETERS = _declared_path_parameters()


def _policy() -> ToolPolicy:
    """Politique de test (les permissions n'ont pas d'effet ici)."""
    return ToolPolicy(granted_permissions={"lecture_systeme"})


def _echo_path_handler(path: str = "") -> str:
    """Handler de test : renvoie le chemin reçu (prouve l'exécution)."""
    return f"chemin recu: {path}"


def _build_engine(registry: ToolRegistry) -> ToolEngine:
    """Construire un moteur avec la politique réelle."""
    return ToolEngine(
        registry=registry,
        policy=_policy(),
        audit=AuditLogger(),
    )


def _registry_with_path_tool() -> ToolRegistry:
    """Registre contenant un outil dont le paramètre est un chemin."""
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            tool_id="outil_chemin",
            description="Outil de test avec un paramètre de chemin",
            parameters=(
                ToolParameter(
                    name="path",
                    type=str,
                    required=True,
                    description="Chemin à examiner",
                    is_path=True,
                ),
            ),
            risk_level="LOW",
            required_permissions=(),
            timeout_seconds=10,
            handler=_echo_path_handler,
        )
    )
    return registry


def _executer_avec_confirmation(
    engine: ToolEngine, tool_id: str, parameters: dict
):
    """Exécuter un outil de risque MEDIUM en fournissant la confirmation."""
    premier = engine.request_tool(tool_id, parameters)
    if not premier.confirmation_required:
        return premier
    return engine.request_tool(
        tool_id,
        parameters,
        user_confirmed=True,
        confirmation_token=premier.confirmation_token,
    )


# ---------------------------------------------------------------------------
# Niveau 1 — l'acceptation par la politique
# ---------------------------------------------------------------------------

class TestClesSensiblesRestentInterdites(unittest.TestCase):
    """Les CLÉS interdites le restent, quelle que soit la valeur."""

    def test_cles_code_refusees(self) -> None:
        for key in ("code", "script", "python", "javascript", "shell_code", "source"):
            with self.subTest(cle=key):
                with self.assertRaises(PermissionError):
                    _policy().validate_no_code_execution({key: "print(1)"})

    def test_cles_shell_refusees(self) -> None:
        for key in ("shell", "command", "cmd", "exec", "eval", "run", "system"):
            with self.subTest(cle=key):
                with self.assertRaises(PermissionError):
                    _policy().validate_no_shell_access({key: "ls"})

    def test_cles_secrets_refusees(self) -> None:
        for key in (
            "password", "secret", "api_key", "token", "private_key",
            "credential", "apikey", "access_key", "secret_key",
        ):
            with self.subTest(cle=key):
                with self.assertRaises(PermissionError):
                    _policy().validate_no_secret_access({key: "valeur"})

    def test_cle_sensible_refusee_meme_avec_un_chemin_valide(self) -> None:
        """Le typage du chemin n'exempte AUCUNE clé interdite."""
        with self.assertRaises(PermissionError):
            _policy().validate_no_code_execution(
                {"path": "C:\\dev\\source", "code": "print(1)"},
                path_parameters=PATH_PARAMETERS,
            )

    def test_cles_interdites_non_declarees_restent_refusees(self) -> None:
        """Un paramètre dont le type n'est pas déclaré reste contrôlé."""
        with self.assertRaises(PermissionError):
            _policy().validate_no_code_execution(
                {"chemin_non_declare": "C:\\dev\\source"},
                path_parameters=PATH_PARAMETERS,
            )

    def test_cle_sensible_avec_valeur_vide_refusee(self) -> None:
        """La clé interdite est refusée même si sa valeur est vide."""
        with self.assertRaises(PermissionError):
            _policy().validate_no_code_execution({"code": ""})


class TestValeursLibresRestentControlees(unittest.TestCase):
    """Les valeurs qui ne sont PAS des chemins restent contrôlées."""

    def test_valeur_libre_avec_mot_interdit_refusee(self) -> None:
        """Les valeurs libres contenant un mot interdit restent refusées."""
        for value in ("import code", "un script shell", "python", "javascript"):
            with self.subTest(valeur=value):
                with self.assertRaises(PermissionError):
                    _policy().validate_no_code_execution({"message": value})

    def test_valeur_libre_avec_mot_shell_refusee(self) -> None:
        for value in ("eval(1)", "exec rm -rf /", "system", "cmd"):
            with self.subTest(valeur=value):
                with self.assertRaises(PermissionError):
                    _policy().validate_no_shell_access({"message": value})

    def test_valeur_libre_avec_mot_secret_refusee(self) -> None:
        for value in ("mon token", "password: xyz", "apikey=abc"):
            with self.subTest(valeur=value):
                with self.assertRaises(PermissionError):
                    _policy().validate_no_secret_access({"message": value})

    def test_valeur_libre_ressemblant_a_un_chemin_refusee(self) -> None:
        """Un chemin placed dans un paramètre NON typé chemin reste refusé."""
        with self.assertRaises(PermissionError):
            _policy().validate_no_code_execution(
                {"message": "C:\\dev\\source"},
                path_parameters=PATH_PARAMETERS,
            )

    def test_valeur_libre_imbriquee_refusee(self) -> None:
        """Une valeur interdite imbriquée reste refusée."""
        with self.assertRaises(PermissionError):
            _policy().validate_no_code_execution(
                {"options": {"valeur": "source"}},
                path_parameters=PATH_PARAMETERS,
            )

    def test_valeurs_libres_innocentes_acceptees(self) -> None:
        """Les valeurs libres sans mot interdit restent acceptées."""
        _policy().validate_no_code_execution({"message": "bonjour"})
        _policy().validate_no_code_execution({})
        _policy().validate_no_shell_access({"fichier": "test.txt"})
        _policy().validate_no_secret_access({"nom": "utilisateur"})


class TestCheminsLegitimesAcceptesParLaPolitique(unittest.TestCase):
    """Les chemins légitimes sont acceptés par la politique (faux D3)."""

    def test_chemins_windows_avec_mots_interdits_acceptes(self) -> None:
        cas = [
            r"C:\dev\source",
            r"C:\dev\source\projet",
            r"C:\Users\X\Documents\code",
            r"C:\Users\X\Documents\scripts",
            r"C:\Python39\Lib",
            r"C:\Users\X\mon-script-de-notes.txt",
            r"C:\Windows\System32",
            r"C:\Users\X\AppData\Local\run",
            r"C:\Users\X\Desktop\command",
            r"C:\Users\X\Documents\secret",
            r"C:\Users\X\Desktop\exec",
        ]
        for chemin in cas:
            with self.subTest(chemin=chemin):
                for validateur in (
                    _policy().validate_no_code_execution,
                    _policy().validate_no_shell_access,
                    _policy().validate_no_secret_access,
                ):
                    validateur(
                        {"path": chemin}, path_parameters=PATH_PARAMETERS
                    )

    def test_chemins_posix_acceptes(self) -> None:
        for chemin in ("/home/user/projet", "/etc/passwd", "docs/coordination"):
            with self.subTest(chemin=chemin):
                _policy().validate_no_code_execution(
                    {"path": chemin}, path_parameters=PATH_PARAMETERS
                )

    def test_repertoires_avec_esperet_ou_dollar_acceptes(self) -> None:
        """« & » et « $ » sont légitimes (« Rock & Roll », « $Recycle.Bin »)."""
        for chemin in (r"C:\Users\X\Rock & Roll", r"C:\$Recycle.Bin"):
            with self.subTest(chemin=chemin):
                _policy().validate_no_code_execution(
                    {"path": chemin}, path_parameters=PATH_PARAMETERS
                )


class TestMetacaracteresBloquesDansUnChemin(unittest.TestCase):
    """Un chemin reste validé structurellement."""

    def test_metacaracteres_de_commande_refuses(self) -> None:
        for chemin in (
            "C:\\x; rm -rf /",
            "C:\\x|c",
            "C:\\x`y",
            "C:\\x>y",
            "C:\\x<y",
        ):
            with self.subTest(chemin=chemin):
                with self.assertRaises(PermissionError):
                    _policy().validate_no_code_execution(
                        {"path": chemin}, path_parameters=PATH_PARAMETERS
                    )

    def test_caracteres_de_controle_refuses(self) -> None:
        for chemin in ("C:\\x\ny", "C:\\x\ry", "C:\\x\x00y"):
            with self.subTest(chemin=chemin):
                with self.assertRaises(PermissionError):
                    _policy().validate_no_code_execution(
                        {"path": chemin}, path_parameters=PATH_PARAMETERS
                    )

    def test_structure_validee_dans_les_trois_validateurs(self) -> None:
        """La validation structurelle s'applique aux trois validateurs."""
        for validateur in (
            _policy().validate_no_code_execution,
            _policy().validate_no_shell_access,
            _policy().validate_no_secret_access,
        ):
            with self.assertRaises(PermissionError):
                validateur(
                    {"path": "C:\\x; rm -rf /"}, path_parameters=PATH_PARAMETERS
                )

    def test_exemption_bornee_a_la_valeur_directe(self) -> None:
        """Une structure sous un paramètre de chemin n'est PAS exemptée."""
        with self.assertRaises(PermissionError):
            _policy().validate_no_code_execution(
                {"path": ["C:\\dev\\source"]}, path_parameters=PATH_PARAMETERS
            )
        with self.assertRaises(PermissionError):
            _policy().validate_no_code_execution(
                {"path": {"valeur": "source"}}, path_parameters=PATH_PARAMETERS
            )

    def test_type_non_chaine_traite_par_la_validation_de_type(self) -> None:
        """Une valeur qui n'est pas une chaîne n'est pas un chemin.

        La politique ne contrôle que les chaînes : elle n'a donc rien à
        dire sur un entier. C'est la validation de type du moteur qui
        refuse le paramètre (voir
        ``TestNiveauOutil.test_outil_refuse_un_type_incorrect``).
        """
        # Aucune exception de la politique : ce n'est pas une chaîne.
        _policy().validate_no_code_execution(
            {"path": 42}, path_parameters=PATH_PARAMETERS
        )


class TestDefautD3Reproduit(unittest.TestCase):
    """Le défaut D3 est reproductible et le correctif est vérifiable.

    Ces tests n'utilisent pas la nouvelle API pour la partie « historique » :
    ils montrent que le comportement antérieur (contrôle par sous-chaîne sur
    **toutes** les valeurs) refuse un chemin légitime, et que le typage
    explicite — seul mécanisme qui distingue un chemin d'une valeur libre —
    le corrige. Ils échouent si l'exemption est supprimée ou mal bornée.
    """

    def test_sans_typage_le_chemin_est_refuse(self) -> None:
        """Comportement historique : sans typage, le chemin est refusé."""
        with self.assertRaises(PermissionError):
            _policy().validate_no_code_execution({"path": r"C:\dev\source"})

    def test_avec_typage_le_meme_chemin_est_accepte(self) -> None:
        """Avec le typage explicite, le même chemin est accepté."""
        _policy().validate_no_code_execution(
            {"path": r"C:\dev\source"}, path_parameters=PATH_PARAMETERS
        )

    def test_le_typage_est_decl_par_l_application(self) -> None:
        """Le typage vient du schéma de l'outil, jamais du modèle."""
        registry = build_default_registry()
        declare = {
            tool_id: sorted(
                param.name
                for param in registry.get_tool(tool_id).parameters
                if param.is_path
            )
            for tool_id in registry.list_tools()
        }
        self.assertEqual(declare["action_list_files"], ["path"])
        self.assertEqual(declare["action_read_file"], ["path"])


# ---------------------------------------------------------------------------
# Niveau 2 — la validation du chemin (confinement, inchangé)
# ---------------------------------------------------------------------------

class TestConfinementResteLEAutorite(unittest.TestCase):
    """Un chemin accepté par la politique ne suffit pas à accéder au fichier."""

    def test_chemin_hors_racines_refuse_par_le_confinement(self) -> None:
        """Niveau 1 accepte, niveau 2 refuse : le confinement tranche."""
        chemin = (
            "C:\\Windows\\System32"
            if os.name == "nt"
            else "/Windows/System32"
        )
        # Niveau 1 : accepté par la politique.
        _policy().validate_no_code_execution(
            {"path": chemin}, path_parameters=PATH_PARAMETERS
        )
        # Niveau 2 : refusé par le confinement.
        with self.assertRaises(PathSecurityError):
            resolve_authorized_path(chemin)

    def test_traversee_de_repertoires_refusee(self) -> None:
        """Une traversée sort des racines : refusée (le chemin est résolu)."""
        for chemin in ("../docs", "../../etc", "docs/../../etc"):
            with self.subTest(chemin=chemin):
                with self.assertRaises(PathSecurityError):
                    resolve_authorized_path(chemin)

    def test_chemin_valide_dans_le_projet_accepte(self) -> None:
        """Un chemin dans les racines autorisées est accepté."""
        resolu = resolve_authorized_path("docs")
        self.assertTrue(str(resolu).endswith("docs"))

    def test_les_racines_autorisees_sont_inchangees(self) -> None:
        """Les racines autorisées sont celles du projet et de ``data/``."""
        racines = {str(r) for r in default_allowed_roots()}
        self.assertEqual(
            racines, {str(project_root()), str(project_root() / "data")}
        )


# ---------------------------------------------------------------------------
# Niveau 3 — l'autorisation effective de l'opération (moteur et handler)
# ---------------------------------------------------------------------------

class TestNiveauOutil(unittest.TestCase):
    """Ce que l'outil fait réellement (moteur)."""

    def setUp(self) -> None:
        self.registry = _registry_with_path_tool()
        self.engine = _build_engine(self.registry)

    def test_outil_execute_avec_un_chemin_legitime(self) -> None:
        """Niveau 3 : l'outil s'exécute avec un chemin contenant « source »."""
        resultat = self.engine.request_tool(
            "outil_chemin", {"path": "C:\\dev\\source"}
        )
        self.assertTrue(resultat.success, resultat.error_message)
        self.assertIn("C:\\dev\\source", str(resultat.data))

    def test_outil_refuse_un_chemin_avec_metacaractere(self) -> None:
        """Niveau 3 : un chemin avec métacaractère est refusé par la politique."""
        resultat = self.engine.request_tool(
            "outil_chemin", {"path": "C:\\x; rm -rf /"}
        )
        self.assertFalse(resultat.success)
        self.assertIn(
            "politique de sécurité", str(resultat.error_message).lower()
        )

    def test_outil_refuse_une_cle_interdite(self) -> None:
        """Niveau 3 : une clé interdite reste refusée par la politique."""
        resultat = self.engine.request_tool(
            "outil_chemin", {"path": "docs", "code": "print(1)"}
        )
        self.assertFalse(resultat.success)
        self.assertIn(
            "politique de sécurité", str(resultat.error_message).lower()
        )

    def test_outil_refuse_un_parametre_non_declare(self) -> None:
        """Niveau 3 : un paramètre non déclaré est refusé (schéma)."""
        resultat = self.engine.request_tool(
            "outil_chemin", {"path": "docs", "source": "x"}
        )
        self.assertFalse(resultat.success)

    def test_outil_refuse_un_type_incorrect(self) -> None:
        """Niveau 3 : un type incorrect est refusé (validation de type)."""
        resultat = self.engine.request_tool("outil_chemin", {"path": 42})
        self.assertFalse(resultat.success)

    def test_outil_refuse_une_cle_sensible_imbriquee(self) -> None:
        """Niveau 3 : une clé interdite imbriquée est refusée par le schéma.

        Le contrôle de CLÉS de la politique ne descend pas dans les
        structures imbriquées (comportement historique, inchangé) : c'est
        le rejet des paramètres non déclarés qui ferme la porte.
        """
        resultat = self.engine.request_tool(
            "outil_chemin", {"path": "docs", "options": {"code": "x"}}
        )
        self.assertFalse(resultat.success)


class TestOutilsReelsEtConfinement(unittest.TestCase):
    """Les outils réels : un répertoire « source » est analysable, un hors périmètre non."""

    def setUp(self) -> None:
        self.registry = build_default_registry()
        self.engine = _build_engine(self.registry)
        self._racine = tempfile.mkdtemp(prefix="d3-", dir=str(project_root()))
        self.addCleanup(shutil.rmtree, self._racine, True)
        self.dossier = os.path.join(self._racine, "dossier source")
        os.makedirs(self.dossier, exist_ok=True)
        with open(
            os.path.join(self.dossier, "note.txt"), "w", encoding="utf-8"
        ) as fh:
            fh.write("contenu de test\n")

    def test_listage_d_un_repertoire_nomme_source_reussit(self) -> None:
        """Le défaut D3 etait bloquant : le listage doit maintenant reussir."""
        resultat = _executer_avec_confirmation(
            self.engine,
            "action_list_files",
            {"path": self.dossier, "depth": 1},
        )
        self.assertTrue(resultat.success, resultat.error_message)
        self.assertIn("note.txt", str(resultat.data))

    def test_listage_d_un_chemin_hors_perimetre_refuse(self) -> None:
        """Un chemin hors racines reste refusé, même sans mot suspect."""
        resultat = _executer_avec_confirmation(
            self.engine,
            "action_list_files",
            {
                "path": "C:\\Windows\\System32" if os.name == "nt" else "/etc",
                "depth": 1,
            },
        )
        self.assertFalse(resultat.success)

    def test_lecture_d_un_fichier_sensible_refusee(self) -> None:
        """Les fichiers sensibles restent refusés (contrôle de lecture inchangé)."""
        from app.tools.local_actions import read_file_handler

        with self.assertRaises(PermissionError):
            read_file_handler(path=".env.example")


class TestAucunDroitNouveau(unittest.TestCase):
    """Le correctif n'accorde aucun outil, permission ni racine supplémentaire."""

    def test_la_liste_des_outils_est_inchangee(self) -> None:
        """Les outils enregistrés sont exactement les mêmes.

        S3 : action_write_note est la seule addition volontaire (écriture
        bornée à data/notes, confirmée) — listée ici pour le tracer.
        """
        registry = build_default_registry()
        self.assertEqual(
            registry.list_tools(),
            [
                "action_datetime",
                "action_list_files",
                "action_read_file",
                "action_workdir",
                "action_write_note",
                "status_read",
            ],
        )

    def test_les_permissions_requises_sont_inchangees(self) -> None:
        """Les permissions requises par les outils n'ont pas bougé."""
        registry = build_default_registry()
        attendu = {
            "action_datetime": (),
            "action_list_files": ("lecture_systeme",),
            "action_read_file": ("lecture_systeme",),
            "action_workdir": (),
            # S3 : permission dédiée, sciemment limitée à l'écriture de note.
            "action_write_note": ("ecriture_note",),
            "status_read": (),
        }
        for tool_id, permissions in attendu.items():
            tool = registry.get_tool(tool_id)
            with self.subTest(outil=tool_id):
                self.assertEqual(tuple(tool.required_permissions), permissions)
                self.assertIn(tool.risk_level, ("LOW", "MEDIUM", "HIGH"))

    def test_seul_le_chemin_est_type(self) -> None:
        """Un seul paramètre est typé « chemin » par outil de lecture."""
        registry = build_default_registry()
        typer = {
            tool_id: sorted(
                param.name
                for param in registry.get_tool(tool_id).parameters
                if param.is_path
            )
            for tool_id in registry.list_tools()
        }
        self.assertEqual(typer["action_list_files"], ["path"])
        self.assertEqual(typer["action_read_file"], ["path"])
        self.assertEqual(typer["action_write_note"], ["path"])
        self.assertEqual(typer["action_datetime"], [])
        self.assertEqual(typer["action_workdir"], [])
        self.assertEqual(typer["status_read"], [])

    def test_les_racines_autorisees_sont_inchangees(self) -> None:
        racines = {str(r) for r in default_allowed_roots()}
        self.assertEqual(
            racines, {str(project_root()), str(project_root() / "data")}
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

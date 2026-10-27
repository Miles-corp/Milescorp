# docs/reports/PHASE_6_4B_DIAGNOSTICS_AGENT_A.md - Diagnostics /status et /provider sans test reseau implicite

- **Auteur** : Agent A
- **Date** : 2026-10-24
- **Branche** : `fix/miles-diagnostics`
- **Commit documente** : `78ac05c3732cbed3bf98bd344effb594c95c1e2f`
- **Parent verifie** : `8b857223bf653f25f606e837724ce9f3a6c9d6ec` (D-MEM-01, `fix/miles-memory-persistent`)
- **Upstream** : **absent** (`git rev-parse fix/miles-diagnostics@{upstream}` -> `no upstream configured` ; `git ls-remote origin` : aucune branche `diagnostics`) — la branche est donc **LOCALE ET NON PUBLIEE**.
- **main** : `b9b7e7d` — inchangee. Aucune fusion. Aucun push.

## 1. Objet

Terminer les commandes de diagnostic `/status` et `/provider` (CLI et web) dans un etat
verifiable : **aucun appel reseau implicite, aucun appel a `is_available()`** par une
commande d'affichage ; la disponibilite reste INCONNUE tant qu'aucun controle explicite
n'a ete execute ; aucun secret expose.

## 2. Travail realise (commit 78ac05c)

| Fichier | Contenu |
|---|---|
| `app/interface/cli.py` | `/provider` : fournisseur, mode (remote/local), URL de base et modele expurges (`sanitize_text`), disponibilite « inconnue (aucun test effectue) » ; `/status` : disponibilite « non testee (aucune requete reseau effectuee) », etat memoire/orchestrateur ; suppression du code bancal herite du diff interrompu (ligne `chr(39)`). |
| `app/interface/web.py` | `provider_state()` ne call plus `is_available()` (suppression de l'appel reseau implicite qui touchait notamment le fournisseur local) ; renvoie `available: None` + `availability: "non testee (aucune requete reseau effectuee)"` ; nouvelle route `GET /provider` protegee par `_require_session`, lecture seule, sans secret. |

## 3. Tests reellement executes le 2026-10-24 (poste Windows, Python 3.14)

| Campagne | Commande | Resultat verifie |
|---|---|---|
| Cibles nouvelles | `python -m unittest tests.test_status_provider_diagnostics` | **14/14 OK** (apres correction de 2 defauts de TESTS, pas du produit : stub ignorant le `default`, hypothese erronee sur `sanitize_text`) |
| Fichiers concernes | `python -m unittest tests.test_web tests.test_cli_reliability tests.test_provider_selection tests.test_miles_session_hardening tests.test_web_security tests.test_answer_d1ter_fixes` | **99 OK** |
| Suite complete | `python -m unittest discover -s tests` | **685 tests OK (4 ignores)** en 96,6 s |

Les 4 ignores sont les limites de plateforme connues (Windows) : liens symboliques,
`/proc/self/fd` — inchanges par ce commit.

## 4. Invariants couverts par les tests (tests/test_status_provider_diagnostics.py)

1. `/status` et `/provider` ne declenchent **aucun** appel a `is_available()` (espion qui
   echoue si appele) ;
2. disponibilite affichee comme inconnue/non testee (CLI et web) ;
3. modes remote et local affiches avec leurs URL/modeles ;
4. fournisseur absent gere sans exception ;
5. cles de configuration absentes gerees (`get()` -> None, affichage sans crash) ;
6. mode invalide rejete par `Settings` (jamais silencieusement accepte) ;
7. secrets (`MILES_REMOTE_API_KEY`, `MILES_LOCAL_API_KEY`) absents des sorties CLI ;
8. route web `/provider` : 200 avec etat expurge, **401 sans session** ;
9. route web `/status` : `available` a `null`, zero appel espion.

## 5. Limites et NON VERIFIE

- **Debian 13 : NON VALIDE** — environnement indisponible sur ce poste ; aucune des
  nombres ci-dessus n'a ete obtenu hors Windows.
- **Audit independant d'Agent B : NON REALISE** — cette branche attend l'audit B comme
  toute la chaine post-D1 ; par sequencing elle sera auditee apres D1 (TASK-DEV-019) et
  les zones web sensibles (`1ef4878` D1-bis, `8b9ab15`).
- Compte de tests revendiques dans les rapports des AUTRES branches de la chaine :
  **NON VERIFIE** document par document a ce jour.
- L'UI HTML integree n'appelle pas la nouvelle route `/provider` (route JSON seule).
- Git signale une conversion LF->CRLF a la prochaine manipulation de `cli.py`
  (comportement de depot preexistant, non corrige ici).

## 6. Etat Git au moment de la redaction

- `fix/miles-diagnostics` : `78ac05c` (HEAD), working tree **propre** avant la creation
  de ce rapport — ce rapport est la SEULE modification locale de ce worktree (non
  commitee volontairement : aucun commit n'est demande pour cette mission).
- Branche de coordination `fix/miles-d1-web-authorization` : `9f044f8` (ahead 1 de origin,
  inchangee par cette mission).
- Anomalie connexe documentee (STATUS.md) : `fix/miles-paths-posix-spaces` ne contient
  aucun commit dedie ; presence d'un octet NULL dans le blob D3 `0be08cd`, absent du
  blob courant `9f044f8` — X ni rejoue ni corrige dans cette mission.

# Tri du dépôt MILES — inventaire, corrections et plan

- **Auteur** : Agent A
- **Date** : 2026-10-27
- **Périmètre** : inventaire Git (branches, worktrees), correction de la coordination, liste des actions destructives soumises à accord.
- **Hors périmètre** : développement fonctionnel du cockpit (traité dans `PHASE_7_COCKPIT_AGENT_A.md`), fusion de `main`, publication sur GitHub.

## 1. Méthode

Commandes utilisées (reproductibles) :

```bash
git fetch --all --prune
git worktree list
git for-each-ref --sort=-committerdate refs/remotes/origin
for b in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin); do
  git rev-list --count origin/integration/miles-post-d1..$b
  git merge-base --is-ancestor $b origin/integration/miles-post-d1 && echo fusionnee
done
python -m unittest discover -s tests -q
```

## 2. Constat principal : `main` n'est plus la vérité du code

| Élément | `main` (`b9b7e7d`) | `integration/miles-post-d1` (`05b7b82`) |
|---|---|---|
| Commits | référence | **+69** |
| Fichiers suivis | 108 | **201** |
| `app/interface/web.py` | 404 lignes, 5 routes | **1652 lignes, 18 routes** |
| Fichiers de tests | 16 | **60** |
| Tests exécutés (Windows) | 146 OK | **816 : 814 OK, 2 échecs environnementaux, 5 ignorés** |
| Dernier commit | 2026-10-20 | 2026-10-27 |

Les deux échecs ne viennent pas du code : le fichier `.env` présent sur ce poste écrase les valeurs par défaut attendues par `tests/test_status_provider_diagnostics.py` (URL et modèle par défaut). Preuve : avec `MILES_ENV_FILE` pointant sur un fichier absent, le module passe **14/14**. Ce comportement est un piège de test à corriger (tests non hermétiques à l'environnement), mais il est hors périmètre de ce tri.

`main` est la branche par défaut de GitHub : un lecteur qui arrive sur le dépôt voit donc un état vieux de sept jours et de 69 commits. **Décision demandée : réaligner `main` sur l'intégration** (fusion locale, aucun push sans accord — DEC-004).

## 3. Branches : 29 hors `main`, 22 fusionnées, 7 non

### 3.1 Fusionnées dans l'intégration — suppression proposée (22)

`fix/miles-diagnostics`, `fix/miles-memory-persistent`, `fix/miles-answer-authorization-only`, `test/miles-read-only-trust-boundaries`, `integration/miles-phases-5-6-6-1`, `fix/miles-windows-paths`, `fix/miles-session-hardening`, `fix/miles-results-persistence`, `fix/miles-read-only-prudent-type`, `fix/miles-policy-path-typing`, `fix/miles-mission-persistence-owner`, `fix/miles-mission-bounds`, `fix/miles-d1bis-authorization-response`, `fix/miles-answer-d1ter`, `fix/miles-web-authorization-security`, `fix/agent-b-s002-s004-s005-s006`, `feature/miles-v1-conversation-persistence`, `feature/miles-tool-engine-integration`, `feature/miles-mission-orchestrator`, `review/phase4-security-fixes`, `review/agent-b-phase4-review`, `fix/agent-b-s001-s003-memory-config`.

Leur contenu est intégralement contenu dans `integration/miles-post-d1` : la suppression ne perd aucun commit. Elle supprime seulement la trace des noms de branches.

### 3.2 Non fusionnées — à conserver et à trancher (7)

| Branche | Avance | Retard | Contenu non intégré |
|---|---|---|---|
| `fix/miles-d1-web-authorization` | +26 | −35 | Spec mémoire avancée v1, préflight « boîtier » Q3, catalogue v1.4, réconciliations MI-013…MI-022 |
| `audit/agent-b-phase6-1-web-security-review` | +12 | −52 | Audit contradictoire Agent B (2026-10-25/26) |
| `audit/agent-b-v1-review` | +7 | −59 | Contre-audit final V1 |
| `audit/agent-b-phase6-orchestrator-review-v2` | +2 | −53 | Réaudit orchestrateur (verdict sous réserves) |
| `audit/agent-b-phase6-orchestrator-review` | +3 | −54 | Première version du réaudit |
| `investigation/d1ter-and-answer-path` | +1 | −32 | Caractérisation du défaut D1-ter |
| `work/agent-a-phase4-audit` | +1 | −71 | Audit complémentaire Phase 4 |

Ces sept branches contiennent des **documents** (rapports, audits, specs) jamais fusionnés. Les fusionner est le seul moyen de les rendre visibles sans perdre l'historique. Aucune n'est supprimable en l'état.

### 3.3 Branches locales sans équivalent distant — risque de perte (2)

| Branche | Commits uniques | Contenu | Situation |
|---|---|---|---|
| `feature/miles-multi-provider` | 2 | Gestionnaire multi-fournisseurs (L1) + adaptateurs Anthropic/Gemini (L2), 25 tests annoncés | **Local uniquement**, worktree `%TEMP%\miles-merge`, **5 fichiers non commités** |
| `feature/miles-memoire-avancee` | 1 | Mémoire v3 : `kind`, liens contradictoires, visibilité par propriétaire, 17 tests | **Local uniquement**, non poussée |

**Action prioritaire** : pousser ces deux branches (ou les fusionner) avant tout nettoyage. Un `git worktree remove` ou une purge de `%TEMP%` les détruirait. Je ne touche à aucune des deux.

## 4. Worktrees : 16 enregistrés, 14 dans `%TEMP%`

| # | Chemin | Branche | Sale |
|---|---|---|---|
| 1 | `C:\Users\StanC\Desktop\Milescorp` | `fix/miles-d1-web-authorization` | non |
| 2 | `.freebuff\worktrees\d7b7b78a\Milescorp` | `feat/miles-cockpit-ui` | non (session courante) |
| 3-15 | `%TEMP%\miles-answer`, `miles-answeronly`, `miles-d1bis`, `miles-d2`, `miles-d3`, `miles-diag`, `miles-invest`, `miles-memory`, `miles-merge`, `miles-persist`, `miles-results`, `miles-trust`, `miles-trustfix` | correctifs et audits déjà fusionnés | `miles-diag` (1 fichier non suivi), `miles-merge` (5) |
| 16 | `%TEMP%\miles-preview` | HEAD détachée `f565528` | non |

Les treize worktrees de correctifs (3 à 12, 14, 15) portent des branches **déjà fusionnées** : les retirer ne perd rien. `miles-preview` est une HEAD détachée à identifier avant suppression.

## 5. Coordination : défauts trouvés et corrigés

| Défaut | Preuve | Correction |
|---|---|---|
| `TASK-DEV-008` portait **deux** tâches | Phase 4 (Agent A) et Phase 3B (Agent B) | Phase 3B → **`TASK-DEV-042`**, mention de renommage |
| `TASK-DEV-029` et `TASK-DEV-030` portaient **deux** tâches chacun | 6.3h et 6.4a (mémoire) | mémoire → **`TASK-DEV-040`**, audit → **`TASK-DEV-041`** |
| Ligne Phase 3B **cassée** : 9 cellules au lieu de 10 | colonne Description absente, colonnes décalées | ligne reconstruite, **toutes les lignes à 10 colonnes** (vérifié) |
| `M-004` **dupliqué**, `M-010` inexistant | deux messages Agent A du 2026-10-19 | second `M-004` → **`M-017`**, note explicite |
| `STATUS.md` figé au **2026-10-19** | état général décrivant la Phase 3B | bloc de tête remplacé par l'état du 2026-10-27 ; historique conservé |
| `docs/reports/PHASE_6_4A…` référençait l'ancien identifiant | ligne 193 | référence mise à jour vers `TASK-DEV-040` |

Vérifications exécutées : `grep` d'unicité des identifiants (aucun doublon), comptage des colonnes sur les **46 lignes de tâches** (10 partout), décision consignée en **DEC-013**.

## 6. Rapports : 45 fichiers, ne pas supprimer

`docs/reports/` contient 45 rapports, dont plusieurs sur la même phase (`PHASE_4_*` ×7, `PHASE_6_3*` ×12). Ce ne sont pas des doublons : chacun documente une correction ou un audit distinct, avec ses preuves. **Recommandation : ne rien supprimer**, produire un `docs/reports/INDEX.md` qui les classe par phase et par auteur. Non fait ici pour ne pas mêler tri et documentation.

## 7. Actions

**Faites (ce rapport)** : inventaire complet, corrections de coordination, DEC-013, `STATUS.md` remis à la vérité, références d'identifiants mises à jour.

**Soumises à votre accord explicite** :

1. Supprimer les **22 branches distantes fusionnées** (§3.1).
2. Retirer les **13 worktrees temporaires** de correctifs fusionnés + `miles-preview` après identification.
3. Réaligner **`main`** sur `integration/miles-post-d1` (local, sans push).
4. Fusionner les **7 branches non fusionnées** (documents d'audit) dans l'intégration.

**Refusées d'office, sans votre accord** : toucher à `feature/miles-multi-provider` et `feature/miles-memoire-avancee` (travail local unique), supprimer un rapport, réécrire l'historique.

## 8. Limites

- Aucune suppression n'est exécutée à ce stade : la liste est proposée, pas appliquée.
- L'état des branches distantes date du `fetch` du 2026-10-27 ; il devra être rafraîchi avant exécution.
- Les tests n'ont pas été exécutés sous Debian 13 (VM d'audit injoignable) : le tri ne change pas cette limite.

# docs/reports/AUDIT_PC_MONITOR_POINT8_AGENT_B.md — Audit contradictoire PC Monitor, Point 8 (Agent B)

> Audit contradictoire demandé par le responsable de projet.
> **RÉSULTAT : audit partiellement vérifiable — le dépôt PC Monitor n'est pas accessible depuis cet environnement.**

## 1. Identité — ce que j'ai pu établir

| Élément | Valeur | Statut |
|---|---|---|
| Dépôt attendu | non communiqué dans la mission | ❌ non identifié |
| Branche candidate | « branche candidate » vs `master` | ❌ non identifiée |
| SHA de la branche candidate | non communiqué | ❌ **non vérifiable** |
| SHA de base | non communiqué | ❌ non vérifiable |
| SHA proposé à l'intégration | non communiqué | ❌ non vérifiable |

### Recherche effectuée sur le poste de l'agent

| Candidat examiné | Chemin | État constaté |
|---|---|---|
| `JARVIS` | `C:\Users\iopjk\Documents\GitHub\JARVIS` | Dépôt Git **complètement vide** : remote `https://github.com/iopjklad-pixel/JARVIS.git`, `git ls-remote origin` → **code de sortie 0 et aucune sortie** (dépôt accessible mais **zéro référence**), `git show-ref` → **0 référence**, aucun index, `.git` de 26 Ko, **0 fichier** hors `.git` |
| `jarvis-OS` (sauvegarde) | `C:\Users\iopjk\jarvis-OS_clean_backup_20261016_222729` | 50 163 fichiers, remote `https://github.com/Grominet95/jarvis-OS` (fork d'un projet amont), HEAD `5702002`, **projet Python** (`src/jarvis/…`, `bundle/`, `skills_data/`) — **aucune application Electron**, aucun `main.js`, aucun `renderer`, aucun `ipcMain`/`ipcRenderer`, aucun `shell:showInExplorer`, aucun PC Monitor |
| Recherche globale | `C:\Users\iopjk` (hors caches) | **0 occurrence** de `showInExplorer` ; **0** `package.json` contenant la dépendance `electron` ; aucun `package.json` applicatif hors `scripts/doc_helper/` |

### Conclusion sur l'accès

Le **PC Monitor n'est pas présent sur cette machine**. Le seul dépôt au nom compatible (`JARVIS`) pointe vers un remote **existant mais vide** — ce qui correspond précisément au risque signalé par la mission : *« vérifier que PC Monitor ne dépend pas d'un remote fictif ou non configuré »*. **Le remote est configuré, mais il ne contient rien** : le travail PC Monitor n'y est pas publié.

## 2. Reproduction

### 2.1 Commandes réellement exécutées

```powershell
Get-ChildItem "$env:USERPROFILE\Documents\GitHub" -Directory
Get-ChildItem "$env:USERPROFILE" -Directory -Recurse -Depth 3 | Where-Object Name -eq '.git'
git -C <JARVIS> remote -v ; git -C <JARVIS> show-ref ; git -C <JARVIS> ls-remote origin
git -C <jarvis-OS> branch -a ; git -C <jarvis-OS> for-each-ref refs/heads refs/remotes/origin
Get-ChildItem <jarvis-OS> -Recurse -Include *.js,*.cjs,*.mjs,*.html | Select-String 'showInExplorer|pcMonitor|ipcMain|ipcRenderer'
Get-ChildItem "$env:USERPROFILE" -Recurse -Include *.js,*.cjs,*.mjs,*.ts | Select-String 'showInExplorer'
Get-ChildItem "$env:USERPROFILE" -Recurse -Depth 4 -Filter package.json | Where-Object { (Get-Content $_ -Raw) -match '"electron"' }
```

### 2.2 Résultats

| Contrôle | Résultat |
|---|---|
| Dépôt PC Monitor identifié | ❌ **non** |
| SHA de branche candidate | ❌ **non vérifiable** |
| Diff vs `master` | ❌ **non vérifiable** |
| Correctif `shell:showInExplorer` inspecté | ❌ **non vérifiable** |
| Contournement IPC par le renderer | ❌ **non vérifiable** |
| Chemins autorisés / hors racine / `..` / symlinks / entrées malformées | ❌ **non vérifiable** |
| Modifications de `main.js` préservées | ❌ **non vérifiable** |
| Garde-fou FPS, B5, B7, comparaison iGPU/dGPU A/B/A/B | ❌ **non vérifiable** |
| Données absentes ≠ zéro, mesures simulées étiquetées | ❌ **non vérifiable** |
| Contrats IPC et protections Electron | ❌ **non vérifiable** |
| Tests + ESLint | ❌ **non exécutables** (pas de sources) |
| « 180 tests annoncés » | ❌ **non reproduits, non inspectés** — traité comme *non vérifié* |

**Nombre de tests réussis / échoués / ignorés : 0 / 0 / 0 — aucun test n'a pu être lancé, faute de code.** Aucun résultat n'est déclaré « réussi ».

## 3. Défauts

Aucun défaut de code n'est déterminable : **aucune ligne du PC Monitor n'est accessible**. Le seul constat vérifiable est un défaut d'accessibilité du livrable :

### D-PC01 — Le dépôt PC Monitor est vide / non publié

| | |
|---|---|
| **Gravité** | **P1 — bloquant pour l'audit** (pas un défaut de code du produit, un défaut de livraison) |
| **Preuve reproductible** | `git -C JARVIS ls-remote origin` → sortie vide, code 0 ; `git -C JARVIS show-ref` → 0 référence ; `Get-ChildItem JARVIS -Recurse -File -Force` (hors `.git`) → 0 fichier ; recherche globale → 0 occurrence de `showInExplorer`, 0 application Electron |
| **Impact** | Aucun audit indépendant du Point 8 n'est possible : ni le correctif `shell:showInExplorer`, ni le confinement des chemins, ni les protections IPC/Electron, ni les tests FPS/B5/B7/iGPU-dGPU, ni la baseline ESLint ne peuvent être vérifiés. Le nombre « 180 tests » reste une **déclaration non vérifiée**. |
| **Correction nécessaire** | Publier le travail PC Monitor sur le remote `iopjklad-pixel/JARVIS` (branches `master` et branche candidate), ou fournir l'archive/patch correspondant, puis relancer l'audit. |
| **Résultat du nouveau test** | Sans objet : aucun test n'est exécutable. |

## 4. Décision finale — PC Monitor

# PARTIELLEMENT VÉRIFIÉ

**Motif** : *environnement ou accès manquant*. L'audit n'a pas pu être conduit : le dépôt est absent/vide sur ce poste, et aucun autre candidat ne contient le code PC Monitor.

**Ce qui reste à faire, manuellement, dans l'ordre :**

1. **Publier ou fournir le code** PC Monitor :
   ```bash
   git -C "C:/Users/iopjk/Documents/GitHub/JARVIS" fetch origin
   git -C "C:/Users/iopjk/Documents/GitHub/JARVIS" branch -a
   ```
   Si le remote reste vide, pousser la branche candidate sur `iopjklad-pixel/JARVIS`, **ou** fournir une archive du dépôt et son SHA.
2. **Communiquer** : nom exact de la branche candidate, SHA exact, SHA de base (`master`), SHA proposé à l'intégration.
3. **Relancer l'audit** avec ces éléments. Il couvrira alors :
   - correctif `shell:showInExplorer` dans le processus principal ;
   - impossibilité pour le renderer de contourner les validations IPC (comparaison de la surface IPC exposée) ;
   - chemins autorisés / hors racine / traversées `..` / liens symboliques / entrées malformées ;
   - préservation des modifications parallèles de `main.js` (le diff doit rester ciblé) ;
   - garde-fou FPS, B5, B7, comparaison iGPU/dGPU en A/B/A/B (détection d'une dérive de mesure) ;
   - distinction « donnée absente » vs « zéro » et étiquetage explicite des mesures simulées ;
   - exécution de la suite **et** d'ESLint, avec une **baseline vérifiable** séparant les erreurs ESLint préexistantes des nouvelles.

**Aucun verdict de sécurité n'est émis sur PC Monitor** : ni « AUTORISÉ À FUSIONNER », ni « REFUSÉ » — la code n'a pas été vu. Le seul état défendable est *non vérifié*.

---

*Audit réalisé par Agent B le 2026-10-20. Recherche exhaustive sur `C:\Users\iopjk` (dépôts `JARVIS` et `jarvis-OS_clean_backup_20261016_222729`), recherche globale de `showInExplorer` et de projets Electron. Aucun test exécuté (aucun code accessible) : 0 réussi, 0 échoué, 0 ignoré — aucun résultat n'est présenté comme réussi. Aucune modification de dépôt, aucun push, aucune fusion, aucune suppression de branche.*

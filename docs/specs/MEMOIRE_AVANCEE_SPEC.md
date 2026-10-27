# Spécification — Mémoire avancée (catalogue §2)

- **Statut** : PROPOSITION à valider — **aucun code écrit**, `persistent.py` intact.
- **Auteur** : Agent A · Date : 2026-10-27 · Modèle utilisé : MiMo-V2.6-Flash (niveau 2-3).
- **Pourquoi une spec d'abord** : l'isolation mémoire vient d'être validée
  (MI-016, audit B) ; toute évolution doit la préserver, et la détection de
  contradictions touche à la crédibilité du produit (jamais d'affirmation fausse).
- **Validation requise** : utilisateur (produit) + audit B (persistant.py) avant implémentation.

## 1. Objectifs (du catalogue §2, statut « Non commencée / Partielle »)

| # | Objectif | Existant | Ce que la spec vise |
|---|---|---|---|
| 1 | Résumés de conversations/souvenirs | Aucun | Rappel compact lisible dans le contexte IA et par commande |
| 2 | Contradictions entre souvenirs détectées/signales | Aucun | Détection **toujours signalée comme hypothèse**, jamais affirmée |
| 3 | Faits confirmés distingués des hypothèses et inconnues | Aucun | 3 valeurs explicites ; **jamais** d'auto-promotion en « fait » |
| 4 | Informations pertinentes retrouvées au bon moment | Partiel (`get_context_memories`) | Recherche par terme + priorité par kind/catégorie |

## 2. Invariants non négociables (hérités de l'audit B)

1. **Isolation par propriétaire** préservée sur toutes les nouvelles lectures/
   écritures (`owner_user_id` + partagés), y compris résumés et liens.
2. **Migration non destructive** : nouvelle version de schéma par ajout de
   colonnes avec défauts (même mécanique que `owner_user_id`, v2), base
   absente → création, base corrompue → dégradation gracieuse.
3. **Aucun secret** : réutiliser `_contains_secret` sur tout nouvel enregistrement ;
   aucun contenu de souvenir dans un message d'erreur.
4. **Zéro réseau par défaut** : aucune opération ne déclenche d'appel au
   fournisseur sans configuration explicite et accord de coût (charte §3).
5. **Aucune mutation des souvenirs existants** lors d'une migration.

## 3. Modèle de données proposé (schéma v3)

```sql
-- Ajout sur memories (défauts = comportement historique préservé)
ALTER TABLE memories ADD COLUMN kind TEXT NOT NULL DEFAULT 'inconnu';
-- valeurs : 'fait' | 'hypothese' | 'inconnu'  (défaut = inconnu)

-- Nouveau : liens entre souvenirs (contradictions / renforcements)
CREATE TABLE IF NOT EXISTS memory_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    relation TEXT NOT NULL,          -- 'contradit' | 'renforce' | 'duplique'
    confidence TEXT NOT NULL DEFAULT 'signale',  -- 'signale' | 'confirme'
    created_at TEXT NOT NULL,
    UNIQUE(source_id, target_id, relation)
);
```

**Règles kind** :
- `inconnu` = défaut de `/remember` (honnête : rien n'est prouvé) ;
- `fait` = promu **uniquement** par confirmation humaine (`/fait <id>`) ;
- `hypothese` = proposition explicite (`/hypothese <texte>`), jamais auto ;
- lecture : le contexte IA marque `[fait]` / `[hypothèse]` dans les éléments injectés.

## 4. Détection de contradictions (sécurité anti-faux-positif)

**Principe : la machine propose, l'humain (ou un modèle sous accord) dispose.**

1. **Règles strictes déterministes (v1, zéro réseau)** — à l'ajout d'un souvenir :
   - contenu **identique** (hors normalisation) → lien `duplique` ;
   - **négation directe détectable** : mêmes termes avec bascule de négation
     (« X est actif » ↔ « X n'est pas actif », « toujours » ↔ « jamais ») →
     lien `contradit`, `confidence='signale'` ;
   - **jamais** de reformulation : un faux positif annoncé est préférable à une
     fausse négation ? Non : une règle trop large est préférée **étroite** →
     on n'égare pas les contradictions réelles ? → décision produit : règles
     étroites d'abord (recall partiel assumé), élargissement après mesure des
     faux positifs.
2. **v2 (sous accord coût + fournisseur configuré)** : analyse sémantique
   batch, sortie = propositions de liens affichées dans `/contradictions`
   avec `confidence='signale'` — **jamais écrit comme `confirme`** sans `/confirmer <id>`.

**Commandes proposées** :
- `/contradictions` — lister les liens `contradit`/`duplique` signalés ;
- `/confirmer <id-lien>` — passer en `confirme` (humain) ;
- `/fait <id>` / `/hypothese <texte>` — gestion du kind.

## 5. Résumés (v1 : règle, pas d'IA)

- `resume_memoire(owner, max_car)` : concatène par ordre (kind : faits d'abord,
  puis hypothèses, puis inconnus), tronqué à `max_content_length` existant,
  expurgé des secrets, **marques `[fait]`/`[hypothèse]`**.
- Sortie : fonction pure testable ; branchée dans `get_context_memories` (option
  `resume=True`, **désactivée par défaut** pour ne pas changer le comportement actuel).
- v2 IA : résumé généré uniquement si fournisseur configuré + accord coût.

## 6. Tests prévus (avant toute écriture de code)

1. Isolation : chaque nouveau point d'accès rejoue les tests MI-016 (alice/bob) ;
2. Migration v3 sur base temporaire : colonnes ajoutées, données préservées, défauts `inconnu` ;
3. Base absente / corrompue : inchangés ;
4. Kind : auto = `inconnu` ; promotion en `fait` seulement par commande ;
5. Détection : contenu identique → duplique ; négation stricte → contradi; négation fausse → **rien** (règle étroite) ;
6. Aucun réseau : garde statique (pas d'import urllib dans le module) ;
7. Aucun secret : contenu de souvenir jamais dans erreur/journal.

## 7. Risques résiduels (à connaître avant validation)

- **Recall partiel** : les contradictions qui ne suivent pas la règle stricte ne
  sont pas détectées (choix assumé, mesuré ensuite) ;
- **Coût** : toute analyse sémantique v2 = appel fournisseur → accord obligatoire ;
- **Taille de contexte** : résumés + mémoires doivent respecter
  `memory_max_memories_in_context` et `memory_max_content_length` (existant) ;
- **Conflit de migration** : un jour, fusionner avec les éventuelles
  modifications concurrentes de `persistent.py` (règle : une seule branche à la fois).

## 8. Livraison par étapes (après validation)

1. Branche `feature/miles-memoire-avancee` depuis l'intégration courante ;
2. Schéma v3 + commandes v1 (règles strictes) + tests §6 ;
3. Revue utilisateur sur `/contradictions` en conditions réelles ;
4. **Audit B de `persistent.py`** (MI-016 doit rester vert) ;
5. Debian 13 (MI-006 refait sur le tip) ;
6. v2 IA seulement si accord coût donné.

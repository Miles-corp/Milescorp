# docs/reports/PHASE_6_4A_MEMORY_PERSISTENCE_AGENT_A.md — Mémoire persistante : état, défaut d'isolation et correctif

- **Auteur** : Agent A
- **Date** : 2026-10-21
- **Base de travail** : `54bd13859602ab007d955115f6273dc2ca9fdb6a` (`fix/miles-results-persistence` : D1 + D2 + D1-bis + D3 + A-α/B-α + D-B05 + D-B05-restants)
- **Branche** : `fix/miles-memory-persistent`
- **`main`** : `b9b7e7d` — **inchangée** · **Intégration** : `69bf670` — **inchangée**
- **D1 / D2 / D1-bis / D3 / A-α·B-α / D-B05 / D-B05-restants** : **inchangées**

> **Aucune fusion.** Les audits D1, D2, D1-bis, D3, A-α/B-α, D-B05 et
> D-B05-restants sont **en cours** ; ce correctif n'est pas validé.
> Aucun appel API payant, aucune donnée réelle modifiée.

---

## 1. État des lieux initial (sur le code réel, pas sur l'existence du code)

### 1.1 Les trois commandes

| Commande | Console (`app/interface/cli.py`) | Web (`app/interface/web.py`) | État constaté |
|----------|-----------------------------------|-----------------------------|---------------|
| `/remember <texte>` | présente (l. ~1130) | `POST /remember` → `_handle_remember` | **opérationnelle** (identifiant renvoyé, contenu enregistré) |
| `/memory` | présente (l. ~1145) | `GET /memory` → `_handle_list_memories` | **opérationnelle** (liste `id`, `content`, `category`, `importance`, `created_at`, `updated_at`) |
| `/forget <id>` | présente (l. ~1160) | `POST /forget` → `_handle_forget` | **opérationnelle** (suppression par identifiant, message explicite si l'identifiant est absent ou non numérique) |

### 1.2 Le stockage

`app/memory/persistent.py::PersistentMemory` — base SQLite locale
(`data/memory.db` par défaut), deux tables :

| Table | Contenu |
|-------|---------|
| `memories` | `id`, `content`, `category`, `importance`, `created_at`, `updated_at` |
| `preferences` | `key`, `value`, `updated_at` |

Garde-fous en place : refus des contenus ressemblant à un secret (clé API,
mot de passe, jeton), longueur bornée (`max_content_length`, 1000 par
défaut), refus du contenu vide, dégradation gracieuse si la base est
endommagée (`is_available` → `False`, aucune exception), connexion partagée
protégée par un `RLock`.

### 1.3 La persistance après fermeture et redémarrage

La base est un **fichier** : les souvenirs et les préférences survivent à la
fermeture du processus ✓ (vérifié par test : `test_les_souvenirs_survivent_a_un_redemarrage`).

### 1.4 Le lien avec l'historique de conversation et l'identité de l'utilisateur

| Lien | Constat |
|------|---------|
| Souvenirs ↔ historique de conversation | **aucun** : `PersistentMemory` ne connaît pas la conversation ; rien n'est enregistré automatiquement (choix documenté : le stockage est **exclusivement** à la demande de l'utilisateur) |
| Souvenirs ↔ identité de l'utilisateur | **AUCUN** : la table `memories` n'a pas de colonne de propriétaire ; `app/memory/persistent.py` ne contient **aucune** occurrence de `user_id`, `session` ou `identity` ; `WebApp.add_memory` / `list_memories` / `delete_memory` ne reçoivent **aucun** identifiant ; les handlers `_handle_remember` / `_handle_forget` / `_handle_list_memories` ne reçoivent **pas** la session |

→ **Défaut D-MEM-01 (P2)** : dans l'interface web multi-utilisateurs, les
souvenirs ne sont rattachés à personne : **tout utilisateur authentifié voit
et peut supprimer les souvenirs des autres**.

### 1.5 Tests existants

| Fichier | Contenu | Couverture du sujet |
|----------|---------|---------------------|
| `tests/test_memory_persistence.py` | 18 tests (schéma, activation, CRUD, catégories, longueurs, préférences, secret, base corrompue) | **le propriétaire n'est pas couvert** (il n'existe pas) |
| `tests/test_web.py::TestWebMemory` | 5 tests (liste vide, `/remember`+`/memory`, `/forget`, mémoire désactivée, identifiant invalide) | **un seul utilisateur** → l'isolation n'est pas couverte |

---

## 2. Le défaut D-MEM-01, reproduit

**Attendu** : les données d'un utilisateur ne sont pas accessibles à un autre.

**Constaté avant correction** (mesuré) : la base ne contient aucun
propriétaire ; n'importe quel utilisateur authentifié obtient la liste
**complète** et peut supprimer n'importe quel souvenir.

La reproduction est portée par les tests de la classe
`TestIsolationEntreUtilisateurs` :

```
=== SANS LE CORRECTIF (revert des 2 fichiers de production) ===
  ERROR: test_le_proprietaire_est_persiste
  ERROR: test_les_souvenirs_existants_sont_partages
  ERROR: test_un_utilisateur_ne_peut_pas_supprimer_les_souvenirs_d_un_autre
  ERROR: test_un_utilisateur_ne_voit_pas_les_souvenirs_d_un_autre
  Ran 17 tests — FAILED (errors=4)
```

**Gravité : P2 (mineure)**, et non P1 : l'interface web est **strictement
locale** (`127.0.0.1` uniquement, serveur lié à une seule adresse) et
l'authentification est requise ; l'exploitation suppose un accès local à la
machine ou plusieurs comptes configurés sur le même poste. L'impact porte sur
la **confidentialité entre utilisateurs** d'un même poste, pas sur
l'accès à distance.

---

## 3. Correctif

### 3.1 `app/memory/persistent.py`

| Modification | Détail |
|--------------|--------|
| `SCHEMA_VERSION` | 1 → **2** |
| Schéma `memories` | nouvelle colonne `owner_user_id TEXT NOT NULL DEFAULT ''` |
| Migration | `ALTER TABLE memories ADD COLUMN owner_user_id …` si la colonne manque (même mécanisme que la migration `budget_json` du magasin de missions) — **les bases existantes sont préservées, sans perte de données** |
| `add_memory(..., owner_user_id="")` | le propriétaire est écrit |
| `list_memories(..., owner_user_id=None)` | si un propriétaire est fourni : ses souvenirs **et** les souvenirs **partagés** (propriétaire vide) |
| `get_memory(..., owner_user_id=None)` | même filtrage |
| `delete_memory(..., owner_user_id=None)` | suppression restreinte au propriétaire (ou partagé) |

**Choix du modèle** : le propriétaire vide (`""`) désigne un souvenir
**partagé** (console locale, qui n'a pas d'identité d'utilisateur). Les
souvenirs antérieurs à l'isolation restent partagés : ils ne sont **pas**
attribués arbitrairement à quelqu'un, et aucun n'est perdu.

### 3.2 `app/interface/web.py`

- `WebApp.list_memories(owner_user_id=None)`, `add_memory(content, owner_user_id="")`,
  `delete_memory(memory_id, owner_user_id=None)` ;
- les handlers `_handle_remember`, `_handle_forget` et `_handle_list_memories`
  reçoivent désormais la **session** et transmettent `session.user_id`.

### 3.3 `app/interface/cli.py` — **inchangé**

La console est une console locale mono-utilisateur : elle n'attribue pas de
propriétaire (souvenirs partagés) et continue de lister la base entière,
comme avant. **Aucun changement de comportement** pour la console.

### 3.4 Ce qui n'a **pas** été touché

Les routes d'autorisation, les contrôles de chemins (D2), la politique de
sécurité, les permissions, le confinement, l'orchestrateur de missions et
toutes les autres branches de travail : **rien n'y a été modifié**.

---

## 4. Tests

`tests/test_memory_persistence.py` — **17 tests**, non destructifs (bases et
répertoires temporaires, aucun fournisseur, aucune donnée réelle).

| # | Exigence de la mission | Test |
|---|------------------------|------|
| 1 | Enregistrer un souvenir | `test_enregistrer_un_souvenir` |
| 2 | Le retrouver avec la liste | `test_retrouver_un_souvenir_par_la_liste` |
| 3 | Le supprimer par identifiant | `test_supprimer_un_souvenir_par_identifiant` |
| 4 | Après redémarrage, les souvenirs sont toujours là | `test_les_souvenirs_survivent_a_un_redemarrage` (+ `test_les_preferences_survivent_a_un_redemarrage`) |
| 5 | Un souvenir supprimé ne réapparaît pas | `test_un_souvenir_supprime_ne_reapparait_pas` |
| 6 | Base absente / vide / endommagée | `test_base_absente_elle_est_creee`, `test_base_vide_elle_est_initialisee`, `test_base_endommagee_degradation_gracieuse`, `test_memoire_desactivee_operations_refusees` |
| 7 | Isolation entre utilisateurs | `test_un_utilisateur_ne_voit_pas_les_souvenirs_d_un_autre`, `test_un_utilisateur_ne_peut_pas_supprimer_les_souvenirs_d_un_autre`, `test_le_proprietaire_est_persiste`, `test_les_souvenirs_existants_sont_partages` |
| + | Les trois commandes de la console | `test_les_commandes_existent`, `test_cycle_complet_en_console`, `test_une_reponse_incomprenable_ne_supprime_pas` |

**Régression** : 4 tests en erreur sans le correctif (§2) ✓.

---

## 5. Commandes et résultats (plateforme : **Windows**, Python 3.12.10)

| Commande | Résultat |
|----------|----------|
| `python -m unittest tests.test_memory_persistence` | **17 tests, 0 échec** (0,5 s) |
| `python -m unittest tests.test_memory_persistence` *(revert du correctif)* | **4 erreurs** |
| `python -m unittest tests.test_memory_persistent` (existant) | 18 tests, 0 échec |
| `python -m unittest tests.test_web` | 14 tests, 0 échec |
| `python -m unittest tests.test_cli_reliability` | 5 tests, 0 échec |
| `python -m unittest tests.test_miles_entrypoint` | 5 tests, 0 échec |
| `python -m unittest tests.test_settings_memory_config` | 15 tests, 0 échec |
| `python -m unittest tests.test_defects_agent_b` | 26 tests, 0 échec |
| `python -m unittest discover -s tests` | **671 tests, 0 échec, 4 ignorés** (182,3 s) |
| Tests d'audit d'Agent B (rejoués tels quels) | **70 tests, 0 échec, 2 ignorés** (25,4 s) |

**Tests ignorés** (4 + 2) : limites de plateforme Windows (liens
symboliques, `/proc/self/fd`) ; ils s'exécutent sous Debian 13.

> **Debian 13 n'a pas pu être testé** : la machine virtuelle de l'audit
> d'Agent B (`ssh -p 2222 miles@127.0.0.1`) est **injoignable** depuis ce
> poste (connexion refusée). **La validation Debian 13 n'est donc pas
> déclarée** ; seul le résultat Windows est rapporté.

**Appels API payants** : aucun (aucun fournisseur n'est configuré dans les
tests ; le catalogue et le rapport le précisent).

---

## 6. Fichiers modifiés

| Fichier | Modification | Volume |
|---------|--------------|--------|
| `app/memory/persistent.py` | propriétaire persistant (schéma, migration, CRUD filtré) | +55 / −25 |
| `app/interface/web.py` | identité de l'utilisateur propagée jusqu'à la mémoire | +18 / −6 |
| `tests/test_memory_persistence.py` | **nouveau** — 17 tests | +340 |
| `docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md` | catalogue (ligne 12) + section §4.11 | +30 |
| `docs/reports/PHASE_6_4A_MEMORY_PERSISTENCE_AGENT_A.md` | **nouveau** — ce rapport | — |
| `docs/coordination/*` | TASK-DEV-040 (renommée depuis TASK-DEV-029 le 2026-10-27, DEC-013), M-016, H-012 | — |

---

## 7. Limites restantes

| # | Limite | Statut |
|---|--------|--------|
| 1 | La base n'est pas chiffrée : les souvenirs sont lisibles par tout processus ayant accès au fichier | inhérent au stockage local ; **hors périmètre** (chiffrement = décision d'architecture) |
| 2 | Les souvenirs « partagés » (propriétaire vide, console locale) sont visibles de tous les utilisateurs du web | choix explicite : ne pas attribuer arbitrairement les souvenirs historiques ; à arbitrer par Agent B |
| 3 | Aucun lien souvenir ↔ historique de conversation | choix d'origine (le stockage est **exclusivement** à la demande) ; le sujet « lien éventuel » reste **ouvert** : aucun mécanisme d'extraction automatique n'existe |
| 4 | Le filtre anti-secret repose sur une liste de mots : un souvenir contenant « token » est refusé (faux positif possible sur un mot innocent) | comportement préexistant, non modifié ; documenté dans le guide |
| 5 | Aucun test sous Debian 13 | VM injoignable ; à exécuter par Agent B |
| 6 | Le compteur `identifiant` des souvenirs est global et séquentiel : un utilisateur peut deviner l'identifiant d'un souvenir d'un autre | sans effet (la suppression et la lecture sont filtrées par le propriétaire) ✓ |

---

## 8. Proposition de mise à jour du catalogue

Le catalogue (`docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md`, §1) ne
mentionnait pas la mémoire persistante. Ajout effectué (ligne 12) :

| # | Fonction | État | Comment |
|---|----------|------|---------|
| 12 | Mémoire persistante (`/remember`, `/memory`, `/forget`) | ✅ **opérationnelle** (souvenirs conservés après redémarrage, isolation par utilisateur — branche `fix/miles-memory-persistent`) | §4.11 |

**Statut de chaque fonctionnalité de mémoire** (état initial → état final) :

| Fonctionnalité | État initial | État final | Commentaire |
|----------------|--------------|------------|-------------|
| `/remember` (console + web) | ✅ opérationnel | ✅ opérationnel | propriétaire désormais enregistré |
| `/memory` (console + web) | ✅ opérationnel | ✅ opérationnel **isolé par utilisateur** (web) | la console locale reste globale |
| `/forget` (console + web) | ✅ opérationnel | ✅ opérationnel **isolé par utilisateur** (web) | un souvenir d'un autre n'est pas supprimable |
| Persistance après redémarrage | ✅ (non testée) | ✅ **testée** | `test_les_souvenirs_survivent_a_un_redemarrage` |
| Suppression définitive | ✅ (non testée) | ✅ **testée** | `test_un_souvenir_supprime_ne_reapparait_pas` |
| Base absente / vide / endommagée | dégradé (non testé) | ✅ **testé** | 4 tests dédiés |
| Isolation entre utilisateurs | ❌ **absente** (D-MEM-01) | ✅ **corrigée** | 4 tests de régression |
| Lien souvenirs ↔ historique / identité | ❌ inexistant | ❌ **toujours inexistant** | sujet ouvert, hors périmètre |
| Chiffrement de la base | ❌ inexistant | ❌ **toujours inexistant** | décision d'architecture à prendre |

---

## 9. Recommandation pour Agent B

1. **Auditer** la branche `fix/miles-memory-persistent` : modèle de propriété
   (partagé vs personnel), migration de la colonne `owner_user_id`,
   filtrage des trois opérations.
2. **Trancher** les deux sujets ouverts : (a) le lien souvenirs ↔
   historique de conversation, qui **n'existe toujours pas** ; (b) le
   chiffrement de la base, qui **n'existe toujours pas**. Les deux sont des
   décisions d'architecture : je ne les ai pas imposées.
3. **Valider Debian 13** (la VM d'audit n'était pas joignable depuis ce
   poste).
4. Ne pas fusionner sans décision explicite ; ordre de fusion inchangé
   (D1 → D2 → D1-bis → D3 → A-α/B-α → D-B05 → D-B05-restants →
   D-MEM-01).

---

## 10. État Git

| Élément | Valeur |
|---------|--------|
| Branche | `fix/miles-memory-persistent` |
| SHA de base | `54bd138` (`fix/miles-results-persistence`) |
| `main` / intégration | `b9b7e7d` / `69bf670` — **inchangées** |
| D1 / D2 / D1-bis / D3 / A-α·B-α / D-B05 / D-B05-restants | **inchangées** |
| Artefact non committé du checkout principal | `tatus --short--branch` — **préservé** |

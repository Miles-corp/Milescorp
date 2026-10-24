# E4_WEB_STARTUP_CHECK_AGENT_A.md — Démarrage et arrêt réels de l'interface web

> **ANALYSE ET TESTS D'AGENT A — SANS AUDIT INDÉPENDANT** (Agent B indisponible).

- **Date** : 2026-10-24 — **Branche** : `integration/miles-post-d1`
- **Exécuté** : sur ce poste Windows, `python miles.py --web --web-port 8412/8413`

## 1. Résultats du test de démarrage (commandes réelles)

| Contrôle | Commande / observation | Résultat |
|---|---|---|
| Démarrage | `python -u miles.py --web --web-port 8413` | processus vivant |
| Page d'accueil | `GET http://127.0.0.1:8413/` | **200 OK, 10 345 octets** |
| Écoute réseau | `Get-NetTCPConnection -LocalPort 8412` | **127.0.0.1 uniquement** |
| Jeton d'accès | sortie standard (non bufferisée) | « Jeton d'accès ... affiché une seule fois » (jeton **éphémère non consigné**) |
| Bandeau de démarrage | sortie standard | « Interface web MILES sur http://127.0.0.1:8413 » |
| Arrêt (kill) | `Stop-Process` | processus arrêté proprement, aucun zombie |

**Conclusion E4** : l'interface web démarre réellement depuis `miles.py`, sert la page
d'accueil, affiche le jeton, écoute **strictement sur 127.0.0.1** (`LOCAL_ONLY_HOST`
+ `assert_local_host` refusant toute autre adresse) et s'arrête correctement.

## 2. Correctif P3 S-E3-02 apporté dans la foulée : POST /logout

- Route `POST /logout` ajoutée (derrière `_require_session` + CSRF, comme les autres
  routes modifiantes) : révocation **immédiate et définitive** de la session courante.
- Avant : seule l'expiration par inactivité (15 min) fermait une session.
- Tests : `tests/test_logout.py` (3 tests : révocation → 401 ensuite, refus sans
  session, usage avec 2 sessions) — **11/11 OK** sur logout+log ; **suite complète
  741 tests OK (4 ignorés)**.

## 3. Limites

- **SANS AUDIT INDÉPENDANT** : vérifications exécutées par Agent A.
- Non exécuté ici : test depuis un autre hôte que 127.0.0.1 (refus attendu ; le
  bind address suffit à l'isoler) ; Debian 13 (MI-006, toujours bloqué).
- Le jeton de test affiché par le démarrage est **éphémère** : non journalisé,
  non recopié dans les documents.

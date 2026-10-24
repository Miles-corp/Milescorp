# docs/coordination/MISSIONS_REGISTRY.md — Registre global des missions actives

Source de vérité pour l'état des missions. Les détails vivent dans
`docs/coordination/continuations/MI-###.md` (une fiche autonome par mission),
les preuves dans `docs/reports/` et `docs/coordination/STATUS.md`/`HANDOFF.md`.

## Règles

- Une ligne par mission active ; passage en archive (table du bas) après clôture,
  jamais de suppression de ligne.
- Chaque changement de statut met à jour cette table ET la continuation.
- Une mission AWAITING_AUDIT reste non approuvée tant que l'audit B manque.

## Missions actives

| ID | Résumé | Statut | Prio | Responsable | Prochaine action | Continuation |
|----|--------|--------|------|-------------|------------------|--------------|
| MI-001 | Audit indépendant de la correction D1 (`6b736d7`) | TODO (EN ATTENTE, M-006/M-007) | Haute | Agent B | Conclure l'audit TASK-DEV-019 | `continuations/MI-001.md` |
| MI-002 | Intégration ordonnée de la chaîne post-D1 (TASK-DEV-023) | TODO (bloquée par MI-001) | Haute | Agent A | Prévisualiser les conflits (branche jetable) | `continuations/MI-002.md` |
| MI-003 | Publier + faire auditer la branche diagnostics `78ac05c` | IMPLEMENTED (code + tests OK) | Moyenne | Agent A | Push de `fix/miles-diagnostics` après accord utilisateur | `continuations/MI-003.md` |
| MI-004 | Trancher le sort de `fix/miles-paths-posix-spaces` (branche sans commit) | BLOCKED (décision humaine) | Basse | Utilisateur + Agent A | Décider : conservation ou suppression explicite | `continuations/MI-004.md` |
| MI-005 | Corriger l'octet NULL du blob D3 `0be08cd` (sans réécriture d'historique) | TODO (correction contrôlée distincte) | Basse | Agent A | Correction lors de l'intégration (MI-002) | `continuations/MI-005.md` |
| MI-006 | Validation complète sur Debian 13 lorsque disponible | BLOCKED (environnement indisponible) | Haute | Agent B | Exécuter la suite `python -m unittest discover -s tests` dès qu'un environnement existe | `continuations/MI-006.md` |

## Archives

| ID | Daté de clôture | H-### | Branche / SHA | Rapport |
|----|-----------------|-------|---------------|---------|
| (vide — aucune mission clôturée depuis la création du registre) | | | | |

Index détaillé : `archive/INDEX.md`.

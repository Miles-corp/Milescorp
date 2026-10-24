# Registre individuel — Agent B (second PC, revue indépendante)

Responsabilités : revue indépendante, audits avec preuve documentée, tests et
contrôles documentés, détection des oublis et ambiguïtés. Détails :
`AGENT_START.md` et `../MISSIONS_REGISTRY.md`.

## Missions dont Agent B est responsable

| ID | Résumé | Statut | Prochaine action |
|----|--------|--------|------------------|
| MI-001 | Audit indépendant D1 `6b736d7` (TASK-DEV-019) | TODO (EN ATTENTE) | Auditer : lien grant/session, non-réutilisabilité, scénario web, 70 tests d'audit, Debian 13 |
| MI-006 | Validation sur Debian 13 (toute la chaîne) | BLOCKED (environnement indisponible) | Exécuter la suite complète et consigner les résultats réels |

## Attendu ensuite de Agent B (après MI-001)

| ID | Objet |
|----|-------|
| MI-002/audits | Audits priorisés : `1ef4878` (D1-bis) et `8b9ab15` (P1-6-06) avant intégration ; revue des chaînes owner/results/read_only/diagnostics |

## Rappel de règles

- Ne jamais considérer un audit comme effectué sans rapport et preuve vérifiables.
- Les tests ignorés sur Windows le sont pour des limites de plateforme ; ils font
  partie de la validation Debian 13 (MI-006).

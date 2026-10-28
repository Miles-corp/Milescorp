# Registre des missions — état au 2026-10-28

Source de vérité pour les missions **actives** sur `main`. Les détails vivent
dans `docs/reports/`, `docs/specs/` et les messages `M-###`.

> **Note** : un registre plus ancien existe sur la branche
> `fix/miles-d1-web-authorization` (MI-001 → MI-022, arrêté au 26/10). Il est
> conservé dans l'historique Git mais **n'est plus maintenu** : depuis, la
> mémoire avancée a été intégrée (`DEC-025`), le moteur local tranché
> (`DEC-024`) et le multi-fournisseurs fusionné (`DEC-023`). Ce fichier-ci
> repart de l'état réel.

## Missions actives

| ID | Résumé | Statut | Responsable | Preuve / emplacement |
|----|--------|--------|-------------|----------------------|
| MI-023 | Vérifier l'intégration Miles Companion (détachement, valeurs inventées, surface HTTP) | **DONE** — 2 écarts trouvés et corrigés | Agent A bis | `docs/reports/COMPANION_INTEGRATION_VERIFICATION_AGENT_ABIS.md` |
| MI-024 | Spécifier comptes, onglet IA et jumelage box ↔ site (V1 locale, V2 passerelle) | **SPEC LIVRÉE** — en attente de validation utilisateur | Agent A bis | `docs/specs/SITE_PAIRING_IA_SPEC.md` |
| MI-025 | Implémenter le jumelage local V1 (code affiché, sans serveur) | **TODO** — bloquée par la validation de `MI-024` | Agent A bis | à créer après validation |
| MI-009 | Refonte UI web par IA de conception | TODO (prompt livré sur l'ancienne branche) | Utilisateur | `docs/web_design/PROMPT_DE_LANCEMENT_WEB.md` (branche D1) |

## Missions closes récemment

| ID | Résumé | Clôture | Preuve |
|----|--------|---------|--------|
| MI-022 | Mémoire avancée v3 | 2026-10-28 | `DEC-025`, 17 tests, suite 995 OK |
| MI-010 | Moteur local (RTX 3050) | 2026-10-28 | `DEC-024` — Ollama retenu |
| MI-006 | Validation Debian 13 (ancienne base `d60ce99`) | 2026-10-25 | audit B, 773 tests — **ne couvre pas `main` actuel** |
| MI-004 | Branche `fix/miles-paths-posix-spaces` | 2026-10-28 | supprimée avec les branches `gone` |

## Règles

- Une ligne par mission active ; clôture par déplacement vers « closes », jamais
  de suppression.
- Une mission `TODO` bloquée indique **bloquée par quoi**.
- Toute mission touchant au réseau ou à la position exige une décision
  explicite de l'utilisateur avant implémentation.

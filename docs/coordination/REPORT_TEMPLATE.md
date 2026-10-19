# docs/coordination/REPORT_TEMPLATE.md — Modèle de compte rendu MILES

Utiliser ce modèle après chaque livrable ou à la fin d'une session de travail. Copier ce fichier et l'adapter (ex. `docs/coordination/rapports/RAPPORT-TASK-001.md`).

---

## Compte rendu — MILES

| Champ | Valeur |
|-------|--------|
| **Auteur** | Agent A / Agent B |
| **Date** | AAAA-MM-JJ |
| **Tâche(s) concernée(s)** | TASK-### (ex. TASK-001) |
| **PC / clone** | Nom du PC |
| **Branche** | main |

## 1. Résumé

Courte description de ce qui a été fait.

## 2. Fichiers créés

- `chemin/vers/fichier.md` — description

## 3. Fichiers modifiés

- `chemin/vers/fichier.md` — description du changement

## 4. Fichiers non modifiés (intentionnellement)

- `chemin/vers/fichier.md` — raison

## 5. Contrôles exécutés

| Contrôle | Commande | Résultat | Vérifié le |
|----------|----------|----------|------------|
| État Git | `git status` | working tree propre / modifications : ... | AAAA-MM-JJ |
| Lecture diff | `git diff` | OK / anomalies : ... | AAAA-MM-JJ |

> Règle : ne jamais prétendre qu'un test a réussi s'il n'a pas réellement été exécuté.

## 6. Décisions prises

- Décision ... (à consigner également dans `docs/coordination/DECISIONS.md` si structurante)

## 7. Questions pour l'autre agent

- ...

## 8. Blocages / erreurs / limites

- ...

## 9. Éléments restant à faire

- ...

## 10. Prochain objectif

- ...

## 11. Faits vérifiés vs non vérifiés

| Élément | Statut | Preuve |
|---------|--------|--------|
| ... | Vérifié / Non vérifié | ... |

---

Signature de l'agent : ____________________   Date : __________

# MILES — Messages asynchrones (MESSAGES.md)

Canal persistant entre l'agent A et l'agent B. Les messages s'ajoutent en queue de fichier, jamais d'effacement d'historique.

## Règles

- Identifiant : M-001, M-002, …
- Statut : [EN ATTENTE] · [LU] · [RÉPONDU]
- Avant de commencer une tâche, consulter les messages non résolus ([EN ATTENTE]).
- Une réponse est un nouveau message qui référence le précédent.

| ID | Auteur → Destinataire | Date | Statut | Objet / Référence tâche |
|----|-----------------------|------|--------|-------------------------|
| M-001 | Agent B → Agent A | 2026-10-19 | [EN ATTENTE] | Défaut L-005 : CLI ignore l'argument `conversation` (cli.py:40 `conversation or Conversation(...)`) — voir TASK-DEV-004 |

## Historique (ajout en queue uniquement)

(Vide — aucun message pour l'instant.)

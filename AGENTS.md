# MILES â€” Instructions agents (AGENTS.md)

Ce fichier donne les rÃ¨gles communes aux deux agents OpenCode (A sur PC 1, B sur PC 2) qui partagent le dÃ©pÃ´t GitHub de MILES.

## RÃ´les
- Agent A : PC 1
- Agent B : PC 2 (conseiller technique, architecte, rÃ©dige les prompts OpenCode)

## Fichiers de coordination (docs/coordination/)
- TASKS.md : tableau des tÃ¢ches (qui fait quoi, Ã©tat)
- STATUS.md : Ã©tat instantanÃ© de chaque agent
- DECISIONS.md : journal append-only des dÃ©cisions d'architecture validÃ©es
- MESSAGES.md : canal persistant de communication asynchrone
- HANDOFF.md : compte rendu officiel de transfert de tÃ¢che

## RÃ¨gles anti-conflits
1. Avant toute modification : inspecter l'Ã©tat Git et les documents de coordination.
2. Un agent ne modifie qu'une tÃ¢che qu'il a lui-mÃªme passÃ©e en [DOING].
3. Pas de modification concurrente d'un mÃªme fichier par les deux agents.
4. En cas de doute sur l'Ã©tat de l'autre agent : consulter GitHub ou demander Ã  l'utilisateur.
5. Jamais de `git push --force`, `git reset --hard` ni checkout des fichiers de l'autre.

## Convention de statut des tÃ¢ches
[TODO] Â· [DOING] Â· [BLOCKED] Â· [DONE] Â· [CANCELLE]

## Identification des identificateurs
- Identifiant de message : M-001, M-002, â€¦
- Identifiant de tÃ¢che : T-001, T-002, â€¦
- Identifiant de dÃ©cision : D-001, D-002, â€¦
- Identifiant de handoff : H-001, H-002, â€¦

## Flux de communication
1. Une question ou une information Ã  transmettre â†’ MESSAGES.md.
2. Une tÃ¢che terminÃ©e ou un transfert de responsabilitÃ© â†’ HANDOFF.md.
3. Une dÃ©cision dÃ©finitive d'architecture â†’ DECISIONS.md, avec une rÃ©fÃ©rence dans le message concernÃ©.

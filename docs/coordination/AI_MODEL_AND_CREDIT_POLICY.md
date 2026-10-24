# docs/coordination/AI_MODEL_AND_CREDIT_POLICY.md — Charte IA, crédits et coordination

- **Version** : 1.0 (2026-10-24, Agent A)
- **Portée** : toutes les missions MILES exécutées dans OpenCode, sur ce poste.
- **Autorité** : l'utilisateur seul autorise les coûts, les pushes et les fusions définitives.

## 1. Niveaux de tâches et modèle minimal adéquat

| Niveau | Tâches typiques | Modèle minimal adéquat | Règle |
|---|---|---|---|
| 1 — Simple | lectures, inventaires, rédaction petite, corrections stylistiques, vérifications déterministes | modèle gratuit rapide (ex. GLM-5.3-Flash Free constaté disponible) | jamais de modèle payant |
| 2 — Technique ciblé | bug reproductible, tests, petite fonctionnalité, MAJ cohérente de quelques fichiers | modèle de programmation économique capable de parcourir le dépôt | escalade uniquement sur échec analysé |
| 3 — Complexe | intégration de branches divergentes, orchestration multi-composants, régression difficile, persistance | modèle de programmation robuste | uniquement si niveau 2 échoue après analyse ou que le risque le justifie |
| 4 — Critique | authentification, sessions, autorisations, écriture, changement architectural | modèle de raisonnement robuste + audit indépendant possible | tout audit « indépendant » devient invalide s'il est réalisé par l'auteur du code |

L'évaluation (difficulté, conséquence, raisonnement, contexte, outils, coût réel, repli) est
faite avant chaque mission via le format G (section 6).

## 2. Registre des modèles

Sources disponibles : uniquement ce que cette session constate. Ce tableau n'est pas une
garantie de prix/quotas — il reflète l'observation côté utilisateur, jamais extrapolée.

| Modèle | Fournisseur | Disponibilité | Coût | Quotas | Capacités observables | Tâches | Recente vérification | Repli |
|---|---|---|---|---|---|---|---|---|
| GLM-5.3-Flash | Z.ai (via opencode) | **OUI** (utilisé cette session) | gratuit constaté côté utilisateur | NON VÉRIFIÉ (aucune donnée fiable) | lecture dossiers, rédaction docs, diagnostics ciblés, corrections ciblées translatées et testées | niveaux 1, 2 (cumulatif de contexte faible) | 24/10/2026 | escalade niveau 3, à vérifier |
| GLM-5.3 (ou certificat modèle robuste pour niveau 3/4) | Z.ai (?) | **NON VÉRIFIÉ** | NON VÉRIFIÉ | NON VÉRIFIÉ | — | — | — | — |
| DeepSeek | DeepSeek | **EPUISÉ** — `Upstream request failed: Insufficient account funds` constaté côté utilisateur | payant | — | — | — | — | — |
| Catalogue exact OpenCode Go | — | **NON CONSULTABLE** dans cette session | | | | | | |

Interdictions : ne pas transformer une estimation utilisateur en garantie ; ne pas relancer
DeepSeek sans cause vérifiée (fonds/autorisation).

## 3. Règles de maîtrise des crédits

1. Privilégier les modèles gratuits réellement disponibles (registre ci-dessus).
2. Ne pas activer Extra Usage ; ne pas ajouter de fonds ; aucun appel payant sans autorisation explicite de l'utilisateur.
3. Ne pas répéter une requête échouée deux fois avec la même erreur : diagnostiquer d'abord.
4. Limiter chaque sujet à 3 tentatives, puis pauser le blocage documenté.
5. Ne pas envoyer tout le contexte du dépôt si quelques fichiers suffisent (lecture ciblée, grep).
6. Préférer les tests ciblés aux suites coûteuses ; suite complète uniquement avant commit.
7. Modèle plus puissant seulement si le gain attendu justifie le coût — justification à produire.
8. Avant tout changement de modèle : raison, modèle proposé, bénéfice attendu.
9. Si aucun modèle gratuit ne suffit de façon fiable : ARRÊT et demande d'autorisation.

## 4. Règles de changement de modèle (déclencheurs obligatoires)

Avertir l'utilisateur si :
- échec de compréhension/correction après 2 tentatives pertinentes ;
- contexte nécessaire dépassant la capacité du modèle ;
- résultats contradictoires ou trop peu fiables ;
- modification touchant l'authentification, les autorisations ou les opérations sensibles ;
- intégration de branches nécessitant une analyse plus robuste ;
- besoin d'un audit réellement indépendant.

Dans chaque cas, fournir : tâche bloquée ; raison précise ; modèle recommandé ; statut de
disponibilité (connu/non vérifié) ; mode Plan ou Agent ; travail pouvant continuer sans attendre ;
autorisation requise. L'utilisateur se sert de ce rapport pour décider ; l'agent ne change pas
de moteur tout seul si OpenCode impose une sélection manuelle.

## 5. Coordination des agents

| Rôle | Responsabilité |
|---|---|
| Agent coordinateur | inventaire, planification, suivi des tâches, gestion des crédits |
| Agent d'implémentation | corrections et fonctionnalités dans un périmètre approuvé |
| Agent d'audit | vérification indépendante, sans modifier le code audité ; jamais auto-validé |
| Agent spécialiste | tâche ciblée nécessitant une capacité particulière |

Si un seul agent est disponible : il poursuit les corrections mais signale explicitement tout
point resté sans audit indépendant. Interdictions : push, fusion définitive, suppression de
worktrees/modifications préexistantes, dépense non autorisée, contrôle personnel présenté
comme validation indépendante.

## 6. Format obligatoire de recommandation d'IA (avant chaque mission importante)

```
Mission : ..................  Niveau : 1|2|3|4
Modèle recommandé : .......  Alternative gratuite : .......
Mode : Plan|Agent
Pourquoi ce choix est le moins coûteux adéquat : .......
Risque principal : .......  Quand changer de modèle : .......
Autorisation nécessaire : .......
```
Si l'utilisateur impose un autre modèle, le registre est mis à jour (observation constatée).

## 7. Application immédiate

- Étapes en cours (voir `MISSIONS_REGISTRY.md`) : MI-001 (audit D1 — analyse interne étiquetée
  en attendant un audit B), MI-002.1 (previs des conflits — déjà réalisée, worktree `miles-preview`).
- Toute étape de niveau 3/4 (auth/session, intégration officielle, écritures) attend le niveau
  adéquat + audit indépendant quand possible, sous notification et sans coût engagement.

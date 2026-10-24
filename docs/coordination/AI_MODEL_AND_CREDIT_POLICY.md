# docs/coordination/AI_MODEL_AND_CREDIT_POLICY.md — Charte IA, crédits et coordination

- **Version** : 2.0 (2026-10-24, Agent A — registre mis à jour avec le catalogue OpenCode Go fourni par l'utilisateur)
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

## 2. Registre des modèles (catalogue OpenCode Go fourni par l'utilisateur, 2026-10-24)

**Source** : tableau des limites Go estimées/mois transmis par l'utilisateur. Les limites sont
des **estimations utilisateur, non vérifiées par l'agent** ; ne jamais les présenter comme
garanties. **DeepSeek exclu du catalogue** (décision utilisateur : échec de fonds antérieur
sur l'API directe, pas de confiance sans test réel).

### Mapping niveaux → modèles (avec 4 replis par niveau, décision utilisateur)

| Niveau | Modèle recommandé (ordre) | Limite estimée | Replis si échec (même ordre) |
|---|---|---|---|
| 1 — Simple | MiMo-V2.6-Flash → DeepSeek V4 Flash → GLM-5.3-Flash → Qwen3.8 Flash | ~150 400 / ~65 000 / ~31 580 / ~27 000 | tous très généreux en quota |
| 2 — Technique ciblé | MiMo-V2.6-Flash → GLM-5.3-Flash → Qwen3.8 Flash → Kimi K2.7 Code | ~150 400 / ~31 580 / ~27 000 / ~6 750 | passer niveau 3 si échec 2× |
| 3 — Complexe | MiMo-V2.6-Pro → DeepSeek V4 Pro → GLM-5.3 → Kimi K2.7 Code | ~16 300 / ~5 200 / ~1 080 / ~6 750 | remonter à GPT 6 Luna (~21 130) |
| 4 — Critique | MiMo-V2.6-Pro → DeepSeek V4 Pro → GPT 6 Luna → Kimi K3 | ~16 300 / ~5 200 / ~21 130 / ~490 | **toujours + audit indépendant requis** |

Modèle actuellement actif dans cette session : **GLM-5.3-Flash** (niveaux 1-2).

### Catalogue complet (limites estimées/mois, source utilisateur — non vérifiées)

| Rang | Modèle | Limite (Go/mois) | Usage retenu MILES |
|---|---|---:|---|
| 1 | DeepSeek V4 Pro | ~5 200 | **exclu** (décision utilisateur) |
| 2 | MiMo-V2.6-Pro | ~16 300 | niveaux 3-4 |
| 3 | Kimi K3 | ~490 | niveau 4, dernier repli (limite très faible) |
| 4 | GPT 6 Luna | ~21 130 | niveau 3-4 repli |
| 5 | Qwen3.8 Max | ~810 | raisonner, limite faible |
| 6 | GLM-5.3 | ~1 080 | niveau 3, gros dépôts |
| 7 | Kimi K2.7 Code | ~6 750 | code spécialisé |
| 8 | MiniMax M3 | ~16 000 | réserve |
| 9 | GLM-5.2 | ~4 300 | réserve |
| 10 | Qwen3.7 Plus | ~21 600 | réserve |
| 11 | MiMo-V2.6-Flash | ~150 400 | niveaux 1-2, modèle courant |
| 12 | DeepSeek V4 Flash | ~65 000 | niveau 1 |
| 13 | DeepSeek V4.1 Flash | ~130 000 | tâches simples |
| 14 | GLM-5.3-Flash | ~31 580 | **actif**, niveaux 1-2 |
| 15 | Qwen3.8 Flash | ~27 000 | niveau 1 |
| 16 | MiMo-V2.5-Pro | ~16 300 | réserve (génération précédente) |
| 17 | MiMo-V2.5 | ~150 400 | réserve |
| 18 | MiniMax M2.7 | ~17 000 | réserve |
| 19 | LongCat-2.0 | ~57 200 | réserve |
| 20 | Hy3 | ~21 500 | réserve |
| 21-22 | Muse Spark 1.3/1.2 | ~226 600 | tâches légères |
| 23 | GPT 5.6 Luna | ~10 250 | derrière GPT 6 |
| 24-25 | Grok 4.7/4.6 | ~845 | limite très faible, éviter |
| 26 | DeepSeek V4 Flash Vision | ~32 500 | vision si besoin |
| 27 | Hy4 | ~6 770 | preview, éviter comme principal |
| 28 | Space Bunny | ~15 630 | non recommandé principal |
| 29 | LongCat 2.5 Preview Free | Illimité* | temporaire |
| 30 | Beam Free | Illimité | ajout manuel utilisateur |

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

- **Priorité du 2026-10-24 (choix utilisateur)** : E3 — audit interne de sécurité
  (sessions, jetons, grants) en premier ; analyse interne étiquetée de D1 (MI-001)
  en attendant Agent B ; fonctionnalités /log (S5) et E4 ensuite.
- Chaque audit interne est **clairement étiqueté « ANALYSE INTERNE, SANS AUDIT
  INDÉPENDANT »** dans son rapport ; il ne remplace pas l'audit B.
- Toute étape de niveau 3/4 (auth/session, intégration officielle, écritures) attend
  le niveau adéquat + audit indépendant quand possible, sous notification et sans
  coût engagement.

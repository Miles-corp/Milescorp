# docs/reports/LOCAL_PROVIDER_FEASIBILITY_STUDY.md — E2 : fournisseur local (RTX 3050, 4 Go)

- **Auteur** : Agent A — **SANS AUDIT INDÉPENDANT** (Agent B indisponible à ce jour)
- **Date** : 2026-10-24
- **Matériel déclaré** (STATUS.md, à re-vérifier par `nvidia-smi` à l'exécution) :
  NVIDIA GeForce RTX 3050, 4096 MiB VRAM, pilote 617.42, CUDA 13.4.
- **Décisions à respecter** : pas d'Ollama imposé ; aucun téléchargement lourd sans
  accord ; aucune installation de dépendance en production dans cette étude.

## 1. Contraintes réelles

| Contrainte | Conséquence |
|---|---|
| VRAM 4 Go (partagée avec l'affichage Windows) | Modèles ≤ ~3 Go de poids réel en q4 ; activés à chaud, sinon dégradation |
| Mini-PC Lenovo M75q (box physique, Debian) | Le GPU Windows n'est PAS sur la box : le fournisseur local réel sur Debian sera CPU, sauf ajout GPU ultérieur |
| Aucune dépendance lourde actuelle (stdlib pur) | llama.cpp via sous-processus (précompilé) = seule voie sans npm/conda |

## 2. Options documentées (aucune imposée)

| Option | Avantages | Limites | Verdict traduit |
|---|---|---|---|
| **llama.cpp** (binaire + GGUF) | Sous-processus, OpenAI-compatible via llama-server ; pas de dépendance Python | Téléchargement du binaire + du modèle ( accord requis) | Recommandé pour la box Debian (CPU) et Windows GPU |
| Ollama | Confort (serveur local OpenAI-compatible) | Installation lourde, gestion de modèles opaque, en conflit avec « pas de dépendance imprévue » | Possible mais non décidé |
| llama-cpp-python | Intégration Python directe | Compilation native casseuse sous Windows ; dépendance de fabrication | Non recommandé |

## 3. Modèles compatibles 4 Go VRAM (exemples connus publiquement, à vérifier)

Qwen2.5-3B-Instruct Q4_K_M (~2,0 Go) ; Llama-3.2-3B-Instruct Q4_K_M (~2,0 Go) ;
Phi-3.5-mini Q4_K_M (~2,2 Go). Marge laissée au KV-cache. Raisonner sobrement.

## 4. Conclusion documentée et testable

1. La faisabilité est **positive mais plafonnée** : les modèles utiles en 2026 sur ce
   matériel sont les ~1-3 B Q4 ; attendez-vous à un raisonnement plus faible qu'en
   distant — conformité partielle au cahier « intelligences hybrides ».
2. Proposition d'intégration (étape suivante, sous autorisation) :
   `LocalProvider` existe déjà (`app/ai_providers/local.py`, base_url + clé) ;
   le branchement réel se limite à lancer un serveur compatible OpenAI
   (llama.cpp) et à configurer `MILES_LOCAL_BASE_URL`. **Aucun code à écrire
   dans cette étape** ; un test de connectivité locale suffit.
3. Test de reproduction vérifiable :
   `python -m unittest tests.test_provider_selection -v` (sélection explicite) ;
   test réel à faire quand le serveur local sera installé (accord utilisateur).

## 5. Limites

- Aucun test réel GPU exécuté dans cette étude (nividia-smi à rejouer).
- Les tailles de modèles citées sont des ordres de grandeur publics, NON VÉRIFIÉ
  sur ce poste.
- La décision Ollama vs llama.cpp reste à l'utilisateur (exigée par la charte).

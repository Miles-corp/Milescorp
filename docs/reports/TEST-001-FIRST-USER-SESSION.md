# docs/reports/TEST-001-FIRST-USER-SESSION.md — Rapport TEST-001 : Première session utilisateur (Agent A)

## 1. Environnement et commit testés

| Élément | Valeur |
|---------|--------|
| Dépôt | `https://github.com/Miles-corp/Milescorp.git` |
| Branche | `main` |
| Commit testé | `fe5a017` (MILESTONE-006) + correction L-006 non encore publiée (en cours) |
| PC / clone | Windows (Agent A) |
| Python 3 | **Non installé sur ce poste** — aucun test n'a pu être exécuté |
| Environnement virtuel | Non créé |

## 2. Commandes exécutées

Aucune commande n'a pu être exécutée (absence de Python 3 sur ce poste Windows). Les commandes documentées ci-dessous sont issues de l'inspection statique du code et attendent une exécution réelle.

## 3. Résultats observés

**Aucun résultat d'exécution n'est disponible.** Toutes les affirmations ci-dessous relèvent de l'inspection statique du code, pas de tests menés.

| Fonction | Inspection statique | Test manuel réel | Test automatisé réel |
|----------|--------------------|------------------|----------------------|
| `miles.py --help` | Affiche l'aide, code de sortie 0 (code inspecté) | Non exécuté | Non exécuté |
| `miles.py` démarre | Boucle CLI + gestion Ctrl+C/EOF implémentée | Non exécuté | Non exécuté |
| `/help`, `/status`, `/provider`, `/quit` | Implémentés dans `cli.py` | Non exécutés | Non exécutés |
| `/remember`, `/memory`, `/forget` | Implémentés si `MILES_MEMORY_ENABLED=true` | Non exécutés | Non exécutés |
| Conversation IA | Refus propre si aucun fournisseur | Non exécuté | Non exécuté |
| Mémoire persistante SQLite | `app/memory/persistent.py` implémenté | Non exécuté | Non exécuté |
| Persistance après redémarrage | Fichier `data/memory.db` (SQLite) | Non exécuté | Non exécuté |
| Refus des secrets | Détection motifs `sk-`, `password`, etc. | Non exécuté | Non exécuté |
| Mémoire désactivée | `is_available = False`, messages d'information | Non exécuté | Non exécuté |
| Dégradation gracieuse base corrompue | L-006 corrigé (pas d'exception, `is_available=False`) | Non exécuté | Non exécuté |

## 4. Fonctions disponibles aujourd'hui (par inspection statique)

- Interface terminal avec commandes `/help`, `/status`, `/provider`, `/quit`
- Sélection explicite fournisseur distant/local (`--provider`, `MILES_PROVIDER`)
- Gestion propre de Ctrl+C et EOF
- Mémoire persistante locale SQLite (`/remember`, `/memory`, `/forget`)
- Détection et refus des secrets (clés API, mots de passe, tokens)
- Dégradation gracieuse : fournisseur indisponible, base corrompue, voix absente
- Aucun secret codé en dur

## 5. Problèmes à corriger avant le prochain jalon

| ID | Problème | Gravité | Statut |
|----|----------|---------|--------|
| L-006 | Base SQLite corrompue levait une exception au lieu de dégradation gracieuse | Moyenne | Corrigé (pas encore publié, tests non exécutés) |
| — | Aucun fournisseur IA configuré par défaut (démonstration conversation bloquée) | Faible | Documenté dans QUICKSTART.md |
| — | Validation sur Debian 13 non effectuée | Moyenne | Bloqué (environnement non disponible) |

## 6. Recommandations prioritaires

1. **Exécuter les tests** sur Debian 13 : `python3 -m unittest discover -s tests -v` (56 tests attendus : 38 existants + 18 nouveaux).
2. **Publier la correction L-006** sur GitHub (commit en attente).
3. **Valider la persistance après redémarrage** par un test manuel réel.
4. **Tester avec un fournisseur IA réel** (distant ou local) pour confirmer la conversation.
5. **Créer un fournisseur IA de test** configuré pour la démonstration si aucun endpoint n'est disponible.

## 7. Bilan honnête

- **Ce que l'utilisateur peut essayer maintenant** : démarrage du programme, commandes `/help`, `/status`, `/provider`, `/quit`, création/suppression/consultation de souvenirs (mémoire activée), refus des secrets, dégradation propre si aucun fournisseur.
- **Ce qui fonctionne avec preuve** : rien n'a été prouvé par exécution sur ce poste. Preuves disponibles uniquement par inspection statique du code.
- **Ce qui nécessite encore du développement** : exécution réelle des tests sur Debian 13, configuration d'un fournisseur IA pour tester la conversation, validation de la persistance après redémarrage.

---

*Aucun commit ni push n'a été effectué pour ce rapport. Il sera publié avec le rapport TEST-002 après autorisation.*

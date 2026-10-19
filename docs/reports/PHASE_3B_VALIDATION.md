# docs/reports/PHASE_3B_VALIDATION.md — Rapport de validation fonctionnelle Phase 3B (Agent B)

## 1. État initial

| Élément | Valeur |
|---------|--------|
| Dépôt | `https://github.com/Miles-corp/Milescorp.git` |
| Branche | `main` |
| Commit HEAD local | `c70f9d1 docs: add Phase 2 final report` |
| Commit origin/main | `c70f9d1` (synchronisé) |
| Working tree | Propre avant modifications |
| Python | 3.14.7 (Windows) |
| Environnement Debian 13 | Disponible sur VM (SSH `ssh -p 2222 miles@127.0.0.1`, mdp `miles`) — tests confirmés précédemment : 67/67 OK |

## 2. Tests de régression

| Commande | Résultat |
|----------|----------|
| `python -m unittest discover -s tests -v` | ✅ **95 tests, 95 OK, 0 échec, 0 erreur** (15,8 s) |

Répartition par module :
| Module | Tests | Résultat |
|--------|-------|----------|
| `tests/test_actions.py` | 7 | OK |
| `tests/test_cli_reliability.py` | 5 | OK |
| `tests/test_conversation.py` | 7 | OK |
| `tests/test_env_loading.py` | 5 | OK |
| `tests/test_memory_persistent.py` | 18 | OK |
| `tests/test_milestone_005.py` | 11 | OK |
| `tests/test_provider_selection.py` | 6 | OK |
| `tests/test_providers.py` | 5 | OK |
| `tests/test_settings.py` | 9 | OK |
| `tests/test_voice.py` | 6 | OK |
| `tests/test_web.py` | 11 | OK |

Aucun appel API réel n'a été effectué pendant les tests (tous les fournisseurs IA sont simulés).

## 3. Validation fonctionnelle — Terminal

| Vérification | Résultat | Preuve |
|--------------|----------|--------|
| Démarrage normal (`miles.py --help`) | ✅ | Affiche l'aide, code de sortie 0 |
| Affichage de l'aide (`--help`) | ✅ | Options `--config`, `--provider`, `-h` |
| État du fournisseur non configuré | ✅ | `provider=remote`, `available=False` (via web /status) |
| Erreur compréhensible si fournisseur indisponible | ✅ | `Erreur du fournisseur IA : …` affiché, conversation préservée |

## 4. Validation fonctionnelle — Interface web

| Vérification | Résultat | Preuve |
|--------------|----------|--------|
| Démarrage propre (`MilesWebServer` sur `127.0.0.1`) | ✅ | Serveur HTTP lancé sur port dynamique, arrêt propre (`shutdown` + `server_close`) |
| Accès à `127.0.0.1` uniquement par défaut | ✅ | `MilesWebServer` utilise `host="127.0.0.1"` par défaut |
| Affichage de la page (`GET /`) | ✅ | HTTP 200, corps HTML contient "MILES" |
| Envoi d'un message (`POST /message`) | ✅ | Avec provider : 200 + réponse simulée. Sans provider : 400 + "Aucun fournisseur IA configuré" |
| Affichage du statut (`GET /status`) | ✅ | HTTP 200, JSON `{name, available, provider}` |
| Gestion des erreurs et entrées invalides | ✅ | Message vide → 400 "Message vide ou invalide." |
| Protection des routes mémoire (ajout/modif/suppr) | ✅ | Mémoire désactivée → 400 "Mémoire persistante indisponible ou désactivée." ; ID invalide → 400 "Identifiant invalide." |
| Route inconnue | ✅ | `GET /inconnu` → 404 |

## 5. Validation fonctionnelle — Mémoire persistante

| Vérification | Résultat | Preuve |
|--------------|----------|--------|
| Création d'une mémoire de test non sensible | ✅ | `add_memory("Souvenir de test non sensible", category="test")` → id=1 |
| Lecture de cette mémoire | ✅ | `list_memories()` retourne 1 souvenir avec le bon contenu |
| Vérification après fermeture et réouverture | ✅ | `mem.close()` puis réouverture `PersistentMemory(enabled=True, db_path=…)` → souvenir retrouvé |
| Suppression de la mémoire de test | ✅ | `delete_memory(mem_id)` → True, puis `list_memories()` vide |
| Gestion base absente | ✅ | Répertoire créé automatiquement si absent |
| Gestion base corrompue | ✅ | Fichier non-SQLite → `is_available = False`, pas d'exception (dégradation gracieuse) |

## 6. Sécurité

| Vérification | Résultat |
|--------------|----------|
| Serveur web sur `127.0.0.1` uniquement | ✅ (pas d'exposition réseau local/Internet) |
| Aucun appel shell arbitraire depuis le modèle | ✅ (pas d'implémentation dans le code inspecté) |
| Aucun secret journalisé | ✅ (`log_message` désactivé dans `MilesHandler`, `as_dict` documente qu'il ne faut pas journaliser les clés) |
| Aucun fichier `.env` ni secret dans le dépôt | ✅ |

## 7. Limites

| Limite | Explication |
|--------|-------------|
| Vrai fournisseur IA (endpoint réel + clé API) | Non testé — aucun endpoint configuré, aucun appel API réel effectué |
| Persistance après redémarrage réel de la machine | Non testée sur ce poste Windows — validée par simulation (fermeture + réouverture de `PersistentMemory` sur même fichier DB) |
| Validation spécifique sur Debian 13 | Effectuée précédemment (67/67 OK via SSH sur VM `ssh -p 2222 miles@127.0.0.1`) ; les nouveaux tests ajoutés depuis (`test_env_loading`, `test_web`, `test_provider_selection`) n'ont pas encore été re-exécutés sur Debian 13 |
| Dépendances vocales (`pyttsx3`, `speech_recognition`) | Non installées sur ce poste — `VoiceUnavailableError` levé proprement, mode texte fonctionnel |

## 8. Commandes de reproduction

```bash
# 1. Cloner le dépôt
git clone https://github.com/Miles-corp/Milescorp.git
cd Milescorp

# 2. Créer et activer l'environnement virtuel
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows
# ou
source .venv/bin/activate         # Debian 13

# 3. Exécuter toute la suite de tests (régression)
python -m unittest discover -s tests -v

# 4. Démarrage CLI (aide)
python miles.py --help

# 5. Vérification absence de secrets
# Aucun fichier .env ne doit exister ; les clés API sont dans .env.example (commentées)
```

## 9. Conclusion

**Tous les contrôles de la Phase 3B sont validés.**
- 95 tests de régression : 95/95 OK.
- Terminal : démarrage, aide, état, erreur fournisseur comprise — OK.
- Interface web : démarrage/arrêt propre, `127.0.0.1` uniquement, page, message, statut, erreurs, routes protégées — OK.
- Mémoire persistante : création, lecture, persistance après réouverture, suppression, base corrompue (dégradation gracieuse) — OK.
- Sécurité : aucun secret, serveur local uniquement, pas de logs de secrets — OK.

**Prochaine action recommandée :** committer le rapport et les mises à jour de coordination (autorisation utilisateur requise pour le push, règle DEC-004).

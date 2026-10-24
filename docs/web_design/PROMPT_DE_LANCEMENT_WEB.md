# docs/web_design/PROMPT_DE_LANCEMENT_WEB.md — Brief + prompt de lancement pour l'IA de conception

## Contexte

- Projet : **MILES**, assistant personnel hybride (terminal + web local `http://127.0.0.1`).
- Backend réel : `app/interface/web.py` (http.server stdlib, auth jeton porteur + CSRF).
  Routes existantes : `POST /session`, `POST /message`, `GET /status`, `GET /provider`,
  `GET /memory`, `GET /tools`, `POST /tool`, `POST /mission`, `GET /missions`,
  `GET /mission/<id>`, `POST /mission/<id>/authorize|/answer|/cancel`.
- L'UI actuelle est une coque HTML brute **intégrée dans web.py** ; la refonte visuelle
  sera préparée par une IA de conception **en parallèle** du développement fonctionnel.
- Contraintes : service strictement local ; sans build (pas de npm/conda) — HTML/CSS/JS
  statique servis par le backend ; tout le dynamique passe par les routes JSON
  existantes ; aucun appel payant, aucun secret affiché.

## PROMPT À COPIER POUR L'IA DE CONCEPTION (web design + accès GitHub)

```
Tu es un designer UI/UX dédié à MILES, assistant personnel local.
Mission : concevoir puis coder en HTML/CSS/JS statique la refonte du panneau web
de MILES (backend Python stdlib http.server déjà fonctionnel).

A. Travail : cloner https://github.com/Miles-corp/Milescorp.git ; créer la branche
   design/web-ui depuis integration/miles-post-d1 ; committer dessus uniquement.
B. Visuel : lancer `python miles.py --web` (jeton d'accès affiché au terminal) ;
   connexion sur http://127.0.0.1:<port> ; l'API exige les en-têtes
   X-MILES-Session et X-MILES-CSRF (déjà gérés par app.js frontal existant).
C. Zones à concevoir (6 onglets) : Connexion / Conversation (chat + historique) /
   Missions (lancement, suivi, autorisation, reprise) / Outils (catalogue,
   exécution, confirmation) / Mémoire (/remember, /memory, /forget) /
   Diagnostic (/status, /provider).
D. Interdits : aucun appel hors 127.0.0.1 ; aucune clé API dans le code ; pas de
   script externe ; pas de bundle. CSS dans un unique style.css, JS dans app.js.
E. Livrable en branche design/web-ui : index.html (généré par le template Python
   de web.py), style.css, app.js ; maquettes (PNG) dans docs/web_design/mockups/.
F. DÉBAT CONCEPTUEL D'ABORD : proposer 2 maquettes contrastées (sombre vs claire ;
   minimal vs riche), argumentées, AVANT d'écrire le code final.
G. Attributs demandés : responsive desktop, contraste AA, interface en français,
   affichage « non testé » pour la disponibilité (comportement /status réel),
   bouton muet, journal d'activité, aucune donnée personnelle affichée.
H. Validation : chaque composant visuel doit préciser la route JSON qu'il
   consomme ; pas de maquette morte.
```

## Travail parallèle d'Agent A (cette session)

- MI-002p2 : finalisation du merge + documentation.
- E4/S2 : branchement de la nouvelle UI dès réception (branche `design/web-ui`),
  revue de diff complète avant tout commit.
- MI-008/S6 : raccourcis de connexion fournisseurs (clé API en un minimum de
  clics, comptes partagés) — conception en cours, niveau 4 (secrets).

**Note d'orchestration : l'IA de conception n'a JAMAIS accès aux secrets ni au
fichier `.env` ; ses livrables sont examinés par diff avant tout commit.**

## Choix de l'IA pour rendre la page réellement fonctionnelle

Décidé dès qu'un design est retenu, via la charte IA (niveau 3 : intégration
multi-composants, contexte web complet) — recommandation livrée dans le rapport
de la mission de cette phase.

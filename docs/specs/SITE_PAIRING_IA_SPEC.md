# Spécification — Comptes, onglet IA et jumelage box ↔ site

- **Version** : 0.1 (proposition, non implémentée)
- **Date** : 2026-10-28
- **Auteur** : Agent A bis (instance site web)
- **Statut** : à valider par l'utilisateur ; aucune ligne de code réseau n'est
  écrite tant que la validation n'est pas donnée.
- **Décisions liées** : `DEC-014` (aucune donnée inventée), `DEC-016` (écoute
  locale par défaut, réseau en opt-in explicite), `DEC-024` (moteur local
  Ollama).

## 1. Principes non négociables

1. **La clé API ne quitte jamais la box.** Le site ne la reçoit pas, ne la
   stocke pas, ne la journalise pas, ne l'affiche pas. La saisie se fait sur la
   page locale de la box.
2. **Le site ne détient aucun secret.** Ni clé fournisseur, ni secret de
   session de la box. Il ne peut que demander une action à une box jumelée.
3. **Fail-closed.** Sans passerelle configurée, la box reste strictement
   locale : aucune découverte, aucune remontée de position, aucun jumelage.
4. **Rien d'inventé.** Un état inconnu s'affiche « inconnu », jamais une valeur
   plausible (`DEC-014`).
5. **Consentement explicite** à chaque étape qui expose la box : jumelage,
   partage de position, activation d'un fournisseur.

## 2. Comptes utilisateur

Le Companion est aujourd'hui sans compte (session navigateur locale). La
création de compte devient obligatoire **avant la première connexion au site**,
pas avant l'usage local de la box.

- **Inscription** : courriel + mot de passe, ou fournisseur OAuth si un jour
  autorisé. Vérification d'adresse avant activation.
- **Stockage** : mot de passe haché avec `scrypt` (`hashlib.scrypt`, stdlib,
  aucune dépendance ajoutée), sel aléatoire par compte, paramètres stockés avec
  le hachage pour permettre la migration.
- **Sessions** : jeton opaque aléatoire (≥ 32 octets), cookie `HttpOnly`,
  `Secure`, `SameSite=Lax`, expiration absolue et inactivité. Révocation
  serveur à la déconnexion.
- **Aucune clé API** dans le compte : le compte identifie une personne, il ne
  porte aucun secret fournisseur.
- **Suppression** : droit à l'effacement du compte et des box jumelées.

## 3. Onglet IA — connexion rapide du fournisseur

Parcours cible, une fois la box jumelée :

1. L'utilisateur ouvre l'onglet **IA** du site et choisit un fournisseur
   (`remote`, `local`, `anthropic`, `gemini`).
2. Le site **déclenche** l'ouverture de la page locale de la box
   (`http://<box>:8080/setup` ou l'écran IA du Companion) et n'y injecte rien.
3. La clé est saisie **sur la box**, écrite dans son `.env` par le mécanisme
   existant (`app/config/provider_config.py` : écriture atomique, validation,
   `statut()` masqué).
4. La box confirme au site, via la passerelle, **uniquement** : fournisseur
   actif, modèle actif, et l'état « configuré / non configuré ». Jamais la clé,
   jamais sa longueur exacte.
5. Le site affiche cet état ; s'il ne l'obtient pas, il affiche « inconnu ».

**Interdit** : un formulaire de clé API sur le site, même masqué, même
temporaire, même en `type=password`.

## 4. Jumelage box ↔ site

### 4.1 Contrainte réseau fondamentale

Une box derrière le NAT d'un domicile **n'est pas joignable depuis
l'extérieur**. Le site ne peut donc pas « contacter » une box : c'est la box qui
maintient une **connexion sortante persistante** vers une passerelle. Toute
conception qui suppose l'inverse est fausse.

### 4.2 V1 — jumelage local, sans aucun serveur (recommandée d'abord)

- La box affiche un **code court** (6 chiffres, durée de vie 2 minutes) sur sa
  page locale ou sur l'écran du boîtier.
- L'utilisateur, sur le site ouvert dans le même réseau local, saisit le code.
- La box vérifie le code (comparaison à temps constant), accepte, et renvoie un
  **jeton de jumelage** propre à cet appareil, révocable depuis la box.
- Aucun compte n'est requis pour la V1 ; aucun paquet ne quitte le réseau local.

Cette version apporte le jumelage réel **sans** hébergement, sans collecte de
position et sans coût. Elle est utilisable dès que le boîtier est livré.

### 4.3 V2 — passerelle et proposition par proximité (cible)

- La box ouvre une connexion sortante persistante (WebSocket/TLS) vers une
  **passerelle** hébergée. Elle s'authentifie avec un secret propre à la box,
  stocké localement, jamais transmis au site.
- La passerelle ne relaie que des **signaux** : présence, version, état de
  configuration. **Aucun contenu** de conversation, aucun fichier, aucune clé.
- Si l'utilisateur consent au partage de position (approximative), la
  passerelle peut proposer les box **les plus proches** ; le site affiche une
  liste courte, jamais une position exacte.
- Au clic sur « Jumeler », la box émet un **signal matériel** local : clignotement
  de la LED sur l'ESP32-S3 ; sur le HP ProDesk, message ou bip à l'écran. Cela
  empêche de jumeler la box du voisin par erreur.
- L'utilisateur confirme physiquement (appui sur le bouton de la box) avant que
  le jumelage ne soit effectif.

### 4.4 Données de position — minimisation

- Consentement explicite, révocable, distinct du jumelage.
- Position **approximative** uniquement (arrondie à une maille de plusieurs
  centaines de mètres), stockée avec une **durée de rétention** explicite
  (proposition : 30 jours, suppression automatique).
- Aucun historique de déplacement, aucun partage avec un tiers.
- Refus possible sans perte de fonction : la V1 reste utilisable.

## 5. Modèle de données minimal (V2)

| Objet | Champs | Notes |
|---|---|---|
| `account` | id, email, hash_scrypt, sel, créé_le | aucun secret fournisseur |
| `box` | id, nom, secret_passerelle_haché, version, dernière_vue | clé jamais stockée |
| `pairing` | id, account_id, box_id, créé_le, révoqué_le | révocable des deux côtés |
| `presence` | box_id, position_arrondie, vu_le | purge automatique |
| `provider_state` | box_id, fournisseur, modèle, configuré | **jamais** la clé |

## 6. Modèle de menaces (extrait)

| Menace | Réponse |
|---|---|
| Vol de la base du site | aucune clé API dedans (principe 1) |
| Rejeu d'un code de jumelage | code court, usage unique, expiration 2 min |
| Jumelage de la mauvaise box | signal matériel + confirmation physique |
| Box usurpée sur la passerelle | secret propre à la box, TLS, révocation |
| Fuite de position | arrondi, consentement, rétention bornée |
| Site compromis | il ne peut que demander des actions ; la box décide et journalise |

## 7. Critères d'acceptation

**V1**
1. Jumelage réussi sur réseau local avec le code affiché, sans serveur.
2. Code expiré ou erroné → refus explicite, aucune session créée.
3. Jeton révocable depuis la box ; révocation effective à la requête suivante.
4. Aucun paquet hors réseau local (vérifiable par capture).

**V2**
5. Box derrière NAT joignable uniquement via sa connexion sortante.
6. La passerelle ne reçoit aucun contenu de conversation ni clé (vérifié par
   revue de code et capture).
7. Position arrondie, purgée après la rétention annoncée.
8. Sans passerelle, la box reste locale : aucune tentative de connexion.

## 8. Décisions qui appartiennent à l'utilisateur

1. **Hébergement de la passerelle** (fournisseur, région, coût) — rien n'est
   provisionné.
2. **Collecte de position** : accepter, ou rester en V1 indéfiniment.
3. **Comptes** : obligatoires au site, ou facultatifs tant que la V1 suffit.
4. **Ordre** : V1 d'abord (recommandé), V2 ensuite.

## 9. Hors périmètre de cette spec

- Aucune implémentation serveur, aucune migration de base, aucun déploiement.
- Aucune modification de `miles.py`, `app/interface/web.py` ni des outils.
- Aucun choix de fournisseur d'hébergement ou d'authentification tierce.

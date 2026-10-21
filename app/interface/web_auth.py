"""Authentification, contrôle d'origine et jetons CSRF de l'interface web.

Ce module corrige les défauts P1 relevés par le réaudit de la Phase 6 :

- **P1-6-03** : aucune route modifiante ne contrôlait l'origine de la
  requête. Une page tierce ouverte dans le navigateur de l'utilisateur
  pouvait émettre des requêtes « simples » (``Content-Type: text/plain``,
  sans préflight) vers ``http://127.0.0.1:<port>/tool`` et déclencher
  l'exécution d'un outil.
- **P1-6-06** : l'autorisation d'une mission ne demandait aucune identité.
  N'importe quel client HTTP pouvait accorder l'autorisation en envoyant
  ``{"approved": true}``.
- **P1-6-02 (résiduel)** : la session du serveur web était créée au
  démarrage du processus : **tous les clients HTTP partageaient le même
  identifiant**, un jeton de confirmation obtenu par un client restant
  utilisable par un autre.

Modèle d'authentification retenu
--------------------------------

MILES n'a **pas** de comptes utilisateurs avec mot de passe. Le mécanisme
retenu est une authentification **par jeton porteur** (*bearer token*) :

- les identifiants sont **configurés explicitement** (jamais dérivés d'un
  identifiant de session technique) :
  ``MILES_WEB_AUTH_TOKEN`` (un utilisateur « local ») ou
  ``MILES_WEB_USERS_FILE`` (fichier JSON ``{"<utilisateur>": "<jeton>"}``,
  permettant plusieurs utilisateurs distincts) ;
- ``POST /session`` échange un jeton contre une **session par client** :
  identifiant opaque et imprévisible, jeton CSRF distinct, expiration ;
- la session sert ensuite d'**identité** : c'est elle qui est liée aux
  jetons de confirmation des outils et aux autorisations de mission ;
- **si aucun identifiant n'est configuré, l'interface web est fermée** :
  les routes sensibles répondent ``403`` et ne sont plus du tout
  atteignables. C'est le comportement « fermé par défaut ».

Ce mécanisme est une authentification minimale mais **réelle** : la possession
du jeton est nécessaire, le jeton n'est pas devinable, il est révocable et
les sessions expirent. Ce n'est **pas** une authentification multi-utilisateur
complète (pas de mot de passe, pas de rotation) : c'est documenté
explicitement, et c'est suffisant pour un serveur local dont l'exposition
est maîtrisée.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger("miles.web.auth")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

#: Taille des jetons générés (octets). 32 octets = 256 bits d'entropie.
TOKEN_BYTES = 32

#: Durée de vie d'une session web (secondes).
DEFAULT_SESSION_TTL_SECONDS = 1800.0

#: Durée de vie d'une demande d'autorisation de mission (secondes).
DEFAULT_APPROVAL_TTL_SECONDS = 300.0

#: Nombre d'échecs de connexion tolérés par adresse client.
MAX_LOGIN_FAILURES = 5

#: Durée du blocage temporaire après trop d'échecs (secondes).
LOGIN_LOCKOUT_SECONDS = 60.0

#: En-tête transportant l'identifiant de session.
SESSION_HEADER = "X-MILES-Session"

#: En-tête transportant le jeton CSRF.
CSRF_HEADER = "X-MILES-CSRF"

#: Hôtes locaux acceptés pour déduire une origine « même origine ».
LOCAL_HOST_NAMES = ("127.0.0.1", "localhost", "::1", "[::1]")


class WebAuthError(Exception):
    """Erreur d'authentification ou de contrôle d'accès.

    Le message est destiné au client : il ne contient aucun secret.
    """


@dataclass(frozen=True)
class WebUser:
    """Utilisateur web identifié par un jeton porteur.

    Le jeton n'est jamais stocké en clair après le chargement : seule son
    empreinte (SHA-256 avec un sel aléatoire par processus) est conservée.
    """

    user_id: str
    token_digest: str

    @staticmethod
    def _digest(token: str, pepper: bytes) -> str:
        return hashlib.sha256(pepper + token.encode("utf-8")).hexdigest()

    @classmethod
    def from_token(cls, user_id: str, token: str, pepper: bytes) -> "WebUser":
        return cls(user_id=user_id, token_digest=cls._digest(token, pepper))

    def matches(self, token: str, pepper: bytes) -> bool:
        """Comparer le jeton fourni à l'empreinte (comparaison constante)."""
        if not token:
            return False
        return hmac.compare_digest(self.token_digest, self._digest(token, pepper))


class WebCredentialStore:
    """Ensemble des identifiants configurés pour l'interface web.

    Un magasin vide signifie : **aucune authentification n'est configurée**.
    Dans ce cas, l'interface web refuse toutes les routes sensibles.
    """

    def __init__(self, users: Optional[Dict[str, str]] = None) -> None:
        # Sel aléatoire par processus : les empreintes stockées en mémoire
        # ne sont pas exploitables par une table de hachage pré calculée.
        self._pepper = secrets.token_bytes(16)
        self._users: Dict[str, WebUser] = {}
        for user_id, token in (users or {}).items():
            if not user_id or not token:
                continue
            self._users[str(user_id)] = WebUser.from_token(
                str(user_id), str(token), self._pepper
            )

    @property
    def is_configured(self) -> bool:
        """Indiquer si au moins un identifiant est configuré."""
        return bool(self._users)

    @property
    def user_ids(self) -> List[str]:
        """Lister les identifiants utilisateurs (sans jeton)."""
        return sorted(self._users)

    def authenticate(self, token: str) -> Optional[str]:
        """Retourner l'identifiant de l'utilisateur correspondant au jeton."""
        if not token or not self._users:
            return None
        for user in self._users.values():
            if user.matches(token, self._pepper):
                return user.user_id
        return None

    @classmethod
    def from_settings(cls, settings: Any) -> "WebCredentialStore":
        """Construire le magasin depuis la configuration de l'application.

        - ``web_auth_token`` : un utilisateur « local » ;
        - ``web_users_file`` : fichier JSON ``{"utilisateur": "jeton"}``.
        """
        users: Dict[str, str] = {}

        token = str(settings.get("web_auth_token", "") or "").strip()
        if token:
            users["local"] = token

        users_file = str(settings.get("web_users_file", "") or "").strip()
        if users_file:
            users.update(_read_users_file(users_file))

        return cls(users)


def _read_users_file(path: str) -> Dict[str, str]:
    """Lire un fichier JSON d'identifiants web.

    Le chemin est confiné aux racines autorisées (répertoire du projet et
    dossier ``data/``) : un fichier d'identifiants situé ailleurs n'est
    pas lu. Un fichier illisible ou mal formé est ignoré (et signalé dans
    les journaux) : l'interface web reste fermée plutôt que d'être ouverte
    avec des identifiants mal lus.
    """
    from app.security.paths import PathSecurityError, resolve_authorized_path

    try:
        resolved = resolve_authorized_path(path)
    except PathSecurityError:
        logger.error(
            "Fichier d'identifiants web hors des racines autorisees : "
            "aucune authentification ne sera configuree."
        )
        return {}
    try:
        with open(resolved, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError) as exc:
        logger.error(
            "Fichier d'identifiants web illisible : aucune authentification "
            "ne sera configuree (%s).",
            type(exc).__name__,
        )
        return {}
    if not isinstance(payload, dict):
        logger.error(
            "Fichier d'identifiants web invalide : objet JSON attendu."
        )
        return {}
    users: Dict[str, str] = {}
    for user_id, token in payload.items():
        if isinstance(user_id, str) and isinstance(token, str) and token:
            users[user_id] = token
    return users


@dataclass
class WebSession:
    """Session web authentifiée, propre à un client.

    Attributs :
        session_id : identifiant opaque et imprévisible.
        user_id : identifiant de l'utilisateur authentifié.
        csrf_token : jeton CSRF, distinct du jeton de session.
        created_at : instant de création.
        expires_at : instant d'expiration.
        revoked : True si la session a été révoquée.
    """

    session_id: str
    user_id: str
    csrf_token: str
    created_at: float
    expires_at: float
    revoked: bool = False

    def is_expired(self, now: float) -> bool:
        """Indiquer si la session a expiré."""
        return now >= self.expires_at


class WebAuthenticator:
    """Émet et vérifie les sessions web authentifiées.

    Attributs :
        credentials : magasin des identifiants.
        session_ttl_seconds : durée de vie d'une session.
    """

    def __init__(
        self,
        credentials: WebCredentialStore,
        *,
        session_ttl_seconds: float = DEFAULT_SESSION_TTL_SECONDS,
        clock: Any = time.time,
    ) -> None:
        self.credentials = credentials
        self.session_ttl_seconds = float(session_ttl_seconds)
        self._clock = clock
        self._sessions: Dict[str, WebSession] = {}
        self._failures: Dict[str, List[float]] = {}
        self._lock = threading.RLock()

    @property
    def is_configured(self) -> bool:
        """Indiquer si une authentification est disponible."""
        return self.credentials.is_configured

    @classmethod
    def from_settings(
        cls,
        settings: Any,
        *,
        session_ttl_seconds: float = DEFAULT_SESSION_TTL_SECONDS,
    ) -> "WebAuthenticator":
        """Construire un authentificateur depuis la configuration.

        Si aucun identifiant n'est configuré, l'authentificateur est créé
        **sans** utilisateur : l'interface web est alors fermée.
        """
        return cls(
            WebCredentialStore.from_settings(settings),
            session_ttl_seconds=session_ttl_seconds,
        )

    # --- Connexion ---

    def login(self, token: str, client_address: str = "") -> WebSession:
        """Authentifier un client et créer une session.

        Raises:
            WebAuthError: si aucun identifiant n'est configuré, si le client
                est bloqué temporairement ou si le jeton est invalide.
        """
        if not self.is_configured:
            raise WebAuthError(
                "Authentification non configuree : l'interface web est fermee."
            )
        address = client_address or "inconnu"
        self._check_lockout(address)

        user_id = self.credentials.authenticate(token or "")
        if user_id is None:
            self._record_failure(address)
            raise WebAuthError("Identifiants invalides.")

        now = float(self._clock())
        session = WebSession(
            session_id=secrets.token_hex(TOKEN_BYTES),
            user_id=user_id,
            csrf_token=secrets.token_hex(TOKEN_BYTES),
            created_at=now,
            expires_at=now + self.session_ttl_seconds,
        )
        with self._lock:
            self._sessions[session.session_id] = session
            self._failures.pop(address, None)
        logger.info("Session web ouverte pour l'utilisateur %s.", user_id)
        return session

    def authenticate(self, session_id: str) -> Optional[WebSession]:
        """Retourner la session correspondante, ou None si elle est invalide."""
        if not session_id:
            return None
        now = float(self._clock())
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.revoked or session.is_expired(now):
                return None
            return session

    def verify_csrf(self, session: Optional[WebSession], csrf_token: str) -> bool:
        """Vérifier le jeton CSRF présenté par le client.

        La comparaison est constante : elle ne révèle pas le jeton.
        """
        if session is None or not csrf_token:
            return False
        return hmac.compare_digest(session.csrf_token, csrf_token)

    def revoke(self, session_id: str) -> bool:
        """Révoquer une session. Retourner True si elle existait."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            session.revoked = True
            self._sessions.pop(session_id, None)
            return True

    def purge_expired(self) -> int:
        """Supprimer les sessions expirées. Retourner le nombre supprimé."""
        now = float(self._clock())
        with self._lock:
            expired = [
                sid
                for sid, session in self._sessions.items()
                if session.is_expired(now)
            ]
            for sid in expired:
                self._sessions.pop(sid, None)
            return len(expired)

    # --- Protection contre la force brute ---

    def _check_lockout(self, address: str) -> None:
        """Refuser la connexion si trop d'échecs récents."""
        now = float(self._clock())
        with self._lock:
            failures = [
                ts for ts in self._failures.get(address, []) if now - ts < LOGIN_LOCKOUT_SECONDS
            ]
            self._failures[address] = failures
            if len(failures) >= MAX_LOGIN_FAILURES:
                raise WebAuthError(
                    "Trop de tentatives echouees : reessayez plus tard."
                )

    def _record_failure(self, address: str) -> None:
        """Enregistrer un échec de connexion."""
        now = float(self._clock())
        with self._lock:
            self._failures.setdefault(address, []).append(now)


def _origin_of(url: str) -> str:
    """Extraire l'origine (schéma + hôte + port) d'une URL."""
    text = (url or "").strip()
    for separator in ("://",):
        if separator in text:
            scheme, _, rest = text.partition(separator)
            return f"{scheme.lower()}://{rest.split('/', 1)[0].lower()}"
    return text.split("/", 1)[0].lower()


class OriginPolicy:
    """Politique d'origine appliquée aux requêtes web.

    Origines autorisées :
    - la liste explicitement configurée (``MILES_WEB_ALLOWED_ORIGINS``) ;
    - les origines « même origine » déduites de l'en-tête ``Host`` de la
      requête, **à condition que cet hôte soit local** (le serveur n'écoute
      que sur ``127.0.0.1``).

    Comportement :
    - ``Origin`` présent et non autorisé → refus (403) ;
    - ``Origin`` absent et ``Referer`` présent et non autorisé → refus (403) ;
    - ``Origin`` absent et ``Referer`` absent → la requête est acceptée à ce
      stade, mais elle doit alors satisfaire les contrôles de session et de
      jeton CSRF, qu'un site tiers ne peut pas satisfaire.
    """

    def __init__(
        self,
        allowed_origins: Iterable[str] = (),
        *,
        server_port: Optional[int] = None,
    ) -> None:
        self._allowed: set[str] = set()
        for origin in allowed_origins or ():
            cleaned = str(origin).strip().rstrip("/")
            if cleaned:
                self._allowed.add(cleaned.lower())
        if server_port:
            for host in ("127.0.0.1", "localhost"):
                self._allowed.add(f"http://{host}:{server_port}")

    @property
    def allowed_origins(self) -> List[str]:
        """Lister les origines explicitement autorisées."""
        return sorted(self._allowed)

    def add_server_port(self, port: int) -> None:
        """Déclarer le port d'écoute (origines « même origine »)."""
        for host in ("127.0.0.1", "localhost"):
            self._allowed.add(f"http://{host}:{port}")

    def check(
        self,
        origin: Optional[str],
        referer: Optional[str],
        host_header: Optional[str],
    ) -> Tuple[bool, str]:
        """Vérifier l'origine d'une requête.

        Returns:
            Un couple ``(autorisé, motif du refus)``.
        """
        allowed = set(self._allowed)
        for host in _local_hosts(host_header):
            allowed.add(f"http://{host}")

        if origin is not None and origin.strip():
            if _origin_of(origin) in allowed:
                return True, ""
            return False, "Origine non autorisee."

        if referer is not None and referer.strip():
            if _origin_of(referer) in allowed:
                return True, ""
            return False, "Referer non autorise."

        # Ni Origin ni Referer : la protection repose alors sur la session
        # authentifiée et le jeton CSRF, vérifiés par l'appelant.
        return True, ""


def _local_hosts(host_header: Optional[str]) -> List[str]:
    """Déduire les hôtes locaux autorisés à partir de l'en-tête Host.

    L'en-tête ``Host`` est fourni par le client : on n'en déduit une
    origine « même origine » que si l'hôte est **local**, ce qui est
    toujours le cas puisque le serveur n'écoute que sur ``127.0.0.1``.
    """
    if not host_header:
        return []
    host = host_header.strip().lower()
    if host.startswith("["):  # IPv6 littéral
        closing = host.find("]")
        if closing == -1:
            return []
        hostname = host[: closing + 1]
    else:
        hostname = host.split(":", 1)[0]
    if hostname in LOCAL_HOST_NAMES:
        return [host]
    return []


def generate_access_token() -> str:
    """Générer un jeton d'accès initial pour l'interface web.

    Le jeton est affiché une seule fois à l'utilisateur : il doit ensuite
    être saisi dans l'interface (ou fourni par ``MILES_WEB_AUTH_TOKEN``).
    """
    return secrets.token_hex(TOKEN_BYTES)

"""Autorisations (« grants ») liées à une session et à une mission.

Ce module corrige le défaut signalé par le rapport de la Phase 5 : le jeton
de confirmation du moteur n'était lié ni à l'utilisateur ni à un contexte.
Un jeton obtenu dans un contexte pouvait être rejoué dans un autre.

Le mécanisme présenté ici est un **passeport d'autorisation** :

- il est émis par l'application (jamais par le modèle) ;
- il est lié à une **session** (identité d'exécution / console) et à une
  **mission** (contexte de travail) ;
- il porte une liste explicite d'outils autorisés et, éventuellement, des
  racines de chemin autorisées ;
- il **expire** et son nombre d'utilisations est borné ;
- il ne peut pas être rejoué : chaque usage est décompté.

Le modèle ne fournit jamais un grant : le grant est un paramètre interne
du moteur, injecté par l'application. Une valeur produite par un modèle ou
par un résultat d'outil ne peut donc pas élargir les autorisations.

Le contrôle effectif reste assuré par :class:`app.tools.engine.ToolEngine`
et :class:`app.tools.policy.ToolPolicy` : un grant ne contourne jamais la
politique de sécurité, il remplace seulement la confirmation **interactive**
d'un outil dont le risque est déjà connu et borné.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Optional, Protocol, Tuple

from app.security.paths import PathSecurityError, canonical_path, is_within

#: Durée de validité par défaut d'un grant (secondes).
DEFAULT_GRANT_TTL_SECONDS = 300.0

#: Nombre maximal d'utilisations d'un grant.
DEFAULT_GRANT_MAX_USES = 32


@dataclass(frozen=True)
class ToolGrant:
    """Autorisation liée à une session, une mission et un ensemble d'outils.

    Attributs :
        grant_id : identifiant unique du grant.
        session_id : identité de session (émise par l'application).
        mission_id : contexte de mission (vide si le grant est global).
        tool_ids : outils explicitement couverts par le grant.
        allowed_roots : racines de chemin autorisées (vide = pas de
            restriction de chemin supplémentaire).
        issued_at : instant d'émission (secondes depuis l'époque).
        expires_at : instant d'expiration (secondes depuis l'époque).
        max_uses : nombre maximal d'utilisations autorisées.
        uses : nombre d'utilisations déjà consommées.
        scope : portée du grant ("lecture_seule" ou "outils_explicites").
        confirmed_by : origine de la confirmation ("humain").
    """

    grant_id: str
    session_id: str
    mission_id: str
    tool_ids: FrozenSet[str]
    allowed_roots: Tuple[str, ...] = ()
    issued_at: float = 0.0
    expires_at: float = 0.0
    max_uses: int = DEFAULT_GRANT_MAX_USES
    uses: int = 0
    scope: str = "outils_explicites"
    confirmed_by: str = "humain"

    def is_expired(self, now: float) -> bool:
        """Indiquer si le grant a expiré."""
        return now >= self.expires_at

    def is_exhausted(self) -> bool:
        """Indiquer si le grant a été consommé au maximum de ses usages."""
        return self.uses >= self.max_uses

    def covers_tool(self, tool_id: str) -> bool:
        """Indiquer si l'outil fait partie du périmètre du grant."""
        return tool_id in self.tool_ids

    def covers_path(self, path: str) -> bool:
        """Indiquer si un chemin est couvert par le périmètre du grant.

        Un grant sans racine autorisée ne restreint pas les chemins : la
        restriction habituelle (``app.security.paths``) s'applique alors
        seule.
        """
        if not self.allowed_roots:
            return True
        try:
            resolved = canonical_path(path)
        except (OSError, ValueError):
            return False
        for root in self.allowed_roots:
            try:
                if is_within(resolved, canonical_path(root)):
                    return True
            except (OSError, ValueError):
                continue
        return False


class GrantChecker(Protocol):
    """Contrat minimal attendu par le moteur d'outils.

    Implémenté par :class:`GrantRegistry`. Le moteur ne connaît que ce
    contrat : aucune dépendance directe vers l'orchestrateur.
    """

    def authorize(
        self,
        tool_id: str,
        parameters: Dict[str, Any],
        context_id: Optional[str],
        actor_id: Optional[str],
    ) -> Optional[str]:
        """Retourner l'identifiant du grant couvrant la demande, ou None."""

    def consume(self, grant_id: str) -> bool:
        """Consommer une utilisation du grant. Retourner False si refusée."""


@dataclass
class _StoredGrant:
    """État mutable d'un grant (les compteurs d'usage sont mis à jour)."""

    grant: ToolGrant
    revoked: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


class GrantRegistry:
    """Registre des autorisations actives, liées à une session et une mission.

    Les grants sont conservés en mémoire : ils sont invalidés à la fin du
    processus, ce qui est le comportement attendu (une autorisation ne
    survit pas au redémarrage de l'application).
    """

    def __init__(
        self,
        *,
        clock: Any = time.time,
        ttl_seconds: float = DEFAULT_GRANT_TTL_SECONDS,
        max_uses: int = DEFAULT_GRANT_MAX_USES,
    ) -> None:
        self._clock = clock
        self._ttl_seconds = ttl_seconds
        self._max_uses = max_uses
        self._grants: Dict[str, _StoredGrant] = {}
        self._lock = threading.RLock()

    # --- Émission ---

    def issue(
        self,
        session_id: str,
        mission_id: str,
        tool_ids,
        *,
        allowed_roots=(),
        ttl_seconds: Optional[float] = None,
        max_uses: Optional[int] = None,
        scope: str = "outils_explicites",
    ) -> ToolGrant:
        """Émettre un grant lié à une session et une mission.

        Args:
            session_id : identité de session émettrice.
            mission_id : contexte de mission.
            tool_ids : outils explicitement couverts.
            allowed_roots : racines de chemin autorisées (optionnel).
            ttl_seconds : durée de validité (défaut : registre).
            max_uses : nombre maximal d'utilisations (défaut : registre).
            scope : portée déclarée du grant.

        Returns:
            Le grant émis.
        """
        now = float(self._clock())
        ttl = self._ttl_seconds if ttl_seconds is None else float(ttl_seconds)
        roots = tuple(
            str(canonical_path(root)) for root in allowed_roots if str(root)
        )
        grant = ToolGrant(
            grant_id=uuid.uuid4().hex,
            session_id=str(session_id),
            mission_id=str(mission_id),
            tool_ids=frozenset(str(t) for t in tool_ids),
            allowed_roots=roots,
            issued_at=now,
            expires_at=now + ttl,
            max_uses=self._max_uses if max_uses is None else int(max_uses),
            uses=0,
            scope=scope,
            confirmed_by="humain",
        )
        with self._lock:
            self._grants[grant.grant_id] = _StoredGrant(grant=grant)
        return grant

    # --- Consultation ---

    def get(self, grant_id: str) -> Optional[ToolGrant]:
        """Retourner un grant actif (non expiré, non révoqué), ou None."""
        with self._lock:
            stored = self._grants.get(grant_id)
            if stored is None or stored.revoked:
                return None
            grant = stored.grant
            if grant.is_expired(float(self._clock())):
                return None
            return grant

    def revoke(self, grant_id: str) -> bool:
        """Révoquer un grant. Retourner True si le grant existait."""
        with self._lock:
            stored = self._grants.get(grant_id)
            if stored is None:
                return False
            stored.revoked = True
            return True

    def revoke_mission(self, mission_id: str) -> int:
        """Révoquer tous les grants d'une mission. Retourner le nombre révoqué."""
        with self._lock:
            count = 0
            for stored in self._grants.values():
                if stored.grant.mission_id == mission_id and not stored.revoked:
                    stored.revoked = True
                    count += 1
            return count

    def list_grants(self) -> list[ToolGrant]:
        """Lister les grants actifs."""
        now = float(self._clock())
        with self._lock:
            return [
                stored.grant
                for stored in self._grants.values()
                if not stored.revoked and not stored.grant.is_expired(now)
            ]

    # --- Contrat GrantChecker ---

    def authorize(
        self,
        tool_id: str,
        parameters: Dict[str, Any],
        context_id: Optional[str],
        actor_id: Optional[str],
    ) -> Optional[str]:
        """Vérifier qu'un grant actif couvre la demande.

        Le grant doit :
        - couvrir l'outil demandé ;
        - être lié à la même session (acteur) que la demande ;
        - être lié à la même mission (contexte) que la demande ;
        - couvrir le chemin ciblé si le grant restreint les chemins ;
        - être valide (non expiré, usages disponibles).

        Returns:
            L'identifiant du grant, ou None si aucun grant ne convient.
        """
        # S-E3-04 / S-E3-04b (audit interne E3 + audit B 2026-10-25) :
        # fail-closed complet — sans identifiant d'acteur ET sans contexte
        # de mission démontrés, aucun grant ne peut être retourné. Le contrat
        # `GrantChecker` accepte `Optional[str]`, mais l'absence de preuve
        # d'appartenance ne doit jamais valoir autorisation.
        if not actor_id:
            return None
        if context_id is None:
            return None
        now = float(self._clock())
        with self._lock:
            for stored in self._grants.values():
                grant = stored.grant
                if stored.revoked:
                    continue
                if grant.is_expired(now) or grant.is_exhausted():
                    continue
                if not grant.covers_tool(tool_id):
                    continue
                if grant.session_id != actor_id:
                    continue
                if grant.mission_id != context_id:
                    continue
                path = parameters.get("path")
                if isinstance(path, str) and path:
                    try:
                        if not grant.covers_path(path):
                            continue
                    except PathSecurityError:
                        continue
                return grant.grant_id
        return None

    def consume(self, grant_id: str) -> bool:
        """Décompter une utilisation du grant.

        Retourne False si le grant est inconnu, expiré, révoqué ou épuisé :
        la consommation est atomique avec la vérification.
        """
        now = float(self._clock())
        with self._lock:
            stored = self._grants.get(grant_id)
            if stored is None or stored.revoked:
                return False
            grant = stored.grant
            if grant.is_expired(now) or grant.is_exhausted():
                return False
            # Le compteur est porté par un objet immuable : on le remplace.
            stored.grant = ToolGrant(
                grant_id=grant.grant_id,
                session_id=grant.session_id,
                mission_id=grant.mission_id,
                tool_ids=grant.tool_ids,
                allowed_roots=grant.allowed_roots,
                issued_at=grant.issued_at,
                expires_at=grant.expires_at,
                max_uses=grant.max_uses,
                uses=grant.uses + 1,
                scope=grant.scope,
                confirmed_by=grant.confirmed_by,
            )
            return True


def default_session_id(prefix: str = "session") -> str:
    """Générer un identifiant de session aléatoire.

    L'identité de session n'est pas une identité humaine : c'est un jeton
    aléatoire créé au démarrage de l'application. Il sert à empêcher qu'une
    autorisation acquise dans un contexte serve dans un autre contexte, et
    il est invalidé à la fermeture du processus.
    """
    return f"{prefix}-{uuid.uuid4().hex}"


def resolve_grant_roots(paths) -> Tuple[str, ...]:
    """Résoudre canoniquement une liste de racines de chemin.

    Les racines qui ne peuvent pas être résolues sont ignorées : une racine
    invalide ne doit jamais élargir le périmètre.
    """
    roots = []
    for path in paths:
        if not path:
            continue
        try:
            roots.append(str(canonical_path(path)))
        except (OSError, ValueError):
            continue
    return tuple(roots)

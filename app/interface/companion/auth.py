"""Comptes, rôles et sessions du site Miles Companion.

Tout est local à la box :

- mot de passe haché avec `scrypt` (stdlib), sel aléatoire par compte ;
- jeton de session opaque, **seul son hachage SHA-256 est stocké** ;
- cookie `HttpOnly` + `SameSite=Strict`, CSRF synchronisé ;
- deux administrateurs au maximum, garanti par une transaction ;
- limitation des tentatives de connexion.

Aucune clé de fournisseur IA ne transite par ce module.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import os
import re
import secrets
import sys
import time
import uuid
from typing import Any, Optional

from app.interface.companion import store as store_module

#: Paramètres scrypt. Choisis pour rester rapides sur un mini-PC tout en
#: coûtant cher à une attaque par dictionnaire locale.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64
SALT_BYTES = 16

#: Un identifiant court, sans espace ni caractère exotique.
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,31}$")

#: Deux administrateurs, pas trois (décision utilisateur du 2026-10-29).
MAX_ADMINS = 2

#: Session : 8 h d'inactivité, 7 jours de vie absolue.
IDLE_TTL_S = 8 * 3600
ABSOLUTE_TTL_S = 7 * 24 * 3600

#: Rafraîchir `last_seen_at` au plus toutes les 60 s (évite une écriture
#: SQLite par requête).
TOUCH_INTERVAL_S = 60.0

#: 5 échecs sur 15 minutes verrouillent le couple compte + adresse.
MAX_FAILURES = 5
FAILURE_WINDOW_S = 15 * 60
LOCKOUT_S = 15 * 60


class AuthError(Exception):
    """Erreur d'authentification ou de gestion de compte, sans secret."""


def _now() -> float:
    return time.time()


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def hash_password(password: str) -> str:
    """Hacher un mot de passe avec scrypt et un sel aléatoire."""
    if not isinstance(password, str):
        raise AuthError("Mot de passe invalide.")
    salt = os.urandom(SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return "scrypt$%d$%d$%d$%s$%s" % (
        SCRYPT_N,
        SCRYPT_R,
        SCRYPT_P,
        _b64(salt),
        _b64(digest),
    )


def verify_password(password: str, stored: str) -> bool:
    """Vérifier un mot de passe en temps constant, sans lever d'exception."""
    try:
        algo, n_s, r_s, p_s, salt_s, digest_s = stored.split("$")
        if algo != "scrypt":
            return False
        salt = _unb64(salt_s)
        expected = _unb64(digest_s)
        computed = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_s),
            r=int(r_s),
            p=int(p_s),
            dklen=len(expected),
        )
        return hmac.compare_digest(computed, expected)
    except (ValueError, TypeError, AttributeError):
        return False


def validate_username(username: str) -> str:
    value = (username or "").strip().lower()
    if not USERNAME_RE.match(value):
        raise AuthError(
            "Identifiant invalide : 3 à 32 caractères, minuscules, chiffres, "
            "point, tiret ou souligné."
        )
    return value


def validate_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 12:
        raise AuthError("Mot de passe trop court : 12 caractères minimum.")
    if len(password) > 256:
        raise AuthError("Mot de passe trop long (256 caractères maximum).")
    if any(not ch.isprintable() for ch in password):
        raise AuthError("Mot de passe invalide (caractère de contrôle).")
    return password


def _account_payload(row: Any) -> dict[str, Any]:
    """Compte exposable au client : jamais le hachage."""
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
        "disabled": bool(row["disabled"]),
        "created_at": row["created_at"],
        "last_login_at": row["last_login_at"],
    }


def _admin_count(conn: Any, exclude: Optional[str] = None) -> int:
    sql = "SELECT COUNT(*) AS n FROM accounts WHERE role = 'admin' AND disabled = 0"
    params: list[Any] = []
    if exclude:
        sql += " AND id != ?"
        params.append(exclude)
    row = conn.execute(sql, params).fetchone()
    return int(row["n"])


def create_account(
    username: str,
    password: str,
    *,
    role: str = "user",
    display_name: str = "",
    store: Optional[store_module.Store] = None,
) -> dict[str, Any]:
    """Créer un compte ; refuse un troisième administrateur."""
    db = store or store_module.get_store()
    username = validate_username(username)
    validate_password(password)
    role = (role or "user").strip().lower()
    if role not in ("admin", "user"):
        raise AuthError("Rôle inconnu.")
    name = (display_name or username).strip()[:60] or username

    with db.lock():
        conn = db.transaction()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if role == "admin" and _admin_count(conn) >= MAX_ADMINS:
                raise AuthError(
                    "Deux administrateurs existent déjà : créez un utilisateur."
                )
            account_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO accounts "
                "(id, username, display_name, role, password_hash, disabled, created_at) "
                "VALUES (?, ?, ?, ?, ?, 0, ?)",
                (account_id, username, name, role, hash_password(password), _now()),
            )
            conn.execute(
                "INSERT INTO preferences (account_id, dev_mode) VALUES (?, 0)",
                (account_id,),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    row = db.query_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
    assert row is not None
    return _account_payload(row)


def list_accounts(store: Optional[store_module.Store] = None) -> list[dict[str, Any]]:
    db = store or store_module.get_store()
    rows = db.query("SELECT * FROM accounts ORDER BY created_at ASC")
    return [_account_payload(row) for row in rows]


def get_account(account_id: str, store: Optional[store_module.Store] = None) -> Optional[dict[str, Any]]:
    db = store or store_module.get_store()
    row = db.query_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
    return _account_payload(row) if row else None


def set_password(account_id: str, password: str, store: Optional[store_module.Store] = None) -> None:
    validate_password(password)
    db = store or store_module.get_store()
    db.execute(
        "UPDATE accounts SET password_hash = ? WHERE id = ?",
        (hash_password(password), account_id),
    )
    revoke_account_sessions(account_id, store=db)


def update_account(
    account_id: str,
    *,
    role: Optional[str] = None,
    disabled: Optional[bool] = None,
    display_name: Optional[str] = None,
    store: Optional[store_module.Store] = None,
) -> dict[str, Any]:
    """Modifier un compte sans jamais pouvoir supprimer le dernier admin."""
    db = store or store_module.get_store()
    row = db.query_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
    if row is None:
        raise AuthError("Compte inconnu.")

    with db.lock():
        conn = db.transaction()
        try:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT * FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
            if current is None:
                raise AuthError("Compte inconnu.")
            new_role = current["role"] if role is None else (role or "").strip().lower()
            if new_role not in ("admin", "user"):
                raise AuthError("Rôle inconnu.")
            new_disabled = int(bool(current["disabled"]) if disabled is None else bool(disabled))
            if new_role == "admin" and _admin_count(conn, exclude=account_id) >= MAX_ADMINS:
                raise AuthError("Deux administrateurs existent déjà.")
            if (
                current["role"] == "admin"
                and _admin_count(conn, exclude=account_id) == 0
                and (new_role != "admin" or bool(new_disabled))
            ):
                raise AuthError(
                    "Impossible de retirer le dernier administrateur actif."
                )
            name = current["display_name"] if display_name is None else (
                (display_name or "").strip()[:60] or current["username"]
            )
            conn.execute(
                "UPDATE accounts SET role = ?, disabled = ?, display_name = ? WHERE id = ?",
                (new_role, new_disabled, name, account_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    if disabled:
        revoke_account_sessions(account_id, store=db)
    updated = db.query_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
    assert updated is not None
    return _account_payload(updated)


def delete_account(account_id: str, store: Optional[store_module.Store] = None) -> None:
    db = store or store_module.get_store()
    with db.lock():
        conn = db.transaction()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
            if row is None:
                raise AuthError("Compte inconnu.")
            if row["role"] == "admin" and _admin_count(conn, exclude=account_id) == 0:
                raise AuthError("Impossible de supprimer le dernier administrateur.")
            conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


# ------------------------------------------------------------------ sessions


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(
    account_id: str,
    *,
    ip: str = "",
    user_agent: str = "",
    store: Optional[store_module.Store] = None,
) -> tuple[str, str, float]:
    """Créer une session ; retourne (jeton, jeton CSRF, expiration absolue)."""
    db = store or store_module.get_store()
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    now = _now()
    expires = now + ABSOLUTE_TTL_S
    db.execute(
        "INSERT INTO sessions "
        "(id_hash, account_id, csrf_token, created_at, last_seen_at, expires_at, ip_hash, ua_hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            _hash_token(token),
            account_id,
            csrf,
            now,
            now,
            expires,
            hashlib.sha256(ip.encode()).hexdigest() if ip else None,
            hashlib.sha256(user_agent.encode()).hexdigest() if user_agent else None,
        ),
    )
    return token, csrf, expires


def resolve_session(
    token: str, store: Optional[store_module.Store] = None
) -> Optional[dict[str, Any]]:
    """Retrouver une session valide, ou None (expirée, révoquée, inconnue)."""
    if not token:
        return None
    db = store or store_module.get_store()
    row = db.query_one(
        "SELECT s.*, a.username, a.display_name, a.role, a.disabled "
        "FROM sessions s JOIN accounts a ON a.id = s.account_id "
        "WHERE s.id_hash = ?",
        (_hash_token(token),),
    )
    if row is None:
        return None
    now = _now()
    if bool(row["disabled"]) or now >= row["expires_at"]:
        revoke_session(token, store=db)
        return None
    if now - row["last_seen_at"] > IDLE_TTL_S:
        revoke_session(token, store=db)
        return None
    if now - row["last_seen_at"] > TOUCH_INTERVAL_S:
        db.execute(
            "UPDATE sessions SET last_seen_at = ? WHERE id_hash = ?",
            (now, _hash_token(token)),
        )
    return {
        "session_id": _hash_token(token),
        "account_id": row["account_id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
        "csrf_token": row["csrf_token"],
        "expires_at": row["expires_at"],
    }


def revoke_session(token: str, store: Optional[store_module.Store] = None) -> None:
    if not token:
        return
    db = store or store_module.get_store()
    db.execute("DELETE FROM sessions WHERE id_hash = ?", (_hash_token(token),))


def revoke_account_sessions(account_id: str, store: Optional[store_module.Store] = None) -> None:
    db = store or store_module.get_store()
    db.execute("DELETE FROM sessions WHERE account_id = ?", (account_id,))


# --------------------------------------------------------------- préférences


def get_preferences(account_id: str, store: Optional[store_module.Store] = None) -> dict[str, Any]:
    db = store or store_module.get_store()
    row = db.query_one("SELECT * FROM preferences WHERE account_id = ?", (account_id,))
    if row is None:
        db.execute("INSERT INTO preferences (account_id, dev_mode) VALUES (?, 0)", (account_id,))
        return {"account_id": account_id, "dev_mode": False, "locale": "fr", "theme": "dark"}
    return {
        "account_id": row["account_id"],
        "dev_mode": bool(row["dev_mode"]),
        "locale": row["locale"],
        "theme": row["theme"],
    }


def set_dev_mode(account_id: str, enabled: bool, store: Optional[store_module.Store] = None) -> dict[str, Any]:
    db = store or store_module.get_store()
    get_preferences(account_id, store=db)
    db.execute(
        "UPDATE preferences SET dev_mode = ? WHERE account_id = ?",
        (1 if enabled else 0, account_id),
    )
    return get_preferences(account_id, store=db)


# ------------------------------------------------------- limitation de débit


def _attempt_key(username: str, ip: str) -> str:
    return "%s|%s" % ((username or "").strip().lower(), ip or "")


def login_locked(username: str, ip: str, store: Optional[store_module.Store] = None) -> bool:
    db = store or store_module.get_store()
    row = db.query_one(
        "SELECT * FROM login_attempts WHERE key = ?", (_attempt_key(username, ip),)
    )
    if row is None:
        return False
    return bool(row["locked_until"] and row["locked_until"] > _now())


def record_login_failure(
    username: str, ip: str, store: Optional[store_module.Store] = None
) -> None:
    db = store or store_module.get_store()
    key = _attempt_key(username, ip)
    now = _now()
    row = db.query_one("SELECT * FROM login_attempts WHERE key = ?", (key,))
    if row is None or now - row["first_at"] > FAILURE_WINDOW_S:
        db.execute(
            "INSERT OR REPLACE INTO login_attempts (key, count, first_at, locked_until) "
            "VALUES (?, 1, ?, NULL)",
            (key, now),
        )
        return
    count = int(row["count"]) + 1
    locked = now + LOCKOUT_S if count >= MAX_FAILURES else None
    db.execute(
        "UPDATE login_attempts SET count = ?, locked_until = ? WHERE key = ?",
        (count, locked, key),
    )


def clear_login_failures(
    username: str, ip: str, store: Optional[store_module.Store] = None
) -> None:
    db = store or store_module.get_store()
    db.execute("DELETE FROM login_attempts WHERE key = ?", (_attempt_key(username, ip),))


def authenticate(
    username: str, password: str, store: Optional[store_module.Store] = None
) -> Optional[dict[str, Any]]:
    """Vérifier identifiant + mot de passe ; None si invalide ou désactivé."""
    db = store or store_module.get_store()
    row = db.query_one(
        "SELECT * FROM accounts WHERE username = ?", ((username or "").strip().lower(),)
    )
    if row is None or bool(row["disabled"]):
        # Coût constant : hacher quand même pour ne pas révéler l'existence
        # du compte par le temps de réponse.
        hash_password(password or "")
        return None
    if not verify_password(password or "", row["password_hash"]):
        return None
    db.execute("UPDATE accounts SET last_login_at = ? WHERE id = ?", (_now(), row["id"]))
    return _account_payload(row)


# --------------------------------------------------------------- CLI admin


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Gestion des comptes du site Miles Companion"
    )
    sub = parser.add_subparsers(dest="commande", required=True)

    add = sub.add_parser("add", help="Créer un compte")
    add.add_argument("username")
    add.add_argument("--role", choices=("admin", "user"), default="user")
    add.add_argument("--name", default="")

    sub.add_parser("list", help="Lister les comptes")

    pwd = sub.add_parser("password", help="Changer un mot de passe")
    pwd.add_argument("username")

    args = parser.parse_args()

    if args.commande == "add":
        password = getpass.getpass("Mot de passe (12 caractères minimum) : ")
        confirm = getpass.getpass("Confirmer : ")
        if password != confirm:
            print("Les deux saisies diffèrent.", file=sys.stderr)
            return 1
        try:
            account = create_account(
                args.username,
                password,
                role=args.role,
                display_name=args.name,
            )
        except AuthError as exc:
            print("Refus : %s" % exc, file=sys.stderr)
            return 1
        print("Compte créé : %s (%s)" % (account["username"], account["role"]))
        return 0

    if args.commande == "list":
        for account in list_accounts():
            print(
                "%-20s %-6s %s%s"
                % (
                    account["username"],
                    account["role"],
                    "désactivé" if account["disabled"] else "actif",
                    " · " + account["display_name"] if account["display_name"] else "",
                )
            )
        return 0

    if args.commande == "password":
        row = store_module.get_store().query_one(
            "SELECT id FROM accounts WHERE username = ?", (validate_username(args.username),)
        )
        if row is None:
            print("Compte inconnu.", file=sys.stderr)
            return 1
        password = getpass.getpass("Nouveau mot de passe : ")
        confirm = getpass.getpass("Confirmer : ")
        if password != confirm:
            print("Les deux saisies diffèrent.", file=sys.stderr)
            return 1
        try:
            set_password(row["id"], password)
        except AuthError as exc:
            print("Refus : %s" % exc, file=sys.stderr)
            return 1
        print("Mot de passe changé ; sessions révoquées.")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())

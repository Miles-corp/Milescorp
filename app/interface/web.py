"""Interface web minimale de MILES (stdlib http.server).

Sépare clairement :
- le serveur web (ici) ;
- la logique applicative (WebApp) ;
- les fournisseurs IA (injectés via WebApp).

Par défaut, le serveur écoute uniquement sur 127.0.0.1.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from app.ai_providers.base import AIProvider, AIProviderError
from app.ai_providers.public_errors import public_provider_error as _public_provider_error
from app.config.settings import Settings
from app.core.conversation import Conversation
from app.memory.persistent import PersistentMemory, PersistentMemoryError
from app.tools.service import ToolService
from app.utilities.redaction import REDACTED, sanitize_text

logger = logging.getLogger("miles.web")
if not logger.handlers:
    # Handler neutre : l'application reste libre de configurer la
    # journalisation. Évite la sortie "No handlers could be found" et
    # n'écrit rien sur stderr par défaut.
    logger.addHandler(logging.NullHandler())

__all__ = [
    "REDACTED",
    "sanitize_text",
    "public_provider_error",
    "LOCAL_ONLY_HOST",
    "MAX_BODY_BYTES",
    "WebServerSecurityError",
    "RequestBodyError",
    "assert_local_host",
    "WebApp",
    "MilesHandler",
    "MilesWebServer",
]

# Adresse d'écoute du serveur web. Elle est imposée par le code et n'est
# pas configurable : le service MILES doit rester strictement local, jamais
# joignable depuis le réseau local ou Internet.
LOCAL_ONLY_HOST = "127.0.0.1"

# Taille maximale du corps d'une requête HTTP, en octets (64 KiB).
# Au-delà, la requête est refusée avec HTTP 413 sans que les données
# annoncées soient lues ou allouées. Le corps n'est JAMAIS lu au-delà de
# cette limite : c'est une invariant de sécurité (un client ne peut pas
# forcer le serveur à consommer de la mémoire en annonçant une taille).
MAX_BODY_BYTES = 65536


class WebServerSecurityError(Exception):
    """Refus de démarrer le serveur web sur une adresse non locale."""


class RequestBodyError(Exception):
    """Corps de requête HTTP invalide (en-tête ou taille).

    Le statut HTTP à renvoyer au client est porté par l'exception.
    """

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def assert_local_host(host: str) -> str:
    """Vérifier qu'une adresse d'écoute est strictement locale.

    Seule l'adresse 127.0.0.1 est acceptée. Toute autre adresse est
    refusée explicitement, y compris 0.0.0.0, :: et les adresses du
    réseau local.
    """
    if not isinstance(host, str):
        raise WebServerSecurityError(
            f"Adresse d'écoute invalide : {host!r}. Le serveur web MILES "
            f"n'écoute que sur {LOCAL_ONLY_HOST}."
        )
    if host != LOCAL_ONLY_HOST:
        raise WebServerSecurityError(
            f"Adresse d'écoute refusée : {host!r}. Le serveur web MILES est "
            f"strictement local et n'écoute que sur {LOCAL_ONLY_HOST}."
        )
    return host

# Motifs de secrets : définis dans app/utilities/redaction.py (source unique
# de vérité, partagée avec la persistance des conversations).
# La classification publique des erreurs fournisseur est définie dans
# app/ai_providers/public_errors.py (source unique, partagée avec le CLI).


def public_provider_error(exc: Exception) -> str:
    """Retourner un message public sûr pour une erreur de fournisseur.

    Ré-exporté depuis ``app.ai_providers.public_errors`` afin que l'interface
    terminal et l'interface web exposent exactement le même message.
    """
    return _public_provider_error(exc)


class WebApp:
    """Logique applicative exposée par l'interface web.

    Dépend uniquement des composants métier de MILES (fournisseurs,
    conversation, mémoire persistante, configuration). Aucun accès shell
    arbitraire n'est permis.
    """

    def __init__(
        self,
        settings: Settings,
        provider: Optional[AIProvider] = None,
        conversation: Optional[Conversation] = None,
        memory: Optional[PersistentMemory] = None,
        tool_service: Optional[ToolService] = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.conversation = conversation or Conversation(
            history_limit=settings.get("history_limit", 10)
        )
        self.memory = memory
        # Même service d'outils que le CLI : aucune duplication de la
        # logique métier (validation, permissions, confirmation, audit).
        self.tool_service = tool_service

    # --- Outils ---

    def list_tools(self) -> dict[str, Any]:
        """Retourner le catalogue des outils disponibles."""
        if self.tool_service is None:
            return {"tools": [], "error": "Aucun service d'outils disponible."}
        return {"tools": self.tool_service.list_tools()}

    def run_tool(self, data: dict[str, Any]) -> dict[str, Any]:
        """Exécuter un outil via le service partagé (même moteur que le CLI).

        Le client peut transmettre ``confirmation_token`` et
        ``user_confirmed`` pour confirmer une action à effet externe.
        """
        if self.tool_service is None:
            return {"error": "Aucun service d'outils disponible."}

        tool_id = data.get("tool", data.get("tool_id", ""))
        if not isinstance(tool_id, str) or not tool_id.strip():
            return {"error": "Identifiant d'outil manquant."}

        raw_parameters = data.get("parameters", {})
        if raw_parameters is None:
            raw_parameters = {}
        if not isinstance(raw_parameters, dict):
            return {"error": "Paramètres invalides."}
        parameters = {str(k): v for k, v in raw_parameters.items()}

        user_confirmed = bool(data.get("user_confirmed", False))
        confirmation_token = data.get("confirmation_token")
        if confirmation_token is not None and not isinstance(confirmation_token, str):
            return {"error": "Jeton de confirmation invalide."}

        result = self.tool_service.request_tool(
            tool_id=tool_id.strip(),
            parameters=parameters,
            user_confirmed=user_confirmed,
            confirmation_token=confirmation_token,
        )
        return self.tool_service.describe_result(result)

    # --- Fournisseur ---

    def provider_state(self) -> dict[str, Any]:
        """Retourner l'état du fournisseur IA."""
        name = self.provider.name if self.provider else "non configuré"
        available = False
        if self.provider is not None:
            try:
                available = self.provider.is_available()
            except Exception:  # noqa: BLE001 — ne pas faire tomber le serveur
                available = False
        return {
            "name": name,
            "available": available,
            "provider": self.settings.provider,
        }

    # --- Conversation ---

    def send_message(self, text: str) -> dict[str, Any]:
        """Envoyer un message à l'IA et retourner la réponse ou l'erreur."""
        if self.provider is None:
            return {
                "error": "Aucun fournisseur IA configuré.",
                "provider": self.settings.provider,
            }

        self.conversation.add_user_message(text)
        context = self.conversation.get_context()

        try:
            response = self.provider.chat(context)
        except AIProviderError as exc:
            # La conversation est conservée : le message utilisateur reste.
            # Le détail technique reste interne et assaini de tout secret.
            logger.error(
                "Échec de l'appel au fournisseur IA : %s", sanitize_text(exc)
            )
            return {
                "error": public_provider_error(exc),
                "provider": self.settings.provider,
                "context_preserved": True,
            }
        except Exception as exc:  # noqa: BLE001 — ne pas faire tomber le serveur
            # Aucune trace brute n'est journalisée : la trace d'appels
            # contiendrait le message d'origine de l'exception, donc
            # potentiellement un secret de format inconnu. Seul le nom de
            # la classe et le message assaini sont conservés.
            logger.error(
                "Erreur interne lors de l'appel au fournisseur IA (%s) : %s",
                type(exc).__name__,
                sanitize_text(exc),
            )
            return {
                "error": "Erreur interne du service.",
                "provider": self.settings.provider,
                "context_preserved": True,
            }

        self.conversation.add_assistant_message(response)
        return {
            "response": response,
            "provider": self.settings.provider,
            "context_preserved": True,
        }

    # --- Mémoire persistante ---

    def memory_state(self) -> dict[str, Any]:
        """Retourner l'état de la mémoire persistante."""
        if self.memory is None:
            return {"enabled": False, "available": False}
        return {
            "enabled": True,
            "available": self.memory.is_available,
        }

    def list_memories(self) -> list[dict[str, Any]]:
        """Lister les souvenirs persistants."""
        if self.memory is None or not self.memory.is_available:
            return []
        return self.memory.list_memories()

    def add_memory(self, content: str) -> dict[str, Any]:
        """Enregistrer un souvenir explicite."""
        if self.memory is None or not self.memory.is_available:
            return {"error": "Mémoire persistante indisponible ou désactivée."}
        try:
            mem_id = self.memory.add_memory(content)
            return {"id": mem_id, "content": content}
        except PersistentMemoryError as exc:
            # Message produit par MILES lui-même (texte fixe) : ne contient
            # aucune valeur sensible, il peut être renvoyé au client.
            logger.error(
                "Refus d'enregistrement d'un souvenir : %s", sanitize_text(exc)
            )
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001 — ne pas faire tomber le serveur
            logger.error(
                "Erreur interne lors de l'enregistrement d'un souvenir (%s) : %s",
                type(exc).__name__,
                sanitize_text(exc),
            )
            return {"error": "Erreur interne du service."}

    def delete_memory(self, memory_id: int) -> dict[str, Any]:
        """Supprimer un souvenir ciblé."""
        if self.memory is None or not self.memory.is_available:
            return {"error": "Mémoire persistante indisponible ou désactivée."}
        try:
            deleted = self.memory.delete_memory(memory_id)
            if deleted:
                return {"id": memory_id, "deleted": True}
            return {"error": f"Aucun souvenir avec l'id {memory_id}."}
        except PersistentMemoryError as exc:
            # Message produit par MILES lui-même (texte fixe) : ne contient
            # aucune valeur sensible, il peut être renvoyé au client.
            logger.error(
                "Refus de suppression d'un souvenir : %s", sanitize_text(exc)
            )
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Erreur interne lors de la suppression d'un souvenir (%s) : %s",
                type(exc).__name__,
                sanitize_text(exc),
            )
            return {"error": "Erreur interne du service."}


class MilesHandler(BaseHTTPRequestHandler):
    """Gestionnaire des requêtes HTTP pour MILES."""

    # Délai maximal d'attente d'une requête. Évite qu'un client qui annonce
    # une taille puis n'envoie rien ne bloque un thread indéfiniment.
    timeout = 30

    # L'application métier est attachée au serveur via server.miles_app.
    app: Optional[WebApp] = None

    def log_message(self, format: str, *args: Any) -> None:
        """Désactiver les logs de requête HTTP par défaut pour éviter
        l'exposition accidentelle de données sensibles dans les logs."""
        return  # noqa: D401

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict[str, Any]:
        """Lire et valider le corps de la requête.

        Le corps ne doit jamais dépasser MAX_BODY_BYTES octets. La taille
        annoncée est contrôlée AVANT toute lecture : un corps trop
        volumineux n'est donc ni lu ni alloué.

        Raises:
            RequestBodyError: en-tête Content-Length absent, négatif, non
                numérique, corps trop volumineux (413) ou incomplet.
        """
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            length = 0
        else:
            try:
                length = int(raw_length)
            except (TypeError, ValueError):
                raise RequestBodyError(
                    400, "Requête mal formée : en-tête Content-Length invalide."
                ) from None
            if length < 0:
                raise RequestBodyError(
                    400, "Requête mal formée : en-tête Content-Length invalide."
                )
            if length > MAX_BODY_BYTES:
                # Refus immédiat : les données annoncées ne sont pas lues.
                # Le corps n'est jamais consommé au-delà de la limite, même
                # en partie : c'est ce qui garantit qu'un client ne peut pas
                # forcer une allocation mémoire côté serveur.
                # Conséquence assumée : le client peut voir sa connexion
                # réinitialisée au lieu de lire la réponse 413, s'il
                # écrivait encore son corps au moment du refus.
                raise RequestBodyError(
                    413,
                    "Requête trop volumineuse : le corps dépasse la limite autorisée.",
                )

        raw = b""
        if length > 0:
            try:
                raw = self.rfile.read(length)
            except (TimeoutError, OSError):
                raise RequestBodyError(
                    400, "Requête mal formée : corps de requête incomplet."
                ) from None
            if len(raw) < length:
                raise RequestBodyError(
                    400, "Requête mal formée : corps de requête incomplet."
                )

        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
        if not isinstance(data, dict):
            raise RequestBodyError(
                400, "Requête mal formée : corps JSON invalide."
            )
        return data

    def _html_escape(self, text: str) -> str:
        return html.escape(text or "", quote=True)

    # --- Routes ---

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]

        if path == "/":
            self._serve_index()
        elif path == "/status":
            self._handle_status()
        elif path == "/memory":
            self._handle_list_memories()
        elif path == "/tools":
            self._handle_list_tools()
        else:
            self._send_json(404, {"error": "Not found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        try:
            data = self._read_body()
        except RequestBodyError as exc:
            # Le corps n'a pas été lu : la connexion ne peut plus être
            # réutilisée pour une requête suivante.
            self.close_connection = True
            self._send_json(exc.status, {"error": exc.message})
            return

        if path == "/message":
            self._handle_message(data)
        elif path == "/remember":
            self._handle_remember(data)
        elif path == "/forget":
            self._handle_forget(data)
        elif path == "/tool":
            self._handle_run_tool(data)
        else:
            self._send_json(404, {"error": "Not found", "path": path})

    # --- Handlers ---

    def _serve_index(self) -> None:
        html_content = self._build_index_html()
        body = html_content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _build_index_html(self) -> str:
        provider_state = self.app.provider_state() if self.app else {}
        memory_state = self.app.memory_state() if self.app else {}

        return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>MILES — Assistant personnel</title>
<style>
body {{ font-family: system-ui, -apple-system, sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; }}
#chat {{ border: 1px solid #ccc; border-radius: 8px; padding: 1rem; height: 40vh; overflow-y: auto; background: #fafafa; margin-bottom: 1rem; }}
.msg {{ margin: 0.5rem 0; padding: 0.5rem; border-radius: 6px; }}
.user {{ background: #e3f2fd; }}
.assistant {{ background: #e8f5e9; }}
.error {{ background: #ffebee; color: #b71c1c; }}
.system {{ background: #eeeeee; color: #666; font-size: 0.9rem; }}
input[type="text"] {{ width: 70%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; }}
button {{ padding: 0.5rem 1rem; border: none; background: #1976d2; color: white; border-radius: 4px; cursor: pointer; }}
button:hover {{ background: #1565c0; }}
button.secondary {{ background: #757575; }}
button.secondary:hover {{ background: #616161; }}
.status {{ margin: 1rem 0; padding: 0.5rem; background: #f5f5f5; border-radius: 4px; font-size: 0.9rem; }}
.memories {{ margin: 1rem 0; }}
.memories ul {{ list-style: none; padding: 0; }}
.memories li {{ margin: 0.25rem 0; padding: 0.25rem; background: #f5f5f5; border-radius: 4px; }}
.tools {{ margin: 1rem 0; }}
.tools ul {{ list-style: none; padding: 0; }}
.tools li {{ margin: 0.35rem 0; padding: 0.35rem; background: #f5f5f5; border-radius: 4px; font-size: 0.9rem; }}
.tools code {{ background: #e0e0e0; padding: 0 0.25rem; border-radius: 3px; }}
.tools input[type="text"] {{ width: auto; padding: 0.25rem; border: 1px solid #ccc; border-radius: 4px; font-size: 0.85rem; }}
</style>
</head>
<body>
<h1>MILES — Assistant personnel</h1>

<div class="status">
<strong>Fournisseur :</strong> {self._html_escape(str(provider_state.get('name', '—')))}<br>
<strong>Disponible :</strong> {'oui' if provider_state.get('available') else 'non'}<br>
<strong>Mémoire :</strong> {'activée' if memory_state.get('available') else 'désactivée/indisponible'}
</div>

<div id="chat">
<div class="msg system">Bienvenue dans MILES. Tapez votre message ci-dessous.</div>
</div>

<form id="form" onsubmit="return sendMessage(event)">
<input type="text" id="input" placeholder="Votre message..." autocomplete="off">
<button type="submit">Envoyer</button>
<button type="button" class="secondary" onclick="loadStatus()">Rafraîchir le statut</button>
</form>

<div class="memories" id="memories"></div>

<div class="tools" id="tools">
<strong>Outils :</strong>
<div id="toolsList"><p>Chargement…</p></div>
</div>

<script>
async function sendMessage(e) {{
  e.preventDefault();
  const input = document.getElementById('input');
  const text = input.value.trim();
  if (!text) return false;
  appendMessage('user', text);
  input.value = '';
  try {{
    const res = await fetch('/message', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ message: text }})
    }});
    const data = await res.json();
    if (data.response) appendMessage('assistant', data.response);
    if (data.error) appendMessage('error', 'Erreur : ' + data.error);
  }} catch (err) {{
    appendMessage('error', 'Erreur réseau : ' + err);
  }}
  return false;
}}

async function loadStatus() {{
  try {{
    const res = await fetch('/status');
    const data = await res.json();
    document.querySelector('.status').innerHTML =
      '<strong>Fournisseur :</strong> ' + escapeHtml(data.name) + '<br>' +
      '<strong>Disponible :</strong> ' + (data.available ? 'oui' : 'non') + '<br>' +
      '<strong>Mémoire :</strong> ' + (data.memory_available ? 'activée' : 'désactivée/indisponible');
    loadMemories();
  }} catch (err) {{ console.error(err); }}
}}

async function loadMemories() {{
  try {{
    const res = await fetch('/memory');
    const data = await res.json();
    const container = document.getElementById('memories');
    if (!Array.isArray(data) || data.length === 0) {{
      container.innerHTML = '<p>Aucun souvenir enregistré.</p>';
      return;
    }}
    container.innerHTML = '<strong>Souvenirs :</strong><ul>' +
      data.map(m => '<li>[{0}] {1} (catégorie: {{m.category}}, importance: {{m.importance}})</li>'.replace('{{0}}', m.id).replace('{{1}}', escapeHtml(m.content))).join('') +
      '</ul>';
  }} catch (err) {{ console.error(err); }}
}}

async function loadTools() {{
  const container = document.getElementById('toolsList');
  try {{
    const res = await fetch('/tools');
    const data = await res.json();
    if (!Array.isArray(data.tools) || data.tools.length === 0) {{
      container.innerHTML = '<p>Aucun outil disponible.</p>';
      return;
    }}
    container.innerHTML = '<ul>' + data.tools.map(t => {{
      const champs = (t.parameters || []).map(p =>
        '<input type="text" data-tool="' + escapeHtml(t.id) + '" data-param="' + escapeHtml(p.name) +
        '" data-type="' + escapeHtml(p.type) + '" placeholder="' + escapeHtml(p.name) + '" size="12">'
      ).join(' ');
      return '<li><code>' + escapeHtml(t.id) + '</code> [' + escapeHtml(t.risk_level) + '] ' +
        escapeHtml(t.description) +
        (t.requires_confirmation ? ' <em>(confirmation requise)</em>' : '') +
        ' ' + champs +
        ' <button type="button" class="secondary" onclick="runTool(\\'' + escapeHtml(t.id) + '\\')">Exécuter</button></li>';
    }}).join('') + '</ul>';
  }} catch (err) {{
    container.innerHTML = '<p>Erreur de chargement des outils.</p>';
    console.error(err);
  }}
}}

function collectToolParams(toolId) {{
  const params = {{}};
  document.querySelectorAll('input[data-tool="' + toolId + '"]').forEach(input => {{
    const valeur = input.value.trim();
    if (!valeur) return;
    const type = input.getAttribute('data-type');
    if (type === 'int') {{
      params[input.getAttribute('data-param')] = parseInt(valeur, 10);
    }} else if (type === 'float') {{
      params[input.getAttribute('data-param')] = parseFloat(valeur);
    }} else if (type === 'bool') {{
      params[input.getAttribute('data-param')] = (valeur === 'true' || valeur === '1');
    }} else {{
      params[input.getAttribute('data-param')] = valeur;
    }}
  }});
  return params;
}}

async function postTool(toolId, params, userConfirmed, token) {{
  const body = {{ tool: toolId, parameters: params }};
  if (userConfirmed) {{
    body.user_confirmed = true;
    body.confirmation_token = token;
  }}
  const res = await fetch('/tool', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify(body)
  }});
  return await res.json();
}}

async function runTool(toolId) {{
  const params = collectToolParams(toolId);
  let data = await postTool(toolId, params, false, null);
  if (data.confirmation_required) {{
    // Confirmation humaine explicite : l'utilisateur tranche dans le
    // navigateur avant que le jeton ne soit renvoyé.
    const ok = window.confirm("L'outil '" + toolId + "' requiert une confirmation humaine.\\nExécuter ?");
    if (!ok) {{
      appendMessage('system', 'Action annulée.');
      return;
    }}
    data = await postTool(toolId, params, true, data.confirmation_token);
  }}
  if (data.success) {{
    appendMessage('assistant', 'Résultat de ' + toolId + ' :\\n' + formatToolResult(data.result));
  }} else {{
    appendMessage('error', 'Outil ' + toolId + ' : ' + (data.error || 'échec'));
  }}
}}

function formatToolResult(result) {{
  if (result === null || result === undefined) return '(aucun résultat)';
  if (typeof result === 'object') return JSON.stringify(result, null, 2);
  return String(result);
}}

function appendMessage(role, text) {{
  const chat = document.getElementById('chat');
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}}

function escapeHtml(text) {{
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}}

loadStatus();
loadTools();
</script>
</body>
</html>"""

    def _handle_status(self) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        state = self.app.provider_state()
        state["memory_available"] = self.app.memory.is_available if self.app.memory else False
        self._send_json(200, state)

    def _handle_list_tools(self) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        payload = self.app.list_tools()
        status = 200 if "error" not in payload else 503
        self._send_json(status, payload)

    def _handle_run_tool(self, data: dict[str, Any]) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        payload = self.app.run_tool(data)
        # Une demande de confirmation est une réponse normale du protocole
        # (200 + jeton), pas une erreur : le client doit pouvoir confirmer.
        if payload.get("confirmation_required"):
            self._send_json(200, payload)
            return
        if not payload.get("success"):
            # Refus ou échec de l'outil : erreur côté appelant, pas serveur.
            self._send_json(400, payload)
            return
        self._send_json(200, payload)

    def _handle_list_memories(self) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        memories = self.app.list_memories()
        self._send_json(200, memories)

    def _handle_message(self, data: dict[str, Any]) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        text = data.get("message", "")
        if not isinstance(text, str) or not text.strip():
            self._send_json(400, {"error": "Message vide ou invalide."})
            return
        result = self.app.send_message(text.strip())
        status = 200 if "response" in result else 400
        self._send_json(status, result)

    def _handle_remember(self, data: dict[str, Any]) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        content = data.get("content", "")
        if not isinstance(content, str) or not content.strip():
            self._send_json(400, {"error": "Contenu vide ou invalide."})
            return
        result = self.app.add_memory(content.strip())
        status = 200 if "id" in result else 400
        self._send_json(status, result)

    def _handle_forget(self, data: dict[str, Any]) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        memory_id = data.get("id")
        try:
            memory_id = int(memory_id)
        except (TypeError, ValueError):
            self._send_json(400, {"error": "Identifiant invalide."})
            return
        result = self.app.delete_memory(memory_id)
        status = 200 if result.get("deleted") else 400
        self._send_json(status, result)


class MilesWebServer:
    """Serveur web MILES, strictement local (127.0.0.1 uniquement).

    L'adresse d'écoute est imposée par le code et n'est pas configurable.
    Toute tentative de démarrage sur une adresse non locale est refusée
    explicitement, que ce soit via le constructeur ou via une affectation
    directe de l'attribut `host`.
    """

    #: Adresse d'écoute autorisée.
    ALLOWED_HOST = LOCAL_ONLY_HOST

    def __init__(
        self,
        app: WebApp,
        host: str = LOCAL_ONLY_HOST,
        port: int = 8080,
    ) -> None:
        self.app = app
        # Passe par la propriété de validation : toute adresse non locale
        # est refusée dès la construction.
        self.host = host
        self.port = port
        self._server: Optional[ThreadingHTTPServer] = None

    @property
    def host(self) -> str:
        """Adresse d'écoute du serveur (toujours locale)."""
        return self._host

    @host.setter
    def host(self, value: str) -> None:
        self._host = assert_local_host(value)

    def start(self) -> None:
        # Revalidation avant toute liaison : `host` est un attribut public,
        # il pourrait avoir été modifié par affectation directe.
        host = assert_local_host(self.host)
        MilesHandler.app = self.app
        self._server = ThreadingHTTPServer((host, self.port), MilesHandler)
        print(f"Interface web MILES sur http://{host}:{self.port}")
        self._server.serve_forever()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()

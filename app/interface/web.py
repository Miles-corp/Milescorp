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
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from app.ai_providers.base import AIProvider, AIProviderError
from app.config.settings import Settings
from app.core.conversation import Conversation
from app.memory.persistent import PersistentMemory


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
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.conversation = conversation or Conversation(
            history_limit=settings.get("history_limit", 10)
        )
        self.memory = memory

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
            return {
                "error": f"Erreur du fournisseur IA : {exc}",
                "provider": self.settings.provider,
                "context_preserved": True,
            }
        except Exception as exc:  # noqa: BLE001 — ne pas faire tomber le serveur
            return {
                "error": f"Erreur inattendue : {exc}",
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
        except Exception as exc:  # noqa: BLE001 — ne pas faire tomber le serveur
            return {"error": str(exc)}

    def delete_memory(self, memory_id: int) -> dict[str, Any]:
        """Supprimer un souvenir ciblé."""
        if self.memory is None or not self.memory.is_available:
            return {"error": "Mémoire persistante indisponible ou désactivée."}
        try:
            deleted = self.memory.delete_memory(memory_id)
            if deleted:
                return {"id": memory_id, "deleted": True}
            return {"error": f"Aucun souvenir avec l'id {memory_id}."}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}


class MilesHandler(BaseHTTPRequestHandler):
    """Gestionnaire des requêtes HTTP pour MILES."""

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
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

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
        else:
            self._send_json(404, {"error": "Not found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        data = self._read_body()

        if path == "/message":
            self._handle_message(data)
        elif path == "/remember":
            self._handle_remember(data)
        elif path == "/forget":
            self._handle_forget(data)
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
    """Serveur web MILES sur 127.0.0.1 par défaut."""

    def __init__(
        self,
        app: WebApp,
        host: str = "127.0.0.1",
        port: int = 8080,
    ) -> None:
        self.app = app
        self.host = host
        self.port = port
        self._server: Optional[ThreadingHTTPServer] = None

    def start(self) -> None:
        MilesHandler.app = self.app
        self._server = ThreadingHTTPServer((self.host, self.port), MilesHandler)
        print(f"Interface web MILES sur http://{self.host}:{self.port}")
        self._server.serve_forever()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()

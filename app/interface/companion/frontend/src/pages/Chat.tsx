import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { Badge, Card, PageHeader } from "../components/ui";

interface Message {
  id: number;
  role: "user" | "miles";
  text: string;
  error?: boolean;
}

export function ChatPage() {
  const { me } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const nextId = useRef(1);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.title = "Conversation — Miles Companion";
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  async function send(event: FormEvent) {
    event.preventDefault();
    const value = text.trim();
    if (!value || busy) return;
    const id = nextId.current++;
    setMessages((current) => [...current, { id, role: "user", text: value }]);
    setText("");
    setBusy(true);
    try {
      const result = await api.message(value);
      setMessages((current) => [
        ...current,
        {
          id: nextId.current++,
          role: "miles",
          text: result.response || result.error || "Réponse vide.",
          error: Boolean(result.error),
        },
      ]);
    } catch (exc) {
      setMessages((current) => [
        ...current,
        { id: nextId.current++, role: "miles", text: errorMessage(exc), error: true },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Conversation"
        title="Parler à MILES"
        description="Le contexte est conservé côté serveur par MILES. Le site relaie le message ; aucune clé de fournisseur n'est exposée."
        actions={
          <Badge tone={me?.miles_configured ? "ok" : "warn"}>
            {me?.miles_configured ? "MILES configuré" : "MILES non configuré"}
          </Badge>
        }
      />

      <Card className="chat-card">
        <div className="chat-log" aria-live="polite">
          {messages.length === 0 ? (
            <p className="muted chat-intro">
              Écrivez un message. Si MILES n'est pas configuré, la réponse sera une
              erreur explicite — jamais une réponse fabriquée.
            </p>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={`chat-msg chat-${message.role} ${message.error ? "chat-error" : ""}`.trim()}
              >
                <span className="chat-role">{message.role === "user" ? "Vous" : "MILES"}</span>
                <p>{message.text}</p>
              </div>
            ))
          )}
          {busy ? <p className="muted small">MILES réfléchit…</p> : null}
          <div ref={bottom} />
        </div>

        <form onSubmit={send} className="chat-form">
          <label className="sr-only" htmlFor="chat-input">
            Votre message
          </label>
          <input
            id="chat-input"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Écrivez à MILES…"
            disabled={busy}
            autoComplete="off"
          />
          <button type="submit" className="btn btn-primary" disabled={busy || !text.trim()}>
            <i className={busy ? "ri-loader-3-line spin" : "ri-send-plane-2-line"} aria-hidden="true" />
            Envoyer
          </button>
        </form>
      </Card>
    </>
  );
}

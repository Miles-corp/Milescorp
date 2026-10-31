import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import type { ProviderInfo, ProviderStatus } from "../types";
import { providerLabel } from "../format";
import {
  Badge,
  Card,
  ConfirmAction,
  ErrorState,
  Loading,
  PageHeader,
} from "../components/ui";

const ICONS: Record<string, string> = {
  groq: "ri-flashlight-line",
  openai: "ri-robot-2-line",
  anthropic: "ri-quill-pen-line",
  gemini: "ri-sparkling-2-line",
  ollama: "ri-computer-line",
};

function onBox(): boolean {
  return ["127.0.0.1", "localhost", "::1"].includes(window.location.hostname);
}

export function ProvidersPage() {
  const [items, setItems] = useState<ProviderInfo[]>([]);
  const [status, setStatus] = useState<ProviderStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const onTheBox = onBox();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.providers();
      setItems(result.providers);
      setStatus(result.status);
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    document.title = "Fournisseurs IA — Miles Companion";
    void load();
  }, [load]);

  function authorize(id: string) {
    window.open(`/setup?provider=${encodeURIComponent(id)}`, "_blank", "noopener");
  }

  return (
    <>
      <PageHeader
        eyebrow="Intelligence artificielle"
        title="Accès aux fournisseurs"
        description="Un accès s'autorise, il ne se saisit pas : aucun champ de clé n'existe dans le site. L'autorisation est enregistrée sur la box, le navigateur ne reçoit qu'un état."
        actions={
          <button type="button" className="btn btn-ghost" onClick={() => void load()}>
            <i className="ri-refresh-line" aria-hidden="true" />
            Rafraîchir
          </button>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {loading && items.length === 0 ? <Loading label="Lecture des accès…" /> : null}

      <Card title="Accès actif" subtitle="état lu sur la box, jamais déduit">
        <div className="row between wrap">
          <div>
            <p className="metric-big">{providerLabel(status?.provider)}</p>
            <p className="muted small">
              {status?.model || "modèle par défaut"} · mode {status?.mode || "inconnu"}
            </p>
          </div>
          <Badge tone={status?.configured ? "ok" : "warn"}>
            {status?.configured ? "accès autorisé" : "aucun accès"}
          </Badge>
        </div>
        <p className="hint-line">
          {status?.restart_required
            ? "Redémarrage de miles.py requis pour que le nouvel accès prenne effet."
            : "Un changement d'accès prend effet au prochain démarrage de miles.py."}
        </p>
      </Card>

      <div className="provider-grid">
        {items.map((provider) => {
          const local = provider.mode === "local";
          const ready = provider.configured || local;
          return (
            <article
              className={`provider-card ${provider.active ? "provider-active" : ""}`.trim()}
              key={provider.id}
            >
              <div className="provider-head">
                <span className="provider-icon" aria-hidden="true">
                  <i className={ICONS[provider.id] || "ri-robot-3-line"} />
                </span>
                <div>
                  <h2>{provider.label}</h2>
                  <p className="muted small">
                    {local ? "moteur local · aucun appel sortant" : "service distant"}
                  </p>
                </div>
                {provider.active ? (
                  <Badge tone="ok">actif</Badge>
                ) : ready ? (
                  <Badge tone="muted">autorisé</Badge>
                ) : (
                  <Badge tone="warn">non autorisé</Badge>
                )}
              </div>

              <p className="provider-model">
                <i className="ri-cpu-line" aria-hidden="true" />
                {provider.model || "modèle par défaut"}
              </p>

              <div className="provider-actions">
                {!local && !ready ? (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => authorize(provider.id)}
                    disabled={!onTheBox}
                    title={
                      onTheBox
                        ? "Ouvre la page d'autorisation de la box"
                        : "L'autorisation se donne sur la box elle-même (127.0.0.1)"
                    }
                  >
                    <i className="ri-shield-keyhole-line" aria-hidden="true" />
                    Autoriser
                  </button>
                ) : null}

                {ready && !provider.active ? (
                  <ConfirmAction
                    action="provider.activate"
                    payload={{ provider: provider.id }}
                    label="Activer"
                    icon="ri-toggle-line"
                    className="btn btn-primary"
                    onDone={() => void load()}
                  />
                ) : null}

                {ready ? (
                  <ConfirmAction
                    action="provider.test"
                    payload={{ provider: provider.id }}
                    label="Tester"
                    icon="ri-signal-tower-line"
                    className="btn btn-ghost"
                    onDone={() => void load()}
                  />
                ) : null}
              </div>

              {!local && !ready && !onTheBox ? (
                <p className="hint-line">
                  À ouvrir depuis la box : <code>http://127.0.0.1:8787/setup</code>. Le site
                  distant ne collecte jamais d'accès.
                </p>
              ) : null}
            </article>
          );
        })}
      </div>

      <Card title="Ce que le site ne fait jamais" subtitle="règles non négociables">
        <ul className="plain">
          <li>Demander une clé, sa longueur ou un extrait dans l'interface du site.</li>
          <li>Journaliser un accès ou un jeton de session.</li>
          <li>Stocker un accès dans la base SQLite du site ou dans le navigateur.</li>
          <li>Servir une page d'autorisation hors de la boucle locale.</li>
        </ul>
      </Card>
    </>
  );
}

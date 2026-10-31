import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import type { AccessEntry, AuditEvent } from "../types";
import { formatDate } from "../format";
import { useAuth } from "../auth";
import { Badge, Card, ErrorState, Loading, PageHeader } from "../components/ui";

export function JournalPage() {
  const { me } = useAuth();
  const dev = Boolean(me?.preferences.dev_mode);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [access, setAccess] = useState<AccessEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"audit" | "access">("audit");

  const load = useCallback(async () => {
    if (!dev) return;
    setLoading(true);
    setError(null);
    try {
      const [auditResult, accessResult] = await Promise.all([
        api.journal(),
        api.accessLog(),
      ]);
      setEvents(auditResult.events);
      setAccess(accessResult.entries);
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setLoading(false);
    }
  }, [dev]);

  useEffect(() => {
    document.title = "Journal — Miles Companion";
    void load();
  }, [load]);

  if (!dev) {
    return (
      <>
        <PageHeader eyebrow="Journal" title="Mode développeur requis" />
        <p className="callout callout-warn">
          Le journal d'audit et le journal d'accès ne sont visibles qu'en mode
          développeur. <Link to="/reglages">Activer le mode développeur</Link>.
        </p>
      </>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Journal"
        title="Ce que le site a réellement fait"
        description="Événements expurgés : aucune clé, aucun jeton, aucun cookie, aucun corps de requête. Les comptes non administrateurs ne voient que leurs propres événements d'audit."
        actions={
          <button type="button" className="btn btn-ghost" onClick={() => void load()}>
            <i className="ri-refresh-line" aria-hidden="true" />
            Rafraîchir
          </button>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}

      <div className="segmented" role="group" aria-label="Type de journal">
        <button
          type="button"
          className={tab === "audit" ? "is-active" : ""}
          onClick={() => setTab("audit")}
          aria-pressed={tab === "audit"}
        >
          Audit ({events.length})
        </button>
        <button
          type="button"
          className={tab === "access" ? "is-active" : ""}
          onClick={() => setTab("access")}
          aria-pressed={tab === "access"}
        >
          Accès HTTP ({access.length})
        </button>
      </div>

      {loading ? <Loading label="Lecture du journal…" /> : null}

      {tab === "audit" ? (
        <Card title="Événements d'audit" subtitle="du plus récent au plus ancien">
          {events.length === 0 && !loading ? (
            <p className="muted">Aucun événement enregistré.</p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col">Compte</th>
                    <th scope="col">Événement</th>
                    <th scope="col">Cible</th>
                    <th scope="col">Résultat</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((event) => (
                    <tr key={event.id}>
                      <td className="mono">{formatDate(event.at)}</td>
                      <td>{event.account || "—"}</td>
                      <td>
                        <code>{event.event}</code>
                      </td>
                      <td>{event.target || "—"}</td>
                      <td>
                        <Badge
                          tone={
                            event.outcome === "ok"
                              ? "ok"
                              : event.outcome === "refus"
                                ? "error"
                                : "muted"
                          }
                        >
                          {event.outcome}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : (
        <Card title="Journal d'accès" subtitle="anneau mémoire de 500 requêtes, sans secret">
          {access.length === 0 && !loading ? (
            <p className="muted">Aucune requête enregistrée depuis le démarrage.</p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Heure</th>
                    <th scope="col">Méthode</th>
                    <th scope="col">Chemin</th>
                    <th scope="col">Statut</th>
                    <th scope="col">Compte</th>
                    <th scope="col">Durée</th>
                  </tr>
                </thead>
                <tbody>
                  {access.map((entry, index) => (
                    <tr key={`${entry.at}-${index}`}>
                      <td className="mono">{formatDate(entry.at)}</td>
                      <td>{entry.method}</td>
                      <td className="mono">{entry.path}</td>
                      <td>{entry.status}</td>
                      <td>{entry.account || "—"}</td>
                      <td>{entry.duration_ms} ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </>
  );
}

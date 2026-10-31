import { useCallback, useEffect, useMemo, useState } from "react";
import { api, errorMessage } from "../api";
import type { MemoryItem } from "../types";
import { formatDate, memoryKind } from "../format";
import { Badge, Card, ErrorState, Loading, PageHeader } from "../components/ui";

export function MemoryPage() {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [available, setAvailable] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.memory();
      setAvailable(result.available);
      setItems(result.memories || []);
      setMessage(result.error || null);
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    document.title = "Mémoire — Miles Companion";
    void load();
  }, [load]);

  const counts = useMemo(() => {
    const result: Record<string, number> = {};
    for (const item of items) {
      const key = item.kind || "inconnu";
      result[key] = (result[key] || 0) + 1;
    }
    return result;
  }, [items]);

  const visible = items.filter((item) => kind === "all" || (item.kind || "inconnu") === kind);

  return (
    <>
      <PageHeader
        eyebrow="Mémoire"
        title="Souvenirs explicites"
        description="Cette vue lit la mémoire locale de MILES : nature du souvenir, catégorie, importance et date. Les liens de contradiction et leur confirmation restent en CLI."
        actions={
          <button type="button" className="btn btn-ghost" onClick={() => void load()}>
            <i className="ri-refresh-line" aria-hidden="true" />
            Rafraîchir
          </button>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {!available && message ? (
        <p className="callout callout-warn" role="status">
          <i className="ri-plug-line" aria-hidden="true" />
          {message}
        </p>
      ) : null}
      {loading && items.length === 0 ? <Loading label="Lecture de la mémoire…" /> : null}

      <div className="grid grid-3">
        <Card title="Facts" subtitle="souvenirs qualifiés « fait »">
          <p className="metric-big">{counts["fait"] || 0}</p>
          <p className="muted small">validés par un humain</p>
        </Card>
        <Card title="Hypothèses" subtitle="à confirmer ou infirmer">
          <p className="metric-big">{counts["hypothese"] || 0}</p>
          <p className="muted small">jamais présentées comme des faits</p>
        </Card>
        <Card title="Non qualifiés" subtitle="nature encore inconnue">
          <p className="metric-big">{counts["inconnu"] || 0}</p>
          <p className="muted small">aucune qualification automatique</p>
        </Card>
      </div>

      <div className="row between wrap section-row">
        <h2 className="section-title">Historique</h2>
        <div className="segmented" role="group" aria-label="Filtrer la mémoire">
          {[
            ["all", "Tout"],
            ["fait", "Faits"],
            ["hypothese", "Hypothèses"],
            ["inconnu", "Non qualifiés"],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={kind === value ? "is-active" : ""}
              onClick={() => setKind(value)}
              aria-pressed={kind === value}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {visible.length === 0 && !loading ? (
        <p className="muted">
          Aucun souvenir dans cette vue. La mémoire ne contient que ce qui a été
          explicitement mémorisé.
        </p>
      ) : (
        <ol className="memory-list">
          {visible.map((item) => (
            <li key={String(item.id)} className="memory-item">
              <div className="memory-marker" aria-hidden="true">
                <i className={item.kind === "fait" ? "ri-check-double-line" : "ri-question-line"} />
              </div>
              <div className="memory-body">
                <div className="row between wrap">
                  <Badge tone={item.kind === "fait" ? "ok" : item.kind === "hypothese" ? "warn" : "muted"}>
                    {memoryKind(item.kind)}
                  </Badge>
                  <span className="muted small">
                    {formatDate(item.created_at as string | number | undefined)} ·{" "}
                    {String(item.category || "sans catégorie")} · importance{" "}
                    {String(item.importance ?? "?")}
                  </span>
                </div>
                <p className="memory-content">{String(item.content || "")}</p>
              </div>
            </li>
          ))}
        </ol>
      )}

      <p className="hint-line">
        Les liens <code>duplique</code> / <code>contradit</code> et leur confirmation
        humaine sont disponibles en CLI (<code>/contradictions</code>,{" "}
        <code>/confirmer</code>). Aucune route web ne les expose aujourd'hui : cette
        page ne les invente pas.
      </p>
    </>
  );
}

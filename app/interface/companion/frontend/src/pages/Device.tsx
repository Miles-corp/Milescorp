import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import type { SensorSnapshot } from "../types";
import { formatBytes, formatDate, formatDuration } from "../format";
import { useAuth } from "../auth";
import { Badge, Card, ErrorState, Loading, PageHeader } from "../components/ui";

export function DevicePage() {
  const { me } = useAuth();
  const dev = Boolean(me?.preferences.dev_mode);
  const [snapshot, setSnapshot] = useState<SensorSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setSnapshot(await api.sensors());
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    document.title = "Boîtier — Miles Companion";
    void load();
    const timer = window.setInterval(() => void load(), 10000);
    return () => window.clearInterval(timer);
  }, [load]);

  const box = snapshot?.box;
  const boxCpu = box?.cpu;
  const temps = (box?.temperatures || []).filter((item) => typeof item.celsius === "number");
  const fans = (box?.ventilos || []).filter((item) => typeof item.tr_min === "number");
  /* Le disque a son propre relevé détaillé : une seule source, pas deux. */
  const metrics = (snapshot?.values || []).filter((metric) => metric.id !== "disk");
  const measured = metrics.filter((metric) => metric.available);
  const missing = metrics.filter((metric) => !metric.available);

  return (
    <>
      <PageHeader
        eyebrow="Boîtier"
        title="Capteurs du poste"
        description="Chaque valeur vient d'une lecture locale (/proc, /sys) ou du backend boîtier. Un capteur absent affiche sa raison, jamais une estimation."
        actions={
          <button type="button" className="btn btn-ghost" onClick={() => void load()}>
            <i className="ri-refresh-line" aria-hidden="true" />
            Actualiser
          </button>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {loading && !snapshot ? <Loading label="Lecture des capteurs…" /> : null}

      {snapshot ? (
        <>
          <p className="meta-line">
            <Badge tone={snapshot.mode === "developpeur" ? "warn" : "muted"}>
              {snapshot.mode === "developpeur" ? "mode développeur" : "mode normal"}
            </Badge>
            <span>
              {snapshot.host.name} · {snapshot.host.system} {snapshot.host.release}
            </span>
            <span className="sep">·</span>
            <span>{snapshot.host.cpu_count} cœurs logiques</span>
            <span className="sep">·</span>
            <span>relevé {formatDate(snapshot.measured_at)}</span>
            <span className="sep">·</span>
            <span>processus depuis {formatDuration(snapshot.process_uptime_s)}</span>
          </p>

          <Card
            title="Mesures du poste"
            subtitle={`${measured.length} lues · ${missing.length} sans lecture`}
          >
            <div className="metric-split">
              <section>
                <h3>Valeurs lues</h3>
                {measured.length ? (
                  <div className="metric-grid">
                    {measured.map((metric) => (
                      <article className="metric-card" key={metric.id}>
                        <div className="row between">
                          <p className="metric-label">{metric.label}</p>
                          <span className="dot dot-ok" aria-hidden="true" />
                        </div>
                        <p className="metric-big">
                          {metric.value}
                          <span>{metric.unit}</span>
                        </p>
                        <p className="metric-reason">{metric.source}</p>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="muted">Aucune valeur lisible sur cette plateforme.</p>
                )}
              </section>

              {missing.length ? (
                <section>
                  <h3>
                    Sans lecture <span>· {missing.length} capteurs</span>
                  </h3>
                  <ul className="missing-list">
                    {missing.map((metric) => (
                      <li key={metric.id}>
                        <strong>{metric.label}</strong>
                        <small>{metric.reason}</small>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
            </div>
          </Card>

          <div className="grid grid-2">
            <Card title="Backend boîtier" subtitle="127.0.0.1:8095/box/telemetry">
              {box?.available ? (
                <dl className="kv">
                  <dt>Source</dt>
                  <dd>{box.source || "boxtelemetry"}</dd>
                  <dt>Reçu</dt>
                  <dd>{formatDate(box.received_at || box.horodatage)}</dd>
                  <dt>Charge</dt>
                  <dd>{boxCpu?.charge ? boxCpu.charge.join(" · ") : "non mesurée"}</dd>
                  <dt>Uptime boîtier</dt>
                  <dd>{boxCpu?.uptime_s ? formatDuration(boxCpu.uptime_s) : "inconnu"}</dd>
                  <dt>Températures</dt>
                  <dd>
                    {temps.length
                      ? temps
                          .map(
                            (item) =>
                              `${item.libelle || item.capteur}: ${item.celsius} °C`,
                          )
                          .join(" · ")
                      : "aucune"}
                  </dd>
                  <dt>Ventilateurs</dt>
                  <dd>
                    {fans.length
                      ? fans.map((item) => `${item.capteur}: ${item.tr_min} tr/min`).join(" · ")
                      : "aucun"}
                  </dd>
                  <dt>ESP32</dt>
                  <dd>
                    {box.injection_esp32?.etat === "recu"
                      ? `${box.injection_esp32.temperature ?? "?"} °C · ${box.injection_esp32.humidite ?? "?"} % (${box.injection_esp32.age_s ?? "?"} s)`
                      : box.injection_esp32?.etat || "aucun relevé"}
                  </dd>
                </dl>
              ) : (
                <p className="muted">
                  Backend injoignable : {box?.reason || "aucune réponse"}. Aucune valeur n'est
                  affichée à sa place.
                </p>
              )}
            </Card>

            <Card title="Disque" subtitle={snapshot.storage?.path || "volume du dépôt"}>
              {snapshot.storage ? (
                <>
                  <p className="metric-big">
                    {snapshot.storage.used_percent}
                    <span>%</span>
                  </p>
                  <progress
                    className="progress"
                    value={snapshot.storage.used_percent}
                    max={100}
                    aria-label="Occupation du disque"
                  />
                  <dl className="kv">
                    <dt>Espace libre</dt>
                    <dd>{formatBytes(snapshot.storage.free_bytes)}</dd>
                    <dt>Total</dt>
                    <dd>{formatBytes(snapshot.storage.total_bytes)}</dd>
                    <dt>Utilisé</dt>
                    <dd>{formatBytes(snapshot.storage.used_bytes)}</dd>
                  </dl>
                </>
              ) : (
                <p className="muted">Volume illisible : aucune valeur inventée.</p>
              )}
            </Card>
          </div>

          {dev && snapshot.dev ? (
            <Card title="Détails techniques" subtitle="mode développeur — données brutes locales">
              <pre className="code-block">{JSON.stringify(snapshot.dev, null, 2)}</pre>
            </Card>
          ) : null}
        </>
      ) : null}
    </>
  );
}

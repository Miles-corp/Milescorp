import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import type { Applet, Mission, ProviderStatus, SensorSnapshot } from "../types";
import { missionLabel, missionTone, providerLabel } from "../format";
import { useAuth } from "../auth";
import {
  Badge,
  Card,
  ConfirmAction,
  ErrorState,
  Loading,
  PageHeader,
  SetupGuide,
} from "../components/ui";

const TYPE_LABELS: Record<Applet["type"], string> = {
  system: "primitive système",
  render: "rendu",
  action: "action confirmée",
};

const TYPE_ICONS: Record<Applet["type"], string> = {
  system: "ri-cpu-line",
  render: "ri-layout-masonry-line",
  action: "ri-flashlight-line",
};

export function HomePage() {
  const { me } = useAuth();
  const [status, setStatus] = useState<{
    provider: ProviderStatus;
    miles: Record<string, unknown> | null;
    box: { available: boolean; reason?: string };
  } | null>(null);
  const [sensors, setSensors] = useState<SensorSnapshot | null>(null);
  const [missions, setMissions] = useState<Mission[]>([]);
  const [missionStatus, setMissionStatus] = useState<{
    available: boolean;
    error: string | null;
  } | null>(null);
  const [applets, setApplets] = useState<Applet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [objective, setObjective] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statusValue, sensorValue, missionValue, appletValue] = await Promise.all([
        api.status(),
        api.sensors(),
        api
          .missions()
          .catch(() => ({ available: false, missions: [], error: "Missions illisibles." })),
        api.applets(),
      ]);
      setStatus(statusValue);
      setSensors(sensorValue);
      setMissions(missionValue.missions || []);
      setMissionStatus({
        available: missionValue.available,
        error: missionValue.error ?? null,
      });
      setApplets(appletValue.applets);
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    document.title = "Accueil — Miles Companion";
    void load();
  }, [load]);

  const measured = (sensors?.values || []).filter((metric) => metric.available);
  const missing = (sensors?.values || []).filter((metric) => !metric.available);
  const quick = ["cpu", "ram", "disk", "temperature"]
    .map((id) => measured.find((metric) => metric.id === id))
    .filter((metric): metric is NonNullable<typeof metric> => Boolean(metric));

  const miles = status?.miles as
    | { name?: string; mode?: string; model?: string; availability?: string; error?: string }
    | null
    | undefined;
  const providerReady = Boolean(status?.provider?.configured);
  const boxReady = Boolean(status?.box?.available);
  const needsSetup = !me?.miles_configured || !providerReady;

  return (
    <>
      <PageHeader
        eyebrow="Cockpit"
        title={`Bonjour, ${me?.account.display_name || "utilisateur"}`}
        description="L'état de la box, ses mesures et ses missions. Tout reste local."
        actions={
          <button type="button" className="btn btn-ghost" onClick={() => void load()}>
            <i className="ri-refresh-line" aria-hidden="true" />
            Rafraîchir
          </button>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {loading && !status ? <Loading label="Lecture de l'état réel…" /> : null}

      {/* Rien n'est affirmé avant la lecture : sans relevé, l'état n'est pas « muet ». */}
      {status ? (
        <div className="status-strip" aria-label="État de la box">
          <Link className="status-item" to="/miles">
            <span
              className={`dot ${me?.miles_configured && !miles?.error ? "dot-ok" : "dot-warn"}`}
              aria-hidden="true"
            />
            <span>
              <strong>MILES</strong>
              <small>
                {me?.miles_configured
                  ? miles?.error
                    ? "jeton présent, moteur muet"
                    : `${miles?.model || "modèle inconnu"}`
                  : "non connecté — jeton absent"}
              </small>
            </span>
          </Link>

          <Link className="status-item" to="/ia">
            <span
              className={`dot ${providerReady ? "dot-ok" : "dot-warn"}`}
              aria-hidden="true"
            />
            <span>
              <strong>Fournisseur IA</strong>
              <small>
                {providerReady
                  ? `${providerLabel(status?.provider?.provider)} · ${status?.provider?.model || "modèle par défaut"}`
                  : "aucun accès autorisé"}
              </small>
            </span>
          </Link>

          <Link className="status-item" to="/boitier">
            <span className={`dot ${boxReady ? "dot-ok" : "dot-warn"}`} aria-hidden="true" />
            <span>
              <strong>Boîtier</strong>
              <small>{boxReady ? "backend joignable" : "backend muet"}</small>
            </span>
          </Link>
        </div>
      ) : null}

      {status && needsSetup ? (
        <Card
          title="Mettre la box en service"
          subtitle="ce qui manque aujourd'hui, dans l'ordre"
        >
          <SetupGuide
            steps={[
              {
                title: "Autoriser MILES côté serveur",
                detail:
                  "Le jeton vit dans le .env de la box. Aucun champ de clé n'existe dans ce site.",
                done: Boolean(me?.miles_configured),
                action: me?.miles_configured ? (
                  <Badge tone="ok">fait</Badge>
                ) : (
                  <Link className="btn btn-ghost btn-small" to="/miles">
                    Voir l'état
                  </Link>
                ),
              },
              {
                title: "Autoriser un fournisseur IA",
                detail:
                  "Un bouton d'autorisation par fournisseur : la clé ne passe jamais par le navigateur.",
                done: providerReady,
                action: providerReady ? (
                  <Badge tone="ok">fait</Badge>
                ) : (
                  <Link className="btn btn-ghost btn-small" to="/ia">
                    Choisir
                  </Link>
                ),
              },
              {
                title: "Appairer un appareil (facultatif)",
                detail:
                  "Le QR au dos de la boîte ouvre l'appareil photo et associe le téléphone.",
                done: false,
                action: (
                  <Link className="btn btn-ghost btn-small" to="/appairer">
                    QR code
                  </Link>
                ),
              },
            ]}
          />
        </Card>
      ) : null}

      <Card
        title="Mesures du poste"
        subtitle={
          sensors
            ? `${measured.length} valeurs lues sur ${measured.length + missing.length} · relevé ${new Date(sensors.measured_at).toLocaleTimeString("fr-FR")}`
            : "en attente de relevé"
        }
        actions={
          <Link className="btn btn-ghost btn-small" to="/boitier">
            Tout voir
          </Link>
        }
      >
        {!sensors ? (
          <Loading label="Lecture des mesures…" />
        ) : quick.length ? (
          <div className="metric-strip">
            {quick.map((metric) => (
              <div className="metric-mini" key={metric.id}>
                <p className="metric-label">{metric.label}</p>
                <p className="metric-value">
                  {metric.value}
                  <span>{metric.unit}</span>
                </p>
                <p className="metric-reason">{metric.source}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">
            Aucune mesure disponible sur cette plateforme.{" "}
            <Link to="/boitier">Voir quels capteurs manquent et pourquoi.</Link>
          </p>
        )}
        {missing.length ? (
          <p className="hint-line">
            {missing.length} capteur{missing.length > 1 ? "s" : ""} sans lecture — la raison
            exacte est sur la page Boîtier.
          </p>
        ) : null}
      </Card>

      <div className="grid grid-2">
        <Card
          title="Missions récentes"
          subtitle="l'état vient de MILES, jamais d'une estimation"
          actions={
            <Link className="btn btn-ghost btn-small" to="/missions">
              Tout voir
            </Link>
          }
        >
          {!missionStatus ? (
            <Loading label="Lecture des missions…" />
          ) : !missionStatus.available ? (
            <p className="muted">
              Missions illisibles : {missionStatus.error || "MILES non configuré."}
            </p>
          ) : missions.length === 0 ? (
            <p className="muted">
              Aucune mission pour l'instant.{" "}
              <Link to="/missions">En lancer une depuis la page Missions.</Link>
            </p>
          ) : (
            <ul className="list">
              {missions.slice(0, 4).map((mission) => (
                <li key={mission.mission_id}>
                  <Link to={`/missions/${mission.mission_id}`} className="list-link">
                    <span className="list-main">
                      <strong>{mission.objective}</strong>
                      <small>{new Date(mission.updated_at * 1000).toLocaleString("fr-FR")}</small>
                    </span>
                    <Badge tone={missionTone(mission.state)}>{missionLabel(mission.state)}</Badge>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Lancer une mission" subtitle="action confirmée, exécutée par MILES">
          <form onSubmit={(event) => event.preventDefault()} className="form">
            <label htmlFor="objective">Objectif</label>
            <textarea
              id="objective"
              name="objective"
              rows={3}
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
              placeholder="Ex. : vérifier l'état des tests et signaler les échecs"
              required
            />
            <ConfirmAction
              action="mission.create"
              payload={{ objective }}
              label="Lancer la mission"
              icon="ri-play-circle-line"
              disabled={!objective.trim() || !me?.miles_configured}
              onDone={() => {
                setObjective("");
                void load();
              }}
            />
            {!me?.miles_configured ? (
              <p className="hint-line">
                MILES non connecté : le jeton se définit sur la box, jamais ici.
              </p>
            ) : null}
          </form>
        </Card>
      </div>

      <Card
        title="Applets"
        subtitle="trois types : primitive système, rendu, action confirmée"
      >
        <div className="applet-grid">
          {applets.map((applet) => (
            <article className="applet" key={applet.id}>
              <div className="row between">
                <span className="applet-icon" aria-hidden="true">
                  <i className={TYPE_ICONS[applet.type]} />
                </span>
                <Badge
                  tone={
                    applet.type === "action" ? "warn" : applet.type === "system" ? "accent" : "muted"
                  }
                >
                  {TYPE_LABELS[applet.type]}
                </Badge>
              </div>
              <h3>{applet.title}</h3>
              <p>{applet.description}</p>
              {applet.dev_only ? <p className="muted small">visible en mode développeur</p> : null}
            </article>
          ))}
        </div>
      </Card>
    </>
  );
}

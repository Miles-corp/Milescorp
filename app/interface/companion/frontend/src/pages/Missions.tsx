import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import type { Mission } from "../types";
import { formatDate, missionLabel, missionTone } from "../format";
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

export function MissionsPage() {
  const { me } = useAuth();
  const [missions, setMissions] = useState<Mission[]>([]);
  const [available, setAvailable] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [objective, setObjective] = useState("");
  const [filter, setFilter] = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.missions();
      setAvailable(result.available);
      setMissions(result.missions || []);
      setMessage(result.error || null);
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    document.title = "Missions — Miles Companion";
    void load();
  }, [load]);

  const visible = missions.filter((mission) => {
    if (filter === "active") return !["completed", "failed", "cancelled"].includes(mission.state);
    if (filter === "done") return ["completed", "failed", "cancelled"].includes(mission.state);
    return true;
  });

  return (
    <>
      <PageHeader
        eyebrow="Missions"
        title="Missions et routines"
        description="Chaque mission affiche son état réel, ses étapes et les notes écrites. Les actions passent par une confirmation explicite."
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
      {loading && missions.length === 0 ? <Loading label="Lecture des missions…" /> : null}

      <Card title="Nouvelle mission" subtitle="l'objectif est transmis tel quel à MILES">
        <form onSubmit={(event) => event.preventDefault()} className="form form-inline">
          <label className="sr-only" htmlFor="objective">
            Objectif de la mission
          </label>
          <input
            id="objective"
            value={objective}
            onChange={(event) => setObjective(event.target.value)}
            placeholder="Ex. : analyser les tests en échec sans modifier de fichier"
            required
          />
          <ConfirmAction
            action="mission.create"
            payload={{ objective }}
            label="Lancer"
            icon="ri-play-circle-line"
            disabled={!objective.trim() || !me?.miles_configured}
            onDone={() => {
              setObjective("");
              void load();
            }}
          />
        </form>
        {!me?.miles_configured ? (
          <p className="hint-line">
            MILES non connecté : aucune mission ne peut être lancée. Le jeton reste
            côté serveur.
          </p>
        ) : null}
      </Card>

      <div className="row between wrap section-row">
        <h2 className="section-title">Historique</h2>
        <div className="segmented" role="group" aria-label="Filtrer les missions">
          {[
            ["all", "Toutes"],
            ["active", "En cours"],
            ["done", "Terminées"],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={filter === value ? "is-active" : ""}
              onClick={() => setFilter(value)}
              aria-pressed={filter === value}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {visible.length === 0 && !loading ? (
        <Card
          title={
            missions.length === 0 && filter === "all"
              ? "Première mission"
              : "Aucune mission dans cette vue"
          }
          subtitle={
            missions.length === 0 && filter === "all"
              ? "l'ordre des étapes avant d'écrire un objectif"
              : "change de filtre ou lance une nouvelle mission"
          }
        >
          {missions.length === 0 && filter === "all" ? (
            <SetupGuide
              steps={[
                {
                  title: "Connecter MILES",
                  detail:
                    "Le jeton est défini sur la box (MILES_WEB_AUTH_TOKEN), jamais dans le navigateur.",
                  done: Boolean(me?.miles_configured),
                  action: (
                    <Link className="btn btn-ghost btn-small" to="/miles">
                      État
                    </Link>
                  ),
                },
                {
                  title: "Écrire un objectif vérifiable",
                  detail:
                    "Une intention mesurable, par exemple « analyser les tests en échec sans modifier de fichier ».",
                },
                {
                  title: "Confirmer l'exécution",
                  detail:
                    "Chaque action passe par une confirmation explicite : rien n'est lancé sans un clic.",
                },
              ]}
            />
          ) : (
            <p className="muted">
              {missions.length === 0
                ? `Aucune mission ${filter === "done" ? "terminée" : "en cours"} pour l'instant.`
                : "Aucun résultat pour ce filtre."}{" "}
              <button type="button" className="link-like" onClick={() => setFilter("all")}>
                Afficher toutes les missions
              </button>
            </p>
          )}
        </Card>
      ) : (
        <ul className="mission-list">
          {visible.map((mission) => (
            <li key={mission.mission_id}>
              <Link to={`/missions/${mission.mission_id}`} className="mission-row">
                <div className="mission-main">
                  <p className="mission-objective">{mission.objective}</p>
                  <p className="muted small">
                    {formatDate(mission.created_at)} · {mission.steps.length} étape(s) ·{" "}
                    {mission.budget.tool_calls} appel(s) d'outil
                  </p>
                </div>
                <div className="mission-side">
                  <Badge tone={missionTone(mission.state)}>{missionLabel(mission.state)}</Badge>
                  {mission.pending ? <Badge tone="warn">demande en attente</Badge> : null}
                  <i className="ri-arrow-right-s-line" aria-hidden="true" />
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import type { Mission } from "../types";
import { formatDate, formatDuration, missionLabel, missionTone } from "../format";
import { useAuth } from "../auth";
import {
  Badge,
  Card,
  ConfirmAction,
  ErrorState,
  Loading,
  PageHeader,
} from "../components/ui";

export function MissionDetailPage() {
  const { me } = useAuth();
  const { id = "" } = useParams();
  const [mission, setMission] = useState<Mission | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [answer, setAnswer] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.mission(id);
      if (!result.available || !result.mission) {
        setError(result.error || "Mission indisponible.");
        setMission(null);
      } else {
        setMission(result.mission);
      }
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    document.title = "Mission — Miles Companion";
    void load();
  }, [load]);

  if (loading) return <Loading label="Lecture de la mission…" />;
  if (error) {
    return (
      <>
        <PageHeader eyebrow="Missions" title="Mission indisponible" />
        <ErrorState message={error} onRetry={() => void load()} />
        <p>
          <Link className="btn btn-ghost" to="/missions">
            Retour aux missions
          </Link>
        </p>
      </>
    );
  }
  if (!mission) return null;

  const notes = mission.steps
    .map((step) => ({ ...step, text: [step.note, step.error].filter(Boolean).join("\n") }))
    .filter((step) => step.text);

  return (
    <>
      <PageHeader
        eyebrow="Mission"
        title={mission.objective}
        description={`Créée ${formatDate(mission.created_at)} · mise à jour ${formatDate(mission.updated_at)} · planificateur ${mission.planner || "inconnu"}`}
        actions={
          <div className="row wrap">
            <Badge tone={missionTone(mission.state)}>{missionLabel(mission.state)}</Badge>
            <button type="button" className="btn btn-ghost btn-small" onClick={() => void load()}>
              <i className="ri-refresh-line" aria-hidden="true" />
              Rafraîchir
            </button>
            <Link className="btn btn-ghost btn-small" to="/missions">
              Retour
            </Link>
          </div>
        }
      />

      {mission.pending ? (
        <Card
          title={
            mission.pending.kind === "authorization"
              ? "Autorisation demandée"
              : "Réponse attendue"
          }
          subtitle={
            mission.pending.expires_at
              ? `expire ${formatDate(mission.pending.expires_at)}`
              : undefined
          }
          className="card-attention"
        >
          <p className="pending-question">{mission.pending.question || "Aucune question fournie."}</p>
          {mission.pending.tool_ids.length ? (
            <p className="muted small">Outils demandés : {mission.pending.tool_ids.join(", ")}</p>
          ) : null}
          {mission.pending.allowed_roots.length ? (
            <p className="muted small">
              Racines autorisées : {mission.pending.allowed_roots.join(", ")}
            </p>
          ) : null}

          {mission.pending.kind === "authorization" ? (
            <div className="row wrap action-row">
              <ConfirmAction
                action="mission.authorize"
                payload={{
                  mission_id: mission.mission_id,
                  approval_token: mission.pending.approval_token,
                  approved: true,
                }}
                label="Autoriser"
                icon="ri-shield-check-line"
                onDone={() => void load()}
              />
              <ConfirmAction
                action="mission.authorize"
                payload={{
                  mission_id: mission.mission_id,
                  approval_token: mission.pending.approval_token,
                  approved: false,
                }}
                label="Refuser"
                icon="ri-shield-close-line"
                className="btn btn-danger"
                onDone={() => void load()}
              />
            </div>
          ) : (
            <div className="form">
              <label htmlFor="answer">Votre réponse</label>
              <textarea
                id="answer"
                rows={3}
                value={answer}
                onChange={(event) => setAnswer(event.target.value)}
                placeholder="Réponse transmise à la mission"
              />
              <ConfirmAction
                action="mission.answer"
                payload={{ mission_id: mission.mission_id, answer }}
                label="Envoyer la réponse"
                icon="ri-reply-line"
                disabled={!answer.trim()}
                onDone={() => {
                  setAnswer("");
                  void load();
                }}
              />
            </div>
          )}
        </Card>
      ) : null}

      <div className="grid grid-3">
        <Card title="Budget exécuté" subtitle="bornes globales de la mission">
          <dl className="kv">
            <dt>Durée</dt>
            <dd>{formatDuration(mission.budget.executed_seconds)}</dd>
            <dt>Étapes</dt>
            <dd>{mission.budget.steps_executed}</dd>
            <dt>Appels d'outils</dt>
            <dd>{mission.budget.tool_calls}</dd>
            <dt>Interactions</dt>
            <dd>{mission.budget.interactions}</dd>
            <dt>Arrêt</dt>
            <dd>{mission.budget.stop_reason || "—"}</dd>
          </dl>
        </Card>
        <Card title="Plan" subtitle={mission.planner_note || "aucune note du planificateur"}>
          <ol className="steps">
            {mission.steps.length ? (
              mission.steps.map((step) => (
                <li key={step.step_id}>
                  <div className="row between">
                    <strong>{step.objective}</strong>
                    <Badge
                      tone={
                        step.status === "done"
                          ? "ok"
                          : step.status === "failed"
                            ? "error"
                            : "muted"
                      }
                    >
                      {step.status}
                    </Badge>
                  </div>
                  <p className="muted small">
                    {step.tool || "aucun outil"} · {step.attempts} tentative(s)
                  </p>
                </li>
              ))
            ) : (
              <li className="muted">Aucune étape planifiée.</li>
            )}
          </ol>
        </Card>
        <Card title="Actions" subtitle="toute action exige une confirmation">
          <div className="stack">
            <ConfirmAction
              action="mission.cancel"
              payload={{ mission_id: mission.mission_id }}
              label="Annuler la mission"
              icon="ri-stop-circle-line"
              className="btn btn-danger btn-block"
              disabled={["completed", "failed", "cancelled"].includes(mission.state)}
              onDone={() => void load()}
            />
            <p className="muted small">
              L'annulation est une demande ; l'état réel est relu après l'action.
            </p>
          </div>
        </Card>
      </div>

      <Card title="Éléments écrits par la mission" subtitle="notes et erreurs réellement enregistrées">
        {notes.length ? (
          <div className="stack">
            {notes.map((step) => (
              <details key={step.step_id} className="code-details" open>
                <summary>
                  {step.objective} <span className="muted">({step.status})</span>
                </summary>
                <pre className="code-block">{step.text}</pre>
              </details>
            ))}
          </div>
        ) : (
          <p className="muted">Aucun code ou note enregistré pour cette mission.</p>
        )}
      </Card>

      {mission.report ? (
        <Card title="Compte rendu" subtitle="produit par MILES">
          <pre className="code-block">{mission.report}</pre>
        </Card>
      ) : null}

      {mission.errors.length || mission.unfinished.length ? (
        <div className="grid grid-2">
          <Card title="Erreurs">
            <ul className="plain">
              {mission.errors.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
              {mission.errors.length === 0 ? <li className="muted">aucune</li> : null}
            </ul>
          </Card>
          <Card title="Points non terminés">
            <ul className="plain">
              {mission.unfinished.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
              {mission.unfinished.length === 0 ? <li className="muted">aucun</li> : null}
            </ul>
          </Card>
        </div>
      ) : null}

      {!me?.miles_configured ? (
        <p className="hint-line">
          Les actions nécessitent une session MILES côté serveur ; le jeton n'est
          jamais transmis au navigateur.
        </p>
      ) : null}
    </>
  );
}

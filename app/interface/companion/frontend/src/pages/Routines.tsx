import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api, errorMessage } from "../api";
import type { Routine } from "../types";
import { formatDate } from "../format";
import { useToast } from "../toast";
import {
  Badge,
  Card,
  ConfirmAction,
  EmptyState,
  ErrorState,
  Loading,
  Modal,
  PageHeader,
} from "../components/ui";

export function RoutinesPage() {
  const toast = useToast();
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [objective, setObjective] = useState("");
  const [creating, setCreating] = useState(false);
  const creatingRef = useRef(false);
  const [toDelete, setToDelete] = useState<Routine | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.routines();
      setRoutines(result.routines);
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    document.title = "Routines — Miles Companion";
    void load();
  }, [load]);

  async function create(event: FormEvent) {
    event.preventDefault();
    // Un double clic ne doit pas créer deux routines identiques : l'état
    // React n'est pas encore à jour entre deux clics de la même frame.
    if (creatingRef.current) return;
    creatingRef.current = true;
    setCreating(true);
    try {
      await api.createRoutine(name.trim(), objective.trim());
      toast.show("Routine enregistrée.", "ok");
      setName("");
      setObjective("");
      await load();
    } catch (exc) {
      toast.show(errorMessage(exc), "error");
    } finally {
      creatingRef.current = false;
      setCreating(false);
    }
  }

  async function remove() {
    if (!toDelete) return;
    try {
      await api.deleteRoutine(toDelete.id);
      toast.show("Routine supprimée.", "ok");
      setToDelete(null);
      await load();
    } catch (exc) {
      toast.show(errorMessage(exc), "error");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Routines"
        title="Actions récurrentes"
        description="Une routine est un modèle de mission : elle ne s'exécute jamais toute seule. Chaque lancement crée une mission réelle, avec confirmation."
      />

      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {loading ? <Loading label="Lecture des routines…" /> : null}

      <Card title="Nouvelle routine" subtitle="nom lisible + objectif transmis à MILES">
        <form onSubmit={create} className="form">
          <label htmlFor="routine-name">Nom</label>
          <input
            id="routine-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Ex. : revue quotidienne des tests"
            required
          />
          <label htmlFor="routine-objective">Objectif</label>
          <textarea
            id="routine-objective"
            rows={3}
            value={objective}
            onChange={(event) => setObjective(event.target.value)}
            placeholder="Ex. : exécuter la suite de tests et lister les échecs sans modifier de fichier"
            required
          />
          <button type="submit" className="btn btn-primary" disabled={creating}>
            <i className={creating ? "ri-loader-3-line spin" : "ri-add-line"} aria-hidden="true" />
            {creating ? "Enregistrement…" : "Enregistrer la routine"}
          </button>
        </form>
      </Card>

      {routines.length === 0 && !loading ? (
        <EmptyState icon="ri-repeat-2-line" title="Aucune routine">
          Créez un modèle ci-dessus. Il ne sera lancé que sur action explicite.
        </EmptyState>
      ) : (
        <ul className="routine-list">
          {routines.map((routine) => (
            <li key={routine.id} className="routine-row">
              <div className="routine-main">
                <div className="row wrap">
                  <h3>{routine.name}</h3>
                  <Badge tone={routine.enabled ? "ok" : "muted"}>
                    {routine.enabled ? "active" : "désactivée"}
                  </Badge>
                </div>
                <p className="muted">{routine.objective}</p>
                <p className="muted small">
                  Dernier lancement :{" "}
                  {routine.last_run_at ? formatDate(routine.last_run_at) : "jamais"}
                </p>
              </div>
              <div className="routine-actions">
                <ConfirmAction
                  action="routine.run"
                  payload={{ routine_id: routine.id }}
                  label="Lancer"
                  icon="ri-play-line"
                  onDone={() => void load()}
                />
                <button
                  type="button"
                  className="btn btn-ghost btn-small"
                  onClick={() => setToDelete(routine)}
                >
                  <i className="ri-delete-bin-line" aria-hidden="true" />
                  Supprimer
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Modal
        open={toDelete !== null}
        title="Supprimer la routine"
        onClose={() => setToDelete(null)}
      >
        <p className="modal-text">
          Supprimer « {toDelete?.name} » ? Les missions déjà lancées ne sont pas
          modifiées.
        </p>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={() => setToDelete(null)}>
            Annuler
          </button>
          <button type="button" className="btn btn-danger" onClick={() => void remove()}>
            Supprimer
          </button>
        </div>
      </Modal>
    </>
  );
}

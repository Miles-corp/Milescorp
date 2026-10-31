import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import type { Account } from "../types";
import { formatDate } from "../format";
import { useAuth } from "../auth";
import { useToast } from "../toast";
import {
  Badge,
  Card,
  ErrorState,
  Loading,
  Modal,
  PageHeader,
} from "../components/ui";
import { InstallAppCard } from "../components/InstallApp";

export function SettingsPage() {
  const { me, setDevMode, logout } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const admin = me?.account.role === "admin";

  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loadingAccounts, setLoadingAccounts] = useState(false);
  const [accountsError, setAccountsError] = useState<string | null>(null);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [changing, setChanging] = useState(false);

  const [newUsername, setNewUsername] = useState("");
  const [newName, setNewName] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("user");
  const [creating, setCreating] = useState(false);
  const [toDelete, setToDelete] = useState<Account | null>(null);

  const loadAccounts = useCallback(async () => {
    if (!admin) return;
    setLoadingAccounts(true);
    setAccountsError(null);
    try {
      const result = await api.accounts();
      setAccounts(result.accounts);
    } catch (exc) {
      setAccountsError(errorMessage(exc));
    } finally {
      setLoadingAccounts(false);
    }
  }, [admin]);

  useEffect(() => {
    document.title = "Réglages — Miles Companion";
    void loadAccounts();
  }, [loadAccounts]);

  async function toggleDev() {
    if (!me) return;
    try {
      await setDevMode(!me.preferences.dev_mode);
      toast.show(
        me.preferences.dev_mode ? "Mode développeur désactivé." : "Mode développeur activé.",
        "ok",
      );
    } catch (exc) {
      toast.show(errorMessage(exc), "error");
    }
  }

  async function changePassword(event: FormEvent) {
    event.preventDefault();
    if (next !== confirm) {
      toast.show("Les deux saisies du nouveau mot de passe diffèrent.", "error");
      return;
    }
    setChanging(true);
    try {
      await api.changePassword(current, next);
      toast.show("Mot de passe changé. Reconnectez-vous.", "ok");
      await logout();
      navigate("/connexion", { replace: true });
    } catch (exc) {
      toast.show(errorMessage(exc), "error");
    } finally {
      setChanging(false);
    }
  }

  async function createAccount(event: FormEvent) {
    event.preventDefault();
    setCreating(true);
    try {
      await api.createAccount({
        username: newUsername.trim(),
        password: newPassword,
        role: newRole,
        display_name: newName.trim(),
      });
      toast.show("Compte créé.", "ok");
      setNewUsername("");
      setNewName("");
      setNewPassword("");
      setNewRole("user");
      await loadAccounts();
    } catch (exc) {
      toast.show(errorMessage(exc), "error");
    } finally {
      setCreating(false);
    }
  }

  async function changeRole(account: Account, role: string) {
    try {
      await api.updateAccount(account.id, { role });
      toast.show(`Rôle de ${account.username} : ${role}.`, "ok");
      await loadAccounts();
    } catch (exc) {
      toast.show(errorMessage(exc), "error");
    }
  }

  async function toggleDisabled(account: Account) {
    try {
      await api.updateAccount(account.id, { disabled: !account.disabled });
      toast.show(account.disabled ? "Compte réactivé." : "Compte désactivé.", "ok");
      await loadAccounts();
    } catch (exc) {
      toast.show(errorMessage(exc), "error");
    }
  }

  async function removeAccount() {
    if (!toDelete) return;
    try {
      await api.deleteAccount(toDelete.id);
      toast.show("Compte supprimé.", "ok");
      setToDelete(null);
      await loadAccounts();
    } catch (exc) {
      toast.show(errorMessage(exc), "error");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Réglages"
        title="Compte et sécurité"
        description="Comptes locaux, sessions révocables, aucun e-mail sortant. Les deux administrateurs maximum sont garantis par une transaction SQLite."
      />

      <div className="grid grid-2">
        <Card title="Votre compte" subtitle="session en cours">
          <dl className="kv">
            <dt>Identifiant</dt>
            <dd>{me?.account.username}</dd>
            <dt>Nom affiché</dt>
            <dd>{me?.account.display_name}</dd>
            <dt>Rôle</dt>
            <dd>{me?.account.role === "admin" ? "administrateur" : "utilisateur"}</dd>
            <dt>Dernière connexion</dt>
            <dd>{formatDate(me?.account.last_login_at ?? null)}</dd>
          </dl>
          <div className="row between wrap setting-row">
            <div>
              <strong>Mode développeur</strong>
              <p className="muted small">
                Affiche les détails techniques, le journal d'audit et le journal
                d'accès. Chaque consultation est journalisée.
              </p>
            </div>
            <button
              type="button"
              className={me?.preferences.dev_mode ? "btn btn-danger" : "btn btn-ghost"}
              onClick={() => void toggleDev()}
              aria-pressed={Boolean(me?.preferences.dev_mode)}
            >
              <i className="ri-terminal-box-line" aria-hidden="true" />
              {me?.preferences.dev_mode ? "Désactiver" : "Activer"}
            </button>
          </div>
          <p className="hint-line">
            <button
              type="button"
              className="btn btn-ghost btn-small"
              onClick={async () => {
                await logout();
                navigate("/connexion", { replace: true });
              }}
            >
              <i className="ri-logout-box-r-line" aria-hidden="true" />
              Fermer la session
            </button>
          </p>
        </Card>

        <Card title="Changer le mot de passe" subtitle="12 caractères minimum">
          <form onSubmit={changePassword} className="form">
            <label htmlFor="current-password">Mot de passe actuel</label>
            <input
              id="current-password"
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
              required
            />
            <label htmlFor="new-password">Nouveau mot de passe</label>
            <input
              id="new-password"
              type="password"
              autoComplete="new-password"
              value={next}
              onChange={(event) => setNext(event.target.value)}
              minLength={12}
              required
            />
            <label htmlFor="confirm-password">Confirmer</label>
            <input
              id="confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              minLength={12}
              required
            />
            <button type="submit" className="btn btn-primary" disabled={changing}>
              <i className={changing ? "ri-loader-3-line spin" : "ri-lock-line"} aria-hidden="true" />
              {changing ? "Changement…" : "Changer le mot de passe"}
            </button>
          </form>
          <p className="hint-line">
            Le changement révoque toutes les sessions, y compris celle-ci : vous
            serez reconnecté.
          </p>
        </Card>
      </div>

      <InstallAppCard />

      {admin ? (
        <Card
          title="Comptes"
          subtitle="deux administrateurs maximum · les autres sont utilisateurs"
          actions={
            <button type="button" className="btn btn-ghost btn-small" onClick={() => void loadAccounts()}>
              <i className="ri-refresh-line" aria-hidden="true" />
              Rafraîchir
            </button>
          }
        >
          {accountsError ? <ErrorState message={accountsError} /> : null}
          {loadingAccounts ? <Loading label="Lecture des comptes…" /> : null}

          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Identifiant</th>
                  <th scope="col">Nom</th>
                  <th scope="col">Rôle</th>
                  <th scope="col">État</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((account) => (
                  <tr key={account.id}>
                    <td>
                      <strong>{account.username}</strong>
                      {account.id === me?.account.id ? <span className="muted"> (vous)</span> : null}
                    </td>
                    <td>{account.display_name}</td>
                    <td>
                      <select
                        value={account.role}
                        onChange={(event) => void changeRole(account, event.target.value)}
                        aria-label={`Rôle de ${account.username}`}
                      >
                        <option value="user">utilisateur</option>
                        <option value="admin">administrateur</option>
                      </select>
                    </td>
                    <td>
                      <Badge tone={account.disabled ? "muted" : "ok"}>
                        {account.disabled ? "désactivé" : "actif"}
                      </Badge>
                    </td>
                    <td>
                      <div className="row wrap">
                        <button
                          type="button"
                          className="btn btn-ghost btn-small"
                          onClick={() => void toggleDisabled(account)}
                          disabled={account.id === me?.account.id}
                        >
                          {account.disabled ? "Réactiver" : "Désactiver"}
                        </button>
                        <button
                          type="button"
                          className="btn btn-ghost btn-small"
                          onClick={() => setToDelete(account)}
                          disabled={account.id === me?.account.id}
                        >
                          Supprimer
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3 className="subtitle">Créer un compte</h3>
          <form onSubmit={createAccount} className="form form-grid">
            <div>
              <label htmlFor="new-username">Identifiant</label>
              <input
                id="new-username"
                value={newUsername}
                onChange={(event) => setNewUsername(event.target.value)}
                pattern="[a-z0-9][a-z0-9_.\-]{2,31}"
                title="3 à 32 caractères : minuscules, chiffres, point, tiret, souligné"
                required
              />
            </div>
            <div>
              <label htmlFor="new-name">Nom affiché</label>
              <input
                id="new-name"
                value={newName}
                onChange={(event) => setNewName(event.target.value)}
                placeholder="facultatif"
              />
            </div>
            <div>
              <label htmlFor="new-account-password">Mot de passe</label>
              <input
                id="new-account-password"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                minLength={12}
                required
              />
            </div>
            <div>
              <label htmlFor="new-role">Rôle</label>
              <select id="new-role" value={newRole} onChange={(event) => setNewRole(event.target.value)}>
                <option value="user">utilisateur</option>
                <option value="admin">administrateur</option>
              </select>
            </div>
            <div className="form-submit">
              <button type="submit" className="btn btn-primary" disabled={creating}>
                <i className={creating ? "ri-loader-3-line spin" : "ri-user-add-line"} aria-hidden="true" />
                {creating ? "Création…" : "Créer le compte"}
              </button>
            </div>
          </form>
          <p className="hint-line">
            Aucun e-mail n'est envoyé : le mot de passe initial est communiqué par
            l'administrateur. Les comptes désactivés perdent immédiatement leurs
            sessions.
          </p>
        </Card>
      ) : null}

      <Card title="Sécurité et données" subtitle="ce que le site stocke réellement">
        <ul className="plain">
          <li>
            Base locale : <code>data/companion.db</code> (comptes, sessions hachées,
            préférences, audit, routines).
          </li>
          <li>Aucune clé de fournisseur dans cette base : elles vivent dans le <code>.env</code> de la box.</li>
          <li>Aucune ressource distante, aucun analytics, aucun cookie tiers.</li>
          <li>Le jeton de session est <code>HttpOnly</code> ; seul son hachage est stocké.</li>
          <li>Le jeton MILES reste côté serveur et n'atteint jamais le navigateur.</li>
        </ul>
      </Card>

      <Modal open={toDelete !== null} title="Supprimer le compte" onClose={() => setToDelete(null)}>
        <p className="modal-text">
          Supprimer « {toDelete?.username} » ? Ses sessions et préférences seront
          supprimées. Le journal d'audit conserve les événements expurgés.
        </p>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={() => setToDelete(null)}>
            Annuler
          </button>
          <button type="button" className="btn btn-danger" onClick={() => void removeAccount()}>
            Supprimer
          </button>
        </div>
      </Modal>
    </>
  );
}

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { errorMessage } from "../api";

export function LoginPage() {
  const { me, login, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);

  useEffect(() => {
    document.title = "Connexion — Miles Companion";
  }, []);

  if (!loading && me) {
    const from = (location.state as { from?: string } | null)?.from || "/";
    return <Navigate to={from} replace />;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    // Un double clic ne doit pas ouvrir deux sessions : l'état React n'est
    // pas encore à jour entre deux clics de la même frame.
    if (busyRef.current) return;
    busyRef.current = true;
    setError(null);
    setBusy(true);
    try {
      await login(username.trim(), password);
      const from = (location.state as { from?: string } | null)?.from || "/";
      navigate(from, { replace: true });
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <div className="brand brand-large">
          <span className="brand-mark" aria-hidden="true">
            <i className="ri-focus-3-line" />
          </span>
          <span>
            <strong>Miles Companion</strong>
            <small>cockpit local de la Miles Box</small>
          </span>
        </div>

        <h1 id="login-title">Ouvrir la session</h1>
        <p className="page-lead">
          Les comptes sont créés par un administrateur sur la box. Aucun compte
          public, aucun envoi d'e-mail, aucune ressource distante.
        </p>

        <form onSubmit={submit} className="form">
          <label htmlFor="username">Identifiant</label>
          <input
            id="username"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
            minLength={3}
            autoFocus
          />

          <label htmlFor="password">Mot de passe</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            minLength={12}
          />

          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}

          <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
            <i className={busy ? "ri-loader-3-line spin" : "ri-login-box-line"} aria-hidden="true" />
            {busy ? "Connexion…" : "Se connecter"}
          </button>
        </form>

        <p className="login-discover">
          <Link to="/presentation">Découvrir Miles Companion</Link>
        </p>

        <p className="login-foot">
          Première installation :{" "}
          <code>python -m app.interface.companion.auth add &lt;identifiant&gt; --role admin</code>
        </p>
      </section>
      <p className="login-note">
        Écoute locale uniquement · <code>127.0.0.1</code> · aucune requête sortante
      </p>
    </main>
  );
}

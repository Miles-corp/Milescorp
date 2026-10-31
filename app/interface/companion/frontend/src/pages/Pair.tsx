import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";

type Status = { state: "idle" | "busy" | "done" | "error"; message?: string; box?: string };

function hashToken(): string {
  return new URLSearchParams(window.location.hash.replace(/^#/, "")).get("t") || "";
}

export function PairPage() {
  const [token] = useState(hashToken);
  const [label, setLabel] = useState("");
  const [status, setStatus] = useState<Status>({ state: "idle" });

  useEffect(() => {
    document.title = "Appairer un appareil — Miles Companion";
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setStatus({ state: "busy" });
    try {
      const result = await api.pair(token, label.trim());
      setStatus({
        state: "done",
        box: result.box.name,
        message: result.device.label,
      });
    } catch (exc) {
      setStatus({ state: "error", message: errorMessage(exc) });
    }
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <p className="eyebrow">Appairage</p>
        <h1>{status.state === "done" ? "Appareil associé" : "Associer cet appareil"}</h1>

        {!token ? (
          <>
            <p className="page-lead">
              Ce lien ne contient aucun code d'appairage. Scannez le QR code collé au
              dos du boîtier avec l'appareil photo du téléphone.
            </p>
            <Link className="btn btn-primary" to="/">
              Revenir à l'accueil
            </Link>
          </>
        ) : status.state === "done" ? (
          <>
            <p className="page-lead">
              Cet appareil est désormais associé à <strong>{status.box}</strong>
              {status.message ? ` (${status.message})` : ""}.
            </p>
            <p className="muted small">
              L'association ne donne aucun accès : la connexion à l'interface reste
              protégée par votre identifiant et votre mot de passe.
            </p>
            <Link className="btn btn-primary" to="/connexion">
              Se connecter
            </Link>
          </>
        ) : (
          <form className="form" onSubmit={submit}>
            <p className="page-lead">
              Le QR code prouve que vous avez le boîtier en main. Donnez un nom à cet
              appareil pour le reconnaître dans la liste des appareils associés.
            </p>
            <label htmlFor="device-label">Nom de l'appareil (facultatif)</label>
            <input
              id="device-label"
              name="label"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="Ex. : Téléphone du salon"
              maxLength={40}
              autoComplete="off"
            />
            {status.state === "error" ? (
              <p className="form-error" role="alert">
                {status.message}
              </p>
            ) : null}
            <button type="submit" className="btn btn-primary" disabled={status.state === "busy"}>
              <i
                className={status.state === "busy" ? "ri-loader-3-line spin" : "ri-link"}
                aria-hidden="true"
              />
              {status.state === "busy" ? "Association…" : "Associer cet appareil"}
            </button>
          </form>
        )}

        <p className="muted small">
          Jeton lu dans le lien, jamais envoyé dans l'URL au serveur. Un appareil
          associé peut être retiré à tout moment depuis la page Découvrir.
        </p>
      </section>
    </main>
  );
}

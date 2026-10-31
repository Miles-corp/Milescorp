import { useState } from "react";
import { promptInstall, useInstallState } from "../pwa";
import { useToast } from "../toast";
import { Badge, Card } from "./ui";

/**
 * Installation du cockpit depuis le navigateur : manifeste + service worker
 * locaux, aucun magasin d'applications, aucun téléchargement distant.
 */
export function InstallAppCard() {
  const toast = useToast();
  const { installed, canInstall, ios } = useInstallState();
  const [busy, setBusy] = useState(false);

  async function install() {
    setBusy(true);
    try {
      const outcome = await promptInstall();
      if (outcome === "accepted") {
        toast.show("Installation lancée : l'application s'ouvre dans sa propre fenêtre.", "ok");
      } else if (outcome === "dismissed") {
        toast.show("Installation annulée. Vous pourrez la relancer depuis les Réglages.", "info");
      } else {
        toast.show("Le navigateur ne propose pas l'installation pour l'instant.", "info");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Application"
      subtitle="Installer le cockpit sur cet appareil, sans magasin d'applications"
      actions={
        installed ? (
          <Badge tone="ok">installée</Badge>
        ) : canInstall ? (
          <Badge tone="accent">disponible</Badge>
        ) : null
      }
    >
      {installed ? (
        <p className="muted">
          Le cockpit s'ouvre comme une application : fenêtre dédiée, icône sur le
          bureau ou l'écran d'accueil. Les pages déjà visitées restent lisibles
          hors ligne ; les mesures et les missions demandent toujours la box.
        </p>
      ) : canInstall ? (
        <>
          <p className="muted">
            Le navigateur installe le site tel qu'il est servi par la box : aucun
            paquet à télécharger, aucune boutique. Le service worker garde la coque
            et les ressources locales pour un démarrage hors ligne.
          </p>
          <div className="install-actions">
            <button type="button" className="btn btn-primary" onClick={install} disabled={busy}>
              <i className={busy ? "ri-loader-3-line spin" : "ri-download-2-line"} aria-hidden="true" />
              {busy ? "Installation…" : "Installer l'application"}
            </button>
          </div>
        </>
      ) : ios ? (
        <>
          <p className="muted">
            Sur iPhone et iPad, l'installation passe par Safari — c'est le seul
            navigateur autorisé à ajouter une application à l'écran d'accueil.
          </p>
          <ol className="install-steps">
            <li>Touchez <strong>Partager</strong> dans la barre de Safari.</li>
            <li>Choisissez <strong>Sur l'écran d'accueil</strong>, puis <strong>Ajouter</strong>.</li>
            <li>Ouvrez l'icône « Miles » : le cockpit s'affiche en plein écran.</li>
          </ol>
        </>
      ) : (
        <>
          <p className="muted">
            Ce navigateur ne propose pas l'installation directe. Sur ordinateur,
            ouvrez le site dans <strong>Chrome</strong> ou <strong>Edge</strong> puis
            utilisez le menu <strong>⋮ → Installer Miles Companion</strong>. Sur
            Android, même chemin depuis Chrome.
          </p>
          <p className="muted">
            L'installation n'est possible qu'en <code>localhost</code> ou en HTTPS :
            sur une adresse <code>http://192.168…</code> le navigateur la refuse tant
            que le certificat local n'est pas en place.
          </p>
        </>
      )}
    </Card>
  );
}

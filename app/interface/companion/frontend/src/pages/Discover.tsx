import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import type { Device } from "../types";
import { formatDate } from "../format";
import { useAuth } from "../auth";
import { useToast } from "../toast";
import { pairingToken } from "../pairing";
import { QrScanner } from "../components/QrScanner";
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  Loading,
  PageHeader,
} from "../components/ui";

export function DiscoverPage() {
  const { me, refresh } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const admin = me?.account.role === "admin";

  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [link, setLink] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!admin) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.devices();
      setDevices(result.devices);
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setLoading(false);
    }
  }, [admin]);

  useEffect(() => {
    document.title = "Appareils — Miles Companion";
    void refresh();
  }, [refresh]);

  useEffect(() => {
    void load();
  }, [load]);

  function openPairing(token: string) {
    setScanError(null);
    navigate(`/appairer#t=${token}`);
  }

  function handleScan(value: string) {
    const token = pairingToken(value);
    if (!token) {
      setScanError("Ce QR code n'est pas un lien d'appairage Miles Companion.");
      return;
    }
    openPairing(token);
  }

  function submitLink(event: FormEvent) {
    event.preventDefault();
    const token = pairingToken(link);
    if (!token) {
      setLinkError("Lien invalide : il doit commencer par http://…/appairer#t=…");
      return;
    }
    setLinkError(null);
    openPairing(token);
  }

  async function revoke(device: Device) {
    if (!window.confirm(`Retirer l'appareil « ${device.label} » ?`)) return;
    setBusy(device.id);
    try {
      await api.revokeDevice(device.id);
      setDevices((current) => current.filter((item) => item.id !== device.id));
      toast.show(`${device.label} retiré.`, "ok");
      await refresh();
    } catch (exc) {
      toast.show(errorMessage(exc), "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Appairage"
        title="Connecter une box"
        description="Scannez le QR code collé au dos du boîtier : l'appareil est associé à la box sans saisir d'adresse. Aucune donnée ne quitte le réseau local."
      />

      <div className="grid grid-2">
        <Card
          title="Scanner le QR code"
          subtitle="au dos du boîtier · caméra ou appareil photo du téléphone"
        >
          <QrScanner onResult={handleScan} />
          {scanError ? (
            <p className="form-error" role="alert">
              {scanError}
            </p>
          ) : null}
          <form className="form" onSubmit={submitLink}>
            <label htmlFor="pair-link">Ou coller le lien du QR code</label>
            <input
              id="pair-link"
              name="link"
              value={link}
              onChange={(event) => setLink(event.target.value)}
              placeholder="http://192.168.1.42:8787/appairer#t=…"
              autoComplete="off"
              spellCheck={false}
            />
            {linkError ? (
              <p className="form-error" role="alert">
                {linkError}
              </p>
            ) : null}
            <button type="submit" className="btn btn-ghost" disabled={!link.trim()}>
              <i className="ri-link" aria-hidden="true" />
              Associer
            </button>
          </form>
          <p className="hint-line">
            Le scanner intégré fonctionne en HTTPS ou sur <code>localhost</code>. Sur le
            réseau local en <code>http</code>, le navigateur interdit la caméra : scannez
            alors avec l'appareil photo du téléphone, qui ouvrira directement le lien
            d'appairage.
          </p>
        </Card>

        <Card title="Cet appareil" subtitle="association locale, révocable depuis la box">
          {me?.device ? (
            <>
              <p className="value">{me.device.label}</p>
              <p className="muted small">
                associé le {formatDate(me.device.paired_at)} · dernière activité{" "}
                {formatDate(me.device.last_seen_at)}
              </p>
              <Badge tone="ok">appareil associé</Badge>
            </>
          ) : (
            <>
              <p className="value value-muted">non associé</p>
              <p className="muted small">
                Ce navigateur n'a pas encore présenté de QR code valide.
              </p>
              <Badge tone="muted">aucune association</Badge>
            </>
          )}
          <p className="hint-line">
            L'association identifie l'appareil auprès de <strong>{me?.box_name || "la box"}</strong> ;
            elle ne remplace jamais la connexion au compte.
          </p>
        </Card>
      </div>

      {admin ? (
        <Card
          title="Appareils associés"
          subtitle="un appareil retiré devra rescaner le QR code"
          actions={
            <button type="button" className="btn btn-ghost btn-small" onClick={() => void load()}>
              <i className="ri-refresh-line" aria-hidden="true" />
              Rafraîchir
            </button>
          }
        >
          {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
          {loading && devices.length === 0 ? <Loading label="Lecture des appareils…" /> : null}
          {devices.length === 0 && !loading ? (
            <EmptyState icon="ri-smartphone-line" title="Aucun appareil associé">
              <p>Scannez le QR du boîtier depuis un téléphone pour le voir apparaître ici.</p>
            </EmptyState>
          ) : (
            <div className="device-grid">
              {devices.map((device) => (
                <article className="device-card" key={device.id}>
                  <div className="row between">
                    <h3>{device.label}</h3>
                    <Badge tone="accent">associé</Badge>
                  </div>
                  <p className="muted small">
                    depuis le {formatDate(device.paired_at)} · vu {formatDate(device.last_seen_at)}
                  </p>
                  <div className="row wrap device-actions">
                    <button
                      type="button"
                      className="btn btn-ghost btn-small btn-danger"
                      onClick={() => void revoke(device)}
                      disabled={busy !== null}
                    >
                      <i className="ri-delete-bin-line" aria-hidden="true" />
                      Retirer
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </Card>
      ) : null}
    </>
  );
}

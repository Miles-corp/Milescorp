import { useEffect, useRef, useState } from "react";

type DetectedBarcode = { rawValue: string };
type BarcodeDetectorLike = { detect: (source: CanvasImageSource) => Promise<DetectedBarcode[]> };
type BarcodeDetectorCtor = new (options?: { formats?: string[] }) => BarcodeDetectorLike;

/**
 * Scanner de QR code par caméra. Le décodage utilise l'API native
 * `BarcodeDetector` : aucune bibliothèque et aucune ressource distante.
 * La caméra n'est accessible qu'en HTTPS ou sur localhost (règle du
 * navigateur) ; l'appelant affiche donc aussi le collage du lien.
 */
export function QrScanner({ onResult }: { onResult: (value: string) => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const stopRef = useRef<(() => void) | null>(null);

  const [active, setActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    return () => stopRef.current?.();
  }, []);

  async function start() {
    setError(null);
    const ctor = (window as unknown as { BarcodeDetector?: BarcodeDetectorCtor }).BarcodeDetector;
    if (!ctor) {
      setError(
        "Ce navigateur ne décode pas les QR codes. Utilisez l'appareil photo du téléphone, " +
          "ou collez le lien affiché sous le QR.",
      );
      return;
    }
    if (!window.isSecureContext) {
      setError(
        "La caméra du navigateur exige HTTPS ou localhost. Sur le réseau local en http, " +
          "scannez le QR avec l'appareil photo du téléphone : il ouvrira le lien d'appairage.",
      );
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      });
    } catch {
      setError("Accès caméra refusé ou indisponible sur cet appareil.");
      return;
    }
    const video = videoRef.current;
    if (!video) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    video.srcObject = stream;
    try {
      await video.play();
    } catch {
      /* l'élément démarre quand même au premier rendu */
    }
    setActive(true);

    const detector = new ctor({ formats: ["qr_code"] });
    let running = true;
    const stop = () => {
      running = false;
      stream.getTracks().forEach((track) => track.stop());
      if (videoRef.current) videoRef.current.srcObject = null;
      setActive(false);
    };
    stopRef.current = stop;

    const tick = async () => {
      if (!running) return;
      try {
        const found = await detector.detect(video);
        if (found.length > 0 && found[0].rawValue) {
          stop();
          onResult(found[0].rawValue);
          return;
        }
      } catch {
        /* image pas encore prête : on réessaie */
      }
      if (running) window.setTimeout(() => void tick(), 250);
    };
    window.setTimeout(() => void tick(), 300);
  }

  return (
    <div className="scanner">
      <video
        ref={videoRef}
        className={active ? "scan-video" : "scan-video scan-video-off"}
        muted
        playsInline
        aria-label="Flux caméra"
      />
      <div className="row wrap">
        {active ? (
          <button type="button" className="btn btn-ghost" onClick={() => stopRef.current?.()}>
            <i className="ri-close-line" aria-hidden="true" />
            Arrêter la caméra
          </button>
        ) : (
          <button type="button" className="btn btn-primary" onClick={() => void start()}>
            <i className="ri-qr-scan-2-line" aria-hidden="true" />
            Ouvrir la caméra
          </button>
        )}
      </div>
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

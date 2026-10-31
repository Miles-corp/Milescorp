import { useCallback, useEffect, useRef, useState } from "react";

const FILM = "/assets/c8cede45891b351eefe713455640c3a7.mp4";
const POSTER = "/assets/img/poster.jpg";
const STILL = "/assets/img/rendu-1.jpg";
const SEEN_KEY = "miles.companion.boot";
const FADE_MS = 650;
const SAFETY_MS = 21000;
const GATE_MS = 10000;

type Gate = "reduced" | "blocked" | null;

function shouldPlay(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.sessionStorage.getItem(SEEN_KEY) !== "1";
  } catch {
    return false;
  }
}

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Film de lancement de la Miles Box, servi par la box elle-même : une seule
 * lecture par session, toujours interruptible. Si la lecture automatique n'est
 * pas possible — mouvement réduit ou refus du navigateur — l'écran devient une
 * affiche fixe (rendu du boîtier) avec un bouton de lancement explicite, et se
 * referme seul.
 */
export function BootFilm() {
  const reduced = prefersReducedMotion();
  const [visible, setVisible] = useState(shouldPlay);
  const [leaving, setLeaving] = useState(false);
  const [progress, setProgress] = useState(0);
  const [gate, setGate] = useState<Gate>(reduced ? "reduced" : null);
  const [playing, setPlaying] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const boot = useRef<HTMLDivElement>(null);
  const launch = useRef<HTMLButtonElement>(null);
  const skip = useRef<HTMLButtonElement>(null);
  const closing = useRef(false);

  const finish = useCallback(() => {
    if (closing.current) return;
    closing.current = true;
    try {
      window.sessionStorage.setItem(SEEN_KEY, "1");
    } catch {
      /* stockage refusé : le film se rejouera à la prochaine ouverture */
    }
    setLeaving(true);
    window.setTimeout(() => setVisible(false), FADE_MS);
  }, []);

  const start = useCallback(() => {
    const element = video.current;
    if (!element) return;
    const attempt = element.play();
    if (attempt && typeof attempt.then === "function") {
      attempt
        .then(() => setGate(null))
        // L'affiche ne parle de film arrêté que si le film ne tourne pas : si
        // l'autoplay natif a démarré entre-temps, on ne couvre pas la lecture.
        .catch(() => setGate(element.paused ? "blocked" : null));
    }
  }, []);

  useEffect(() => {
    if (!visible || gate) return;
    const element = video.current;
    if (!element) return;

    start();

    const onFrame = () => {
      const duration =
        Number.isFinite(element.duration) && element.duration > 0 ? element.duration : 14;
      const value = Math.min(100, Math.max(0, Math.round((element.currentTime / duration) * 100)));
      setProgress((current) => (current === value ? current : value));
      setPlaying(!element.paused && !element.ended);
      if (element.ended || (duration > 0 && element.currentTime >= duration - 0.08)) {
        finish();
        return;
      }
      frame = window.requestAnimationFrame(onFrame);
    };
    let frame = window.requestAnimationFrame(onFrame);

    const onError = () => finish();
    const onEnded = () => finish();
    element.addEventListener("error", onError);
    element.addEventListener("ended", onEnded);

    return () => {
      window.cancelAnimationFrame(frame);
      element.removeEventListener("error", onError);
      element.removeEventListener("ended", onEnded);
    };
  }, [visible, gate, start, finish]);

  // Échap fonctionne dans les deux états, et Tab reste enfermé dans la boîte.
  useEffect(() => {
    if (!visible) return;
    const focusables = () => {
      const root = boot.current;
      if (!root) return [];
      return Array.from(
        root.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((node) => node.getClientRects().length > 0);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        finish();
        return;
      }
      if (event.key !== "Tab") return;
      const nodes = focusables();
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement;
      if (!boot.current?.contains(active)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
        return;
      }
      if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [visible, finish]);

  // Le fond ne doit être ni focusable ni lisible pendant la boîte de dialogue.
  useEffect(() => {
    if (!visible) return;
    const node = boot.current;
    const parent = node?.parentElement;
    if (!node || !parent) return;
    const siblings = Array.from(parent.children).filter(
      (child): child is HTMLElement => child instanceof HTMLElement && child !== node,
    );
    const previous = siblings.map((element) => ({
      element,
      inert: element.hasAttribute("inert"),
      hidden: element.getAttribute("aria-hidden"),
    }));
    for (const element of siblings) {
      element.setAttribute("inert", "");
      element.setAttribute("aria-hidden", "true");
    }
    return () => {
      for (const item of previous) {
        if (!item.inert) item.element.removeAttribute("inert");
        if (item.hidden === null) item.element.removeAttribute("aria-hidden");
        else item.element.setAttribute("aria-hidden", item.hidden);
      }
    };
  }, [visible]);

  // Le focus entre dans la boîte : le bouton de lancement si l'affiche est
  // visible, sinon « Passer » pendant la lecture.
  useEffect(() => {
    if (!visible) return;
    const target = gate ? launch.current : skip.current;
    target?.focus();
  }, [visible, gate]);

  // Affiche seule : elle ne bloque pas le visiteur plus de dix secondes.
  useEffect(() => {
    if (!visible || !gate) return;
    const timer = window.setTimeout(finish, GATE_MS);
    return () => window.clearTimeout(timer);
  }, [visible, gate, finish]);

  useEffect(() => {
    if (!visible || !playing) return;
    const safety = window.setTimeout(finish, SAFETY_MS);
    return () => window.clearTimeout(safety);
  }, [visible, playing, finish]);

  // La page derrière ne doit ni défiler ni bouger pendant le film.
  useEffect(() => {
    if (!visible) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [visible]);

  if (!visible) return null;

  return (
    <div
      ref={boot}
      className="boot"
      data-phase={leaving ? "out" : "live"}
      data-gate={gate ?? undefined}
      role="dialog"
      aria-modal="true"
      aria-label="Démarrage de Miles Companion"
    >
      <video
        ref={video}
        className="boot-film"
        src={FILM}
        poster={POSTER}
        autoPlay={!reduced}
        muted
        playsInline
        preload="auto"
        aria-hidden="true"
      />
      <div className="boot-veil" aria-hidden="true" />
      <div className="boot-grain" aria-hidden="true" />

      <button ref={skip} type="button" className="boot-skip" onClick={finish}>
        Passer <kbd>Échap</kbd>
      </button>

      {gate ? (
        <div className="boot-gate">
          <div className="boot-gate-media">
            <img
              src={STILL}
              alt="Rendu du boîtier Miles Box : bloc noir, grille perforée, objectif central et liseré lumineux cyan."
              width={1400}
              height={1100}
              decoding="async"
            />
          </div>
          <div className="boot-gate-text">
            <p className="boot-eyebrow">Miles Box</p>
            <h2 className="boot-title">Miles Companion</h2>
            <p className="boot-lead">Quatorze secondes, sans son.</p>
            <button
              ref={launch}
              type="button"
              className="btn btn-primary btn-lg"
              onClick={start}
            >
              <i className="ri-play-fill" aria-hidden="true" />
              Lancer le film
            </button>
            <p className="boot-hint">
              {gate === "reduced"
                ? "Mouvement réduit activé : l'affiche reste fixe, rien ne démarre sans votre clic."
                : "Le film ne démarre pas seul sur cet appareil. Lancez-le quand vous voulez."}
            </p>
          </div>
        </div>
      ) : null}

      {!gate && progress > 0 ? (
        <div className="boot-foot">
          <div
            className="boot-meter"
            role="progressbar"
            aria-label="Chargement"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div className="boot-meter-fill" style={{ width: `${progress}%` }}>
              <span className="boot-meter-tip" aria-hidden="true" />
            </div>
            <div className="boot-meter-row">
              <span className="boot-meter-label">
                <span className="boot-meter-dot" aria-hidden="true" />
                Chargement
              </span>
              <span className="boot-meter-pct mc-num">
                {progress}
                <em>%</em>
              </span>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

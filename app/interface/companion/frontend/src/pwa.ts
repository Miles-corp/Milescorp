import { useEffect, useState } from "react";

/** Événement d'installation du navigateur (non standard, Chromium). */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
}

let deferred: BeforeInstallPromptEvent | null = null;
const subscribers = new Set<() => void>();

function emit() {
  for (const listener of subscribers) listener();
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferred = event as BeforeInstallPromptEvent;
    emit();
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    emit();
  });
}

export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  const iosStandalone =
    (window.navigator as Navigator & { standalone?: boolean }).standalone === true;
  return window.matchMedia("(display-mode: standalone)").matches || iosStandalone;
}

export function isIos(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent;
  return /iPad|iPhone|iPod/.test(ua) || (ua.includes("Macintosh") && navigator.maxTouchPoints > 1);
}

export interface InstallState {
  installed: boolean;
  canInstall: boolean;
  ios: boolean;
}

function snapshot(): InstallState {
  return { installed: isStandalone(), canInstall: deferred !== null, ios: isIos() };
}

export function useInstallState(): InstallState {
  const [state, setState] = useState<InstallState>(snapshot);

  useEffect(() => {
    const update = () => setState(snapshot());
    update();
    subscribers.add(update);
    const media = window.matchMedia("(display-mode: standalone)");
    media.addEventListener("change", update);
    return () => {
      subscribers.delete(update);
      media.removeEventListener("change", update);
    };
  }, []);

  return state;
}

export async function promptInstall(): Promise<"accepted" | "dismissed" | "unavailable"> {
  if (!deferred) return "unavailable";
  const event = deferred;
  deferred = null;
  emit();
  await event.prompt();
  const choice = await event.userChoice;
  return choice.outcome;
}

/** Enregistre le service worker : coque et assets locaux disponibles hors ligne. */
export function registerServiceWorker(): void {
  if (!import.meta.env.PROD) return;
  if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
      /* installation refusée ou indisponible : le site reste utilisable en ligne */
    });
  });
}

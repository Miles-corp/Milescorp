export const PAIR_PATH = "/appairer";

const TOKEN = /^[A-Za-z0-9_-]{20,120}$/;

/** Jeton d'appairage extrait d'un lien `…/appairer#t=…` ou collé seul. */
export function pairingToken(value: string): string | null {
  const text = value.trim();
  if (!text) return null;
  if (!text.includes("://") && !text.includes("#")) {
    return TOKEN.test(text) ? text : null;
  }
  try {
    const url = new URL(text, window.location.origin);
    if (url.pathname.replace(/\/$/, "") !== PAIR_PATH) return null;
    const token = new URLSearchParams(url.hash.replace(/^#/, "")).get("t");
    return token && TOKEN.test(token) ? token : null;
  } catch {
    return null;
  }
}

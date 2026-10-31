import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { promptInstall, useInstallState } from "../pwa";
import { useToast } from "../toast";

type NavItem = { to: string; label: string; short: string; icon: string; end?: boolean };

const GROUPS: { title: string; items: NavItem[] }[] = [
  {
    title: "Pilotage",
    items: [
      { to: "/", label: "Accueil", short: "Accueil", icon: "ri-home-5-line", end: true },
      { to: "/missions", label: "Missions", short: "Missions", icon: "ri-route-line" },
      { to: "/miles", label: "Conversation", short: "MILES", icon: "ri-chat-3-line" },
    ],
  },
  {
    title: "Mémoire",
    items: [
      { to: "/memoire", label: "Mémoire", short: "Mémoire", icon: "ri-brain-line" },
      { to: "/routines", label: "Routines", short: "Routines", icon: "ri-repeat-2-line" },
      { to: "/decouvrir", label: "Découvrir", short: "Découvrir", icon: "ri-compass-3-line" },
    ],
  },
  {
    title: "Système",
    items: [
      { to: "/boitier", label: "Boîtier", short: "Boîtier", icon: "ri-hard-drive-3-line" },
      { to: "/ia", label: "Fournisseurs IA", short: "IA", icon: "ri-sparkling-2-line" },
      { to: "/reglages", label: "Réglages", short: "Réglages", icon: "ri-settings-3-line" },
    ],
  },
];

const ALL = GROUPS.flatMap((group) => group.items);
/** Quatre destinations au pouce, dans cet ordre, le reste derrière « Plus ». */
const TABS = ["/", "/boitier", "/ia", "/missions"]
  .map((path) => ALL.find((item) => item.to === path))
  .filter((item): item is NavItem => Boolean(item));

export function Layout() {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const { canInstall } = useInstallState();
  const location = useLocation();
  const [sheetOpen, setSheetOpen] = useState(false);
  const sheet = useRef<HTMLDivElement>(null);
  const plus = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  const dev = Boolean(me?.preferences.dev_mode);

  const current =
    ALL.slice()
      .sort((a, b) => b.to.length - a.to.length)
      .find((item) => (item.end ? location.pathname === item.to : location.pathname.startsWith(item.to)))
      ?.label ?? "Présentation";

  useEffect(() => {
    setSheetOpen(false);
  }, [location.pathname]);

  // Le focus entre dans la feuille, y reste, et revient au bouton « Plus ».
  useEffect(() => {
    if (!sheetOpen) {
      if (wasOpen.current) plus.current?.focus();
      wasOpen.current = false;
      return;
    }
    wasOpen.current = true;
    const root = sheet.current;
    const first = root?.querySelector<HTMLElement>('a[href], button:not([disabled])');
    (first ?? root)?.focus();
  }, [sheetOpen]);

  useEffect(() => {
    if (!sheetOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setSheetOpen(false);
        return;
      }
      if (event.key !== "Tab") return;
      const root = sheet.current;
      if (!root) return;
      const nodes = Array.from(
        root.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((node) => node.getClientRects().length > 0);
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement;
      if (!root.contains(active)) {
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
  }, [sheetOpen]);

  // Le reste de la page est inerte sous la feuille ; le voile reste cliquable.
  useEffect(() => {
    if (!sheetOpen) return;
    const node = sheet.current;
    const parent = node?.parentElement;
    if (!node || !parent) return;
    const siblings = Array.from(parent.children).filter(
      (child): child is HTMLElement =>
        child instanceof HTMLElement &&
        child !== node &&
        !child.classList.contains("sheet-backdrop"),
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
  }, [sheetOpen]);

  async function handleInstall() {
    const outcome = await promptInstall();
    if (outcome === "accepted") toast.show("Installation lancée.", "ok");
    else if (outcome === "dismissed") toast.show("Installation annulée.", "info");
  }

  async function handleLogout() {
    await logout();
    navigate("/connexion", { replace: true });
  }

  const secondary = [
    ...ALL.filter((item) => !TABS.some((tab) => tab.to === item.to)),
    { to: "/presentation", label: "Présentation", short: "Présentation", icon: "ri-presentation-line" },
    ...(dev
      ? [{ to: "/journal", label: "Journal", short: "Journal", icon: "ri-terminal-box-line" }]
      : []),
  ];

  return (
    <div className="shell">
      <a className="skip-link" href="#contenu">
        Aller au contenu
      </a>

      <aside className="sidebar">
        <NavLink className="brand" to="/" aria-label="Miles Companion, accueil">
          <span className="brand-mark" aria-hidden="true">
            <i className="ri-focus-3-line" />
          </span>
          <span>
            <strong>Miles Companion</strong>
            <small>cockpit local</small>
          </span>
        </NavLink>

        <nav className="nav" aria-label="Navigation principale">
          {GROUPS.map((group) => (
            <div className="nav-group" key={group.title}>
              <p className="nav-group-label">{group.title}</p>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) => (isActive ? "nav-link is-active" : "nav-link")}
                >
                  <i className={item.icon} aria-hidden="true" />
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
          <div className="nav-group nav-group-foot">
            <NavLink
              to="/presentation"
              className={({ isActive }) => (isActive ? "nav-link is-active" : "nav-link")}
            >
              <i className="ri-presentation-line" aria-hidden="true" />
              Présentation
            </NavLink>
            {dev ? (
              <NavLink
                to="/journal"
                className={({ isActive }) => (isActive ? "nav-link is-active" : "nav-link")}
              >
                <i className="ri-terminal-box-line" aria-hidden="true" />
                Journal
              </NavLink>
            ) : null}
          </div>
        </nav>

        <div className="sidebar-foot">
          <div className="link-state">
            <span
              className={`dot ${me?.miles_configured ? "dot-ok" : "dot-warn"}`}
              aria-hidden="true"
            />
            <div>
              <strong>{me?.miles_configured ? "MILES connecté" : "MILES non connecté"}</strong>
              <small>{me?.miles_configured ? "jeton côté serveur" : "voir Réglages"}</small>
            </div>
          </div>
          {canInstall ? (
            <button
              type="button"
              className="btn btn-quiet btn-small sidebar-install"
              onClick={() => void handleInstall()}
            >
              <i className="ri-download-2-line" aria-hidden="true" />
              Installer l'application
            </button>
          ) : null}
          <p className="version">Miles Box v1.0 · site local</p>
        </div>
      </aside>

      <div className="content">
        <header className="topbar">
          <p className="topbar-title">{current}</p>
          <div className="topbar-right">
            {dev ? <span className="badge badge-warn">mode développeur</span> : null}
            <span className="user-chip" title={`${me?.account.display_name} (${me?.account.role})`}>
              <i className="ri-user-3-line" aria-hidden="true" />
              <span>{me?.account.display_name}</span>
              <small>{me?.account.role === "admin" ? "admin" : "utilisateur"}</small>
            </span>
            <button type="button" className="btn btn-quiet btn-small" onClick={handleLogout}>
              <i className="ri-logout-box-r-line" aria-hidden="true" />
              Quitter
            </button>
          </div>
        </header>

        {dev ? (
          <p className="dev-banner" role="status">
            <i className="ri-terminal-box-line" aria-hidden="true" />
            Mode développeur actif : détails techniques et journaux visibles. Chaque
            consultation est journalisée.
          </p>
        ) : null}

        <main id="contenu" className="main">
          <Outlet />
        </main>
      </div>

      <nav className="tabbar" aria-label="Navigation mobile">
        {TABS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => (isActive ? "tab-link is-active" : "tab-link")}
          >
            <i className={item.icon} aria-hidden="true" />
            <span>{item.short}</span>
          </NavLink>
        ))}
        <button
          ref={plus}
          type="button"
          className={`tab-link ${
            sheetOpen || secondary.some((item) => location.pathname.startsWith(item.to))
              ? "is-active"
              : ""
          }`}
          aria-expanded={sheetOpen}
          aria-controls="sheet-plus"
          onClick={() => setSheetOpen((value) => !value)}
        >
          <i className="ri-menu-3-line" aria-hidden="true" />
          <span>Plus</span>
        </button>
      </nav>

      {sheetOpen ? (
        <>
          <div className="sheet-backdrop" onClick={() => setSheetOpen(false)} />
          <div
            ref={sheet}
            className="sheet"
            id="sheet-plus"
            role="dialog"
            aria-modal="true"
            aria-label="Plus de pages"
            tabIndex={-1}
          >
            <p className="nav-group-label">Toutes les pages</p>
            <ul className="sheet-list">
              {secondary.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) => (isActive ? "sheet-link is-active" : "sheet-link")}
                  >
                    <i className={item.icon} aria-hidden="true" />
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
            <div className="sheet-actions">
              {canInstall ? (
                <button
                  type="button"
                  className="btn btn-quiet"
                  onClick={() => void handleInstall()}
                >
                  <i className="ri-download-2-line" aria-hidden="true" />
                  Installer l'application
                </button>
              ) : null}
              <button type="button" className="btn btn-quiet" onClick={handleLogout}>
                <i className="ri-logout-box-r-line" aria-hidden="true" />
                Quitter la session
              </button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api, errorMessage } from "../api";
import { summarizeResult } from "../format";
import { useToast } from "../toast";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {description ? <p className="page-lead">{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function Card({
  title,
  subtitle,
  actions,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`.trim()}>
      {title || actions ? (
        <header className="card-head">
          <div>
            {title ? <h2>{title}</h2> : null}
            {subtitle ? <p className="muted">{subtitle}</p> : null}
          </div>
          {actions ? <div className="card-actions">{actions}</div> : null}
        </header>
      ) : null}
      {children}
    </section>
  );
}

export function Badge({
  tone = "muted",
  children,
}: {
  tone?: "ok" | "warn" | "error" | "muted" | "accent";
  children: ReactNode;
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function Loading({ label = "Chargement…" }: { label?: string }) {
  return (
    <p className="state state-loading" role="status">
      <span className="spinner" aria-hidden="true" />
      {label}
    </p>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state state-error" role="alert">
      <i className="ri-error-warning-line" aria-hidden="true" />
      <p>{message}</p>
      {onRetry ? (
        <button type="button" className="btn btn-ghost" onClick={onRetry}>
          Réessayer
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({
  icon = "ri-information-line",
  title,
  children,
  action,
}: {
  icon?: string;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="state state-empty">
      <span className="state-icon" aria-hidden="true">
        <i className={icon} />
      </span>
      <h2>{title}</h2>
      {children ? <div className="state-body">{children}</div> : null}
      {action}
    </div>
  );
}

export function SetupGuide({
  steps,
}: {
  steps: { title: string; detail: string; action?: ReactNode; done?: boolean }[];
}) {
  return (
    <ol className="guide">
      {steps.map((step, index) => (
        <li className="guide-step" key={step.title}>
          <span className="guide-index" aria-hidden="true">
            {step.done ? <i className="ri-check-line" /> : String(index + 1).padStart(2, "0")}
          </span>
          <div>
            <strong>{step.title}</strong>
            <small>{step.detail}</small>
          </div>
          {step.action ?? null}
        </li>
      ))}
    </ol>
  );
}

export function Modal({
  open,
  title,
  children,
  onClose,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const first = ref.current?.querySelector<HTMLElement>(
      "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])",
    );
    first?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
      if (event.key !== "Tab" || !ref.current) return;
      const nodes = Array.from(
        ref.current.querySelectorAll<HTMLElement>(
          "button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
        ),
      );
      if (nodes.length === 0) return;
      const firstNode = nodes[0];
      const lastNode = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === firstNode) {
        event.preventDefault();
        lastNode.focus();
      } else if (!event.shiftKey && document.activeElement === lastNode) {
        event.preventDefault();
        firstNode.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        ref={ref}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="modal-head">
          <h2 id="modal-title">{title}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Fermer">
            <i className="ri-close-line" aria-hidden="true" />
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}

export function ConfirmAction({
  action,
  payload,
  label,
  icon = "ri-play-line",
  className = "btn btn-primary",
  disabled = false,
  onDone,
}: {
  action: string;
  payload: Record<string, unknown>;
  label: string;
  icon?: string;
  className?: string;
  disabled?: boolean;
  onDone?: () => void;
}) {
  const toast = useToast();
  const [pending, setPending] = useState<{ token: string; confirmation: string } | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function prepare() {
    setPreparing(true);
    setError(null);
    try {
      const result = await api.prepare(action, payload);
      setPending({ token: result.token, confirmation: result.confirmation });
    } catch (exc) {
      setError(errorMessage(exc));
      toast.show(errorMessage(exc), "error");
    } finally {
      setPreparing(false);
    }
  }

  async function execute() {
    if (!pending) return;
    setExecuting(true);
    try {
      const result = await api.execute(pending.token, payload);
      toast.show(summarizeResult(result.result), "ok");
      setPending(null);
      onDone?.();
    } catch (exc) {
      setError(errorMessage(exc));
      toast.show(errorMessage(exc), "error");
    } finally {
      setExecuting(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className={className}
        onClick={prepare}
        disabled={disabled || preparing}
        title={label}
      >
        <i className={preparing ? "ri-loader-3-line spin" : icon} aria-hidden="true" />
        {preparing ? "Préparation…" : label}
      </button>
      <Modal
        open={pending !== null}
        title="Confirmation"
        onClose={() => {
          if (!executing) setPending(null);
        }}
      >
        <p className="modal-text">{pending?.confirmation}</p>
        <p className="muted small">
          L'action est réellement exécutée après confirmation ; le jeton est à
          usage unique et expire en 60 secondes.
        </p>
        {error ? <p className="form-error" role="alert">{error}</p> : null}
        <div className="modal-actions">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setPending(null)}
            disabled={executing}
          >
            Annuler
          </button>
          <button type="button" className="btn btn-primary" onClick={execute} disabled={executing}>
            <i className={executing ? "ri-loader-3-line spin" : "ri-check-line"} aria-hidden="true" />
            {executing ? "Exécution…" : "Confirmer"}
          </button>
        </div>
      </Modal>
    </>
  );
}

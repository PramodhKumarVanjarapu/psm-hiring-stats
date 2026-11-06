import { useEffect, useRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import type { Stage } from "../types";

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

/* ---------- buttons & inputs ---------- */
type Variant = "primary" | "secondary" | "ghost" | "danger";
export function Button({ variant = "secondary", className, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  const styles: Record<Variant, string> = {
    primary: "bg-primary text-primary-ink hover:brightness-110",
    secondary: "bg-surface text-ink border border-line hover:bg-sunken",
    ghost: "text-primary hover:bg-sunken",
    danger: "bg-bad text-white hover:brightness-110",
  };
  return (
    <button
      {...p}
      className={cx("inline-flex items-center justify-center gap-1.5 rounded-md px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50", styles[variant], className)}
    />
  );
}

const fieldCls = "w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-faint focus:border-primary focus:outline-none";
export const Input = ({ className, ...p }: InputHTMLAttributes<HTMLInputElement>) => <input {...p} className={cx(fieldCls, className)} />;
export const Select = ({ className, children, ...p }: SelectHTMLAttributes<HTMLSelectElement>) => (
  <select {...p} className={cx(fieldCls, "pr-8", className)}>{children}</select>
);

export function Field({ label, hint, children, className }: { label: string; hint?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <label className={cx("block", className)}>
      <span className="mb-1 block text-sm font-medium text-ink">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </label>
  );
}

/* ---------- page structure ---------- */
export function PageHeader({ title, sub, actions }: { title: ReactNode; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {sub && <div className="mt-1 text-sm text-muted">{sub}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Section({ title, aside, children, className }: { title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx("mb-8", className)}>
      {(title || aside) && (
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          {title && <h2 className="text-base font-semibold text-ink">{title}</h2>}
          {aside && <div className="text-sm text-muted">{aside}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export const Panel = ({ children, className }: { children: ReactNode; className?: string }) => (
  <div className={cx("rounded-lg border border-line bg-surface", className)}>{children}</div>
);

/* ---------- tables ---------- */
export function Table({ head, children, className }: { head: ReactNode[]; children: ReactNode; className?: string }) {
  return (
    <div className={cx("overflow-x-auto rounded-lg border border-line bg-surface", className)}>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs font-medium text-muted">
            {head.map((h, i) => (
              <th key={i} className="whitespace-nowrap px-3 py-2.5 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="[&>tr]:border-b [&>tr]:border-line [&>tr:last-child]:border-0">{children}</tbody>
      </table>
    </div>
  );
}
export const Td = ({ children, className, num }: { children?: ReactNode; className?: string; num?: boolean }) => (
  <td className={cx("px-3 py-2.5 align-middle", num && "num text-right whitespace-nowrap", className)}>{children}</td>
);
export const Th = ({ children, num }: { children: ReactNode; num?: boolean }) => <span className={cx(num && "block text-right")}>{children}</span>;

export function Pager({ total, skip, limit, onChange }: { total: number; skip: number; limit: number; onChange: (skip: number) => void }) {
  if (total <= limit) return null;
  const from = skip + 1;
  const to = Math.min(skip + limit, total);
  return (
    <div className="mt-3 flex items-center justify-between text-sm text-muted">
      <span className="num">
        {from.toLocaleString("en-IN")}–{to.toLocaleString("en-IN")} of {total.toLocaleString("en-IN")}
      </span>
      <div className="flex gap-2">
        <Button disabled={skip === 0} onClick={() => onChange(Math.max(0, skip - limit))}>Previous</Button>
        <Button disabled={to >= total} onClick={() => onChange(skip + limit)}>Next</Button>
      </div>
    </div>
  );
}

/* ---------- feedback ---------- */
export function Note({ tone = "info", children }: { tone?: "info" | "good" | "warn" | "bad"; children: ReactNode }) {
  const t = {
    info: "border-line bg-sunken text-ink",
    good: "border-transparent bg-good-bg text-good",
    warn: "border-transparent bg-warn-bg text-warn",
    bad: "border-transparent bg-bad-bg text-bad",
  }[tone];
  return <div role={tone === "bad" ? "alert" : undefined} className={cx("rounded-md border px-3.5 py-2.5 text-sm", t)}>{children}</div>;
}

export const Loading = ({ label = "Loading…" }: { label?: string }) => (
  <div className="py-10 text-sm text-muted" aria-live="polite">{label}</div>
);

export function ErrorNote({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : "Something went wrong.";
  return <Note tone="bad">{msg}</Note>;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line px-6 py-10 text-center">
      <p className="font-medium text-ink">{title}</p>
      {children && <div className="mt-1 text-sm text-muted">{children}</div>}
    </div>
  );
}

/* ---------- stage + label chips ---------- */
export const STAGE_BG: Record<Stage, string> = {
  TA: "bg-st-ta", RS: "bg-st-rs", SC: "bg-st-sc", AS: "bg-st-as", SP: "bg-st-sp",
};
export const STAGE_TEXT_ON: Record<Stage, string> = {
  TA: "text-[#0e2233]", RS: "text-white", SC: "text-white", AS: "text-white", SP: "text-white",
};

export function StageDot({ stage }: { stage: Stage }) {
  return <span aria-hidden className={cx("inline-block h-2.5 w-2.5 shrink-0 rounded-sm", STAGE_BG[stage])} />;
}

export function labelTone(label?: string | null): "good" | "warn" | "bad" | "neutral" {
  if (!label) return "neutral";
  if (label === "P1" || label === "Select") return "good";
  if (label === "Hold" || label === "P3") return "warn";
  if (label === "Reject") return "bad";
  return "neutral";
}

export function LabelChip({ label }: { label?: string | null }) {
  if (!label) return <span className="text-faint">–</span>;
  const tone = labelTone(label);
  const cls = {
    good: "bg-good-bg text-good",
    warn: "bg-warn-bg text-warn",
    bad: "bg-bad-bg text-bad",
    neutral: "bg-sunken text-muted",
  }[tone];
  return <span className={cx("inline-block whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium", cls)}>{label}</span>;
}

export function CategoryTag({ category }: { category?: string | null }) {
  if (!category) return <span className="text-faint">–</span>;
  return <span className="text-sm text-ink">{category}</span>;
}

/* ---------- tabs ---------- */
export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: { id: T; label: string }[] }) {
  return (
    <div role="tablist" className="mb-5 flex gap-1 overflow-x-auto border-b border-line">
      {items.map((it) => (
        <button
          key={it.id}
          role="tab"
          aria-selected={value === it.id}
          onClick={() => onChange(it.id)}
          className={cx(
            "-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition",
            value === it.id ? "border-primary text-ink" : "border-transparent text-muted hover:text-ink",
          )}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}

/* ---------- dialog ---------- */
export function Dialog({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={onClose}
      className={cx("m-auto w-[calc(100%-2rem)] rounded-xl border border-line bg-surface p-0 text-ink shadow-xl", wide ? "max-w-2xl" : "max-w-md")}
    >
      {open && (
        <div className="p-6">
          <div className="mb-4 flex items-start justify-between gap-4">
            <h2 className="text-lg font-semibold">{title}</h2>
            <button onClick={onClose} aria-label="Close" className="rounded px-2 text-xl leading-none text-muted hover:text-ink">×</button>
          </div>
          {children}
        </div>
      )}
    </dialog>
  );
}

/* ---------- small figure ---------- */
export function Figure({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div>
      <div className="text-sm text-muted">{label}</div>
      <div className="num text-2xl font-semibold text-ink">{value}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  );
}

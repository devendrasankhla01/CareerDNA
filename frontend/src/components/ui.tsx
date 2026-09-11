import { Loader2 } from "lucide-react";
import { CATEGORY_META, STATUS_META } from "../lib/format";

export function Card({ title, subtitle, actions, children, className = "" }: {
  title?: string; subtitle?: string; actions?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div>
            {title && <h2 className="text-[15px] font-semibold text-slate-900">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-[13px] text-slate-500">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function Badge({ children, cls = "bg-slate-100 text-slate-600 border-slate-200" }: {
  children: React.ReactNode; cls?: string;
}) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11.5px] font-medium ${cls}`}>
      {children}
    </span>
  );
}

export function CategoryBadge({ category }: { category: string }) {
  const m = CATEGORY_META[category] || { label: category, cls: "bg-slate-100 text-slate-600 border-slate-200" };
  return <Badge cls={m.cls}>{m.label}</Badge>;
}

export function StatusBadge({ status }: { status: string }) {
  const m = STATUS_META[status] || { label: status, cls: "bg-slate-100 text-slate-600 border-slate-200" };
  return <Badge cls={m.cls}>{m.label}</Badge>;
}

export function Stat({ label, value, sub, tone }: {
  label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: "good" | "bad" | "neutral";
}) {
  const toneCls = tone === "good" ? "text-teal-700" : tone === "bad" ? "text-rose-700" : "text-slate-900";
  return (
    <div className="card px-5 py-4">
      <div className="label">{label}</div>
      <div className={`mt-1.5 text-2xl font-semibold tabular-nums ${toneCls}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[12.5px] text-slate-500">{sub}</div>}
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      {message}
      {onRetry && (
        <button className="ml-3 font-semibold underline" onClick={onRetry}>Retry</button>
      )}
    </div>
  );
}

export function EmptyState({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="py-10 text-center">
      <div className="text-sm font-medium text-slate-600">{title}</div>
      {sub && <div className="mt-1 text-[13px] text-slate-400">{sub}</div>}
    </div>
  );
}

export function Bar({ value, max = 100, tone = "navy" }: { value: number; max?: number; tone?: "navy" | "teal" | "amber" | "rose" }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const cls =
    tone === "teal" ? "bg-teal-500" : tone === "amber" ? "bg-amber-500" : tone === "rose" ? "bg-rose-500" : "bg-navy-600";
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
      <div className={`h-full rounded-full ${cls}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Disclaimer({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-lg bg-slate-50 px-3.5 py-2.5 text-[12px] leading-relaxed text-slate-500">
      {children}
    </p>
  );
}

export function Table({ head, children }: { head: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] border-collapse">
        <thead className="border-b border-slate-200">{head}</thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
    </div>
  );
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return <span className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">{children}</span>;
}

export const CATEGORY_META: Record<string, { label: string; cls: string; dot: string }> = {
  READY: { label: "Ready", cls: "bg-teal-50 text-teal-700 border-teal-200", dot: "bg-teal-500" },
  NEAR_READY: { label: "Near-Ready", cls: "bg-amber-50 text-amber-700 border-amber-200", dot: "bg-amber-500" },
  NEEDS_TRAINING: { label: "Needs Training", cls: "bg-rose-50 text-rose-700 border-rose-200", dot: "bg-rose-500" },
};

export const CATEGORY_COLORS: Record<string, string> = {
  READY: "#149c8d",
  NEAR_READY: "#d97706",
  NEEDS_TRAINING: "#e11d48",
};

export const STATUS_META: Record<string, { label: string; cls: string }> = {
  PENDING: { label: "Pending", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  VERIFIED: { label: "Verified", cls: "bg-teal-50 text-teal-700 border-teal-200" },
  CORRECTION_REQUIRED: { label: "Correction Required", cls: "bg-orange-50 text-orange-700 border-orange-200" },
  REJECTED: { label: "Rejected", cls: "bg-rose-50 text-rose-700 border-rose-200" },
};

export function fmt(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}

export function fmt1(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toFixed(1);
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function trustBand(score: number): string {
  if (score >= 90) return "Very High";
  if (score >= 75) return "High";
  if (score >= 60) return "Moderate";
  return "Low";
}

export function ScoreRing({ score, size = 120, stroke = 10, label = "Placement Readiness" }: {
  score: number; size?: number; stroke?: number; label?: string;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score));
  const off = c * (1 - pct / 100);
  const color = pct >= 80 ? "#149c8d" : pct >= 60 ? "#d97706" : "#e11d48";
  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#eef2f7" strokeWidth={stroke} />
          <circle
            cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
            strokeLinecap="round" strokeDasharray={c} strokeDashoffset={off}
            style={{ transition: "stroke-dashoffset 600ms ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[26px] font-semibold tabular-nums text-slate-900">{pct.toFixed(1)}</span>
          <span className="text-[10.5px] font-medium uppercase tracking-wide text-slate-400">/ 100</span>
        </div>
      </div>
      <div className="mt-2 text-[12.5px] font-medium text-slate-500">{label}</div>
    </div>
  );
}

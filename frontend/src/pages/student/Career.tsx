import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Target } from "lucide-react";
import { api } from "../../api/client";
import { fmt, fmt1 } from "../../lib/format";
import { Bar, Card, ErrorBox, Spinner, Stat } from "../../components/ui";

interface Comparison {
  skill_code: string; target: number; current: number | null; gap: number | null;
  mandatory: boolean; weight: number;
}
interface CareerResp {
  status: string;
  tracks: { code: string; name: string; description: string }[];
  matches: { career_code: string; name: string; match_score: number; alignment: string; major_gap_count: number; data_coverage: number }[];
  target_code: string | null;
  detail: {
    career_code: string; match_score: number; alignment: string; data_coverage: number;
    major_gap_count: number; comparisons: Comparison[];
    gaps: Comparison[]; strengths: Comparison[];
  } | null;
}

export default function Career() {
  const qc = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["career"],
    queryFn: () => api<CareerResp>("/student/career"),
  });

  const setTarget = useMutation({
    mutationFn: (code: string | null) => api("/student/career/target", { body: { career_code: code } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["career"] }),
  });

  if (isLoading) return <Spinner label="Computing career matches…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data || !data.detail) return <ErrorBox message="Career data unavailable." />;

  const detail = data.detail;
  const isTarget = data.target_code === detail.career_code;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Career Match</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          Transparent weighted benchmark matching against institutional benchmarks.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        {data.matches.map((m) => (
          <button
            key={m.career_code}
            className="card px-5 py-4 text-left transition hover:border-navy-300"
            style={m.career_code === data.target_code ? { borderColor: "#2c5489", boxShadow: "0 0 0 1px #2c5489" } : undefined}
            onClick={() => setTarget.mutate(m.career_code)}
          >
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[15px] font-semibold text-slate-900">{m.name}</div>
                <div className="mt-0.5 text-[12px] text-slate-400">{m.alignment} alignment · {m.data_coverage}% data coverage</div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-semibold tabular-nums text-navy-800">{fmt(m.match_score)}</div>
                <div className="text-[11px] text-slate-400">match</div>
              </div>
            </div>
            <div className="mt-3">
              <Bar value={m.match_score} tone={m.match_score >= 80 ? "teal" : m.match_score >= 65 ? "navy" : "amber"} />
            </div>
            <div className="mt-2 text-[12px] text-slate-500">
              {m.major_gap_count > 0 ? `${m.major_gap_count} major gap${m.major_gap_count > 1 ? "s" : ""} to close` : "No major gaps"}
              {m.career_code === data.target_code && (
                <span className="ml-2 inline-flex items-center gap-1 font-medium text-navy-700">
                  <Target className="h-3 w-3" /> your target
                </span>
              )}
            </div>
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card
          title={detail.career_code === "FULL_STACK" ? "Full-Stack Developer" : "Data Analyst"}
          subtitle="Benchmark comparison (selected track)"
          actions={
            <button
              className={isTarget ? "btn-outline" : "btn-primary"}
              onClick={() => setTarget.mutate(isTarget ? null : detail.career_code)}
            >
              {isTarget ? "Unset target" : "Set as target"}
            </button>
          }
        >
          <ul className="space-y-3">
            {detail.comparisons.map((c) => (
              <li key={c.skill_code}>
                <div className="mb-1 flex items-center justify-between gap-2 text-[12.5px]">
                  <span className="flex items-center gap-1.5 font-medium text-slate-700">
                    {prettySkill(c.skill_code)}
                    {c.mandatory && (
                      <span title="Mandatory skill" className="text-[10px] font-semibold uppercase text-rose-500">req</span>
                    )}
                  </span>
                  <span className="tabular-nums text-slate-500">
                    {c.current !== null ? fmt(c.current) : "—"} / {fmt(c.target)}
                  </span>
                </div>
                <Bar
                  value={c.current ?? 0} max={c.target}
                  tone={(c.current ?? 0) >= c.target ? "teal" : (c.current ?? 0) >= c.target * 0.7 ? "navy" : "amber"}
                />
                {c.gap !== null && c.gap >= 10 && (
                  <div className="mt-0.5 text-[11px] text-amber-600">gap {fmt(c.gap)}</div>
                )}
              </li>
            ))}
          </ul>
        </Card>

        <div className="space-y-4 lg:col-span-2">
          <div className="grid gap-4 sm:grid-cols-3">
            <Stat label="Match score" value={fmt(detail.match_score)} sub={detail.alignment} />
            <Stat label="Major gaps" value={fmt(detail.major_gap_count)} tone={detail.major_gap_count ? "bad" : "good"} />
            <Stat label="Data coverage" value={`${fmt(detail.data_coverage)}%`} sub="benchmark skills measured" />
          </div>

          <Card title="Priority gaps for this track"
            subtitle={detail.gaps.length ? "Weighted by importance × distance to benchmark" : undefined}>
            {detail.gaps.length === 0 ? (
              <p className="flex items-center gap-2 text-[13.5px] text-teal-700">
                <CheckCircle2 className="h-4 w-4" /> No significant gaps for this track right now.
              </p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {detail.gaps.map((g) => (
                  <li key={g.skill_code} className="flex items-center justify-between gap-3 py-2.5">
                    <div>
                      <div className="text-[13.5px] font-medium text-slate-800">{prettySkill(g.skill_code)}</div>
                      <div className="text-[11.5px] text-slate-400">
                        weight {fmt(g.weight * 100)}% {g.mandatory && "· required"}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[13px] font-semibold tabular-nums text-amber-700">
                        {g.gap !== null ? `${fmt1(g.gap)} pts` : "no data"}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {g.current !== null ? `${fmt(g.current)} → ${fmt(g.target)}` : `target ${fmt(g.target)}`}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 flex items-start gap-1.5 text-[12px] text-slate-400">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Setting a target career changes your gaps, roadmap and Path to Ready — it does not
              change your base Placement Readiness score.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}

function prettySkill(code: string) {
  if (code === "PROJECT_EXP") return "Practical Projects";
  if (code === "C_CPP") return "C/C++";
  if (code === "HTML_CSS") return "HTML/CSS";
  if (code === "NODE_JS") return "Node.js";
  if (code === "REST_API") return "REST APIs";
  return code.replace(/_/g, " ");
}

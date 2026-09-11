import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, TrendingUp } from "lucide-react";
import { api } from "../../api/client";
import { fmt, fmt1 } from "../../lib/format";
import { Badge, Card, ErrorBox, Spinner, Table } from "../../components/ui";

interface RankedIv {
  intervention_id: number; code: string; name: string; skills: string[];
  estimated_weeks: number; affected_students: number; affected_share: number;
  avg_severity: number; avg_readiness_delta_at_default: number;
  primary_cohorts: { label: string; count: number; average_readiness: number }[];
  baseline_sim: {
    cohort_size: number; avg_readiness_delta: number; students_moving_category: number;
    movements: { from: string; to: string; count: number }[];
    baseline: Record<string, number>; projected: Record<string, number>;
  } | null;
  score: number; priority: "High" | "Medium" | "Low"; reason_summary: string;
}
interface IvResp { status: string; interventions: RankedIv[]; analyzed_students: number }
interface SimResp {
  status: string;
  intervention: { code: string; name: string; skills: string[]; estimated_weeks: number };
  assumption: string;
  simulation: {
    cohort_size: number; avg_readiness_delta: number; students_moving_category: number;
    movements: { from: string; to: string; count: number }[];
    baseline: Record<string, number>; projected: Record<string, number>;
  } | null;
  disclaimer: string;
  message?: string;
}
interface CohortResp {
  status: string;
  students: {
    student_id: number; name: string; usn: string; branch: string; semester: number;
    readiness: number; category: string; profile_trust: number; primary_gap: string | null;
  }[];
}

const PRIORITY_CLS: Record<string, string> = {
  High: "bg-rose-50 text-rose-700 border-rose-200",
  Medium: "bg-amber-50 text-amber-700 border-amber-200",
  Low: "bg-slate-100 text-slate-600 border-slate-200",
};

const CAT_LABEL: Record<string, string> = {
  READY: "Ready", NEAR_READY: "Near-Ready", NEEDS_TRAINING: "Needs Training",
};

export default function Interventions() {
  const qc = useQueryClient();
  const [branch, setBranch] = useState("");
  const [semester, setSemester] = useState("");
  const [code, setCode] = useState<string>("");
  const [improvement, setImprovement] = useState(20);
  const [showCohort, setShowCohort] = useState(false);

  const q = useQuery({
    queryKey: ["tpo-interventions", branch, semester],
    queryFn: () => api<IvResp>(
      `/tpo/interventions${branch ? `?branch=${branch}` : ""}${semester ? (branch ? "&" : "?") + `semester=${semester}` : ""}`
    ),
  });
  const activeCode = code || q.data?.interventions[0]?.code || "";

  const cohort = useQuery({
    queryKey: ["iv-cohort", activeCode],
    queryFn: () => api<CohortResp>(`/tpo/interventions/${activeCode}/cohort`),
    enabled: showCohort && !!activeCode,
  });

  const sim = useMutationSim(activeCode, improvement, branch, semester);

  if (q.isLoading) return <Spinner label="Ranking interventions from cohort deficits…" />;
  if (q.isError) return <ErrorBox message={(q.error as Error).message} onRetry={() => q.refetch()} />;
  if (!q.data) return null;
  if (q.data.status === "model_unavailable") {
    return <ErrorBox message="The readiness model is not deployed — intervention simulation requires it." />;
  }
  if (q.data.interventions.length === 0) {
    return (
      <div className="space-y-5">
        <h1 className="text-xl font-semibold text-slate-900">Recommended Interventions</h1>
        <Card>
          <p className="text-[13px] text-slate-500">
            No intervention qualifies in this filter — each needs a minimum affected population.
            Widen the branch/semester filter.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Recommended Interventions</h1>
          <p className="mt-0.5 text-[13px] text-slate-500">
            Ranked from real cohort skill deficits and simulated readiness sensitivity
            ({fmt(q.data.analyzed_students)} analyzed students).
          </p>
        </div>
        <div className="flex gap-2">
          <select className="input !w-auto" value={branch} onChange={(e) => setBranch(e.target.value)}>
            <option value="">All branches</option>
            {["CSE", "ISE", "CE", "ECE", "ME"].map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
          <select className="input !w-auto" value={semester} onChange={(e) => setSemester(e.target.value)}>
            <option value="">All semesters</option>
            {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => <option key={n} value={n}>Semester {n}</option>)}
          </select>
        </div>
      </header>

      <div className="space-y-3">
        {q.data.interventions.map((iv, i) => (
          <Card key={iv.code} className={activeCode === iv.code ? "ring-2 ring-navy-300" : ""}
            actions={
              <button
                className={`rounded-full border px-3 py-1 text-[12px] font-medium transition ${
                  activeCode === iv.code ? "border-navy-300 bg-navy-50 text-navy-800" : "border-slate-200 text-slate-500 hover:bg-slate-50"
                }`}
                onClick={() => { setCode(iv.code); setShowCohort(false); }}
              >
                {activeCode === iv.code ? "Simulating" : "Simulate impact"}
              </button>
            }>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-[240px]">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-navy-700 text-[12px] font-semibold text-white">{i + 1}</span>
                  <span className="text-[14.5px] font-semibold text-slate-900">{iv.name}</span>
                  <Badge cls={PRIORITY_CLS[iv.priority] || PRIORITY_CLS.Low}>{iv.priority} priority</Badge>
                </div>
                <p className="mt-1.5 max-w-2xl text-[12.5px] leading-relaxed text-slate-500">{iv.reason_summary}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {iv.skills.map((sk) => <Badge key={sk} cls="bg-navy-50 text-navy-700 border-navy-200">{sk}</Badge>)}
                  <Badge>~{iv.estimated_weeks} weeks</Badge>
                </div>
              </div>
              <div className="flex gap-6 text-right">
                <div>
                  <div className="label !text-[10.5px]">Affected</div>
                  <div className="mt-0.5 text-lg font-semibold tabular-nums text-slate-900">{fmt(iv.affected_students)}</div>
                  <div className="text-[11px] text-slate-400">{fmt(iv.affected_share * 100, 1)}% of cohort</div>
                </div>
                <div>
                  <div className="label !text-[10.5px]">Avg delta (default)</div>
                  <div className="mt-0.5 text-lg font-semibold tabular-nums text-teal-700">+{fmt1(iv.avg_readiness_delta_at_default)}</div>
                  <div className="text-[11px] text-slate-400">readiness pts</div>
                </div>
              </div>
            </div>
            {iv.primary_cohorts?.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2 border-t border-slate-100 pt-3">
                <span className="text-[11.5px] text-slate-400">Most affected:</span>
                {iv.primary_cohorts.map((c) => (
                  <Badge key={c.label} cls="bg-slate-50 text-slate-600 border-slate-200">
                    {c.label} · {c.count} (avg {fmt1(c.average_readiness)})
                  </Badge>
                ))}
              </div>
            )}
          </Card>
        ))}
      </div>

      <Card title="Cohort impact simulation"
        subtitle="Assume an average skill improvement for students below benchmark, then re-run the readiness model on the cohort">
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-4">
            <div>
              <label className="label" htmlFor="ivsel">Intervention</label>
              <select id="ivsel" className="input mt-1.5" value={activeCode} onChange={(e) => setCode(e.target.value)}>
                {q.data.interventions.map((iv) => <option key={iv.code} value={iv.code}>{iv.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="imp">Assumed average skill improvement: <span className="font-semibold text-navy-700">+{improvement} pts</span></label>
              <input id="imp" type="range" min={5} max={40} step={5} value={improvement}
                onChange={(e) => setImprovement(Number(e.target.value))} className="mt-2 w-full accent-navy-700" />
              <div className="flex justify-between text-[10.5px] text-slate-400"><span>+5</span><span>+40</span></div>
            </div>
            <button className="btn-teal w-full" disabled={!activeCode || sim.isPending}
              onClick={() => { sim.mutate(); qc.invalidateQueries({ queryKey: ["iv-cohort", activeCode] }); }}>
              <FlaskConical className="h-4 w-4" /> {sim.isPending ? "Running model…" : "Run simulation"}
            </button>
            <button className="btn-outline w-full" disabled={!activeCode || showCohort}
              onClick={() => setShowCohort(true)}>
              {showCohort ? "Hiding affected students" : "Show affected students"}
            </button>
          </div>

          <div className="lg:col-span-2">
            {showCohort && activeCode && !sim.data ? (
              cohort.isLoading ? <Spinner label="Loading affected students…" />
                : cohort.isError ? <ErrorBox message={(cohort.error as Error).message} />
                : (
                  <div className="max-h-[380px] overflow-y-auto">
                    <Table head={<tr><th>Student</th><th>Branch/Sem</th><th>Readiness</th><th>Primary gap</th></tr>}>
                      {(cohort.data?.students || []).slice(0, 40).map((s) => (
                        <tr key={s.student_id}>
                          <td>
                            <div className="text-[13px] font-medium text-slate-800">{s.name}</div>
                            <div className="text-[11px] text-slate-400">{s.usn}</div>
                          </td>
                          <td className="text-[12.5px] text-slate-500">{s.branch} · {s.semester}</td>
                          <td className="tabular-nums text-slate-700">{fmt1(s.readiness)}</td>
                          <td className="text-[12.5px] text-slate-500">{s.primary_gap || "—"}</td>
                        </tr>
                      ))}
                    </Table>
                  </div>
                )
            ) : sim.data ? (
              sim.data.status !== "ok" ? (
                <ErrorBox message={sim.data.message || "Simulation unavailable."} />
              ) : (
                <div className="space-y-4">
                  <p className="rounded-lg bg-navy-50 px-3.5 py-2.5 text-[12.5px] text-navy-800">
                    <TrendingUp className="mr-1.5 inline h-3.5 w-3.5" />
                    Assumption: {sim.data.assumption}
                  </p>
                  {sim.data.simulation && (
                    <>
                      <div className="grid grid-cols-3 gap-3">
                        <MiniStat label="Cohort size" value={fmt(sim.data.simulation.cohort_size)} />
                        <MiniStat label="Avg readiness delta" value={`+${fmt1(sim.data.simulation.avg_readiness_delta)}`} tone="good" />
                        <MiniStat label="Moving category" value={fmt(sim.data.simulation.students_moving_category)} />
                      </div>
                      <div className="flex items-end gap-6">
                        <div className="flex-1">
                          <div className="label">Readiness distribution</div>
                          <div className="mt-2 space-y-2">
                            <DistRow label="Baseline" data={sim.data.simulation.baseline} />
                            <DistRow label="Projected" data={sim.data.simulation.projected} />
                          </div>
                        </div>
                      </div>
                      {sim.data.simulation.movements.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {sim.data.simulation.movements.map((m) => (
                            <Badge key={`${m.from}-${m.to}`}
                              cls={m.to === "READY" ? "bg-teal-50 text-teal-700 border-teal-200" : "bg-amber-50 text-amber-700 border-amber-200"}>
                              {m.count} students: {CAT_LABEL[m.from]} → {CAT_LABEL[m.to]}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                  <p className="rounded-lg bg-amber-50 px-3.5 py-2.5 text-[12px] text-amber-800">
                    {sim.data.disclaimer}
                  </p>
                </div>
              )
            ) : (
              <div className="flex h-full min-h-[200px] flex-col items-center justify-center rounded-lg border border-dashed border-slate-200 text-center">
                <FlaskConical className="h-7 w-7 text-slate-300" />
                <p className="mt-3 text-[13px] text-slate-500">Pick an intervention and an assumed improvement,</p>
                <p className="text-[13px] text-slate-500">then run the model-based projection.</p>
              </div>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}

function MiniStat({ label, value, tone }: { label: string; value: React.ReactNode; tone?: "good" }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3.5 py-2.5">
      <div className="label !text-[10.5px]">{label}</div>
      <div className={`mt-0.5 text-lg font-semibold tabular-nums ${tone === "good" ? "text-teal-700" : "text-slate-900"}`}>{value}</div>
    </div>
  );
}

function DistRow({ label, data }: { label: string; data: Record<string, number> }) {
  const total = (data.READY || 0) + (data.NEAR_READY || 0) + (data.NEEDS_TRAINING || 0) || 1;
  return (
    <div>
      <div className="flex items-center justify-between text-[11.5px] text-slate-500">
        <span>{label}</span>
        <span className="tabular-nums">
          {data.READY || 0} ready · {data.NEAR_READY || 0} near · {data.NEEDS_TRAINING || 0} training
        </span>
      </div>
      <div className="mt-1 flex h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div className="bg-teal-500" style={{ width: `${((data.READY || 0) / total) * 100}%` }} />
        <div className="bg-amber-400" style={{ width: `${((data.NEAR_READY || 0) / total) * 100}%` }} />
        <div className="bg-rose-400" style={{ width: `${((data.NEEDS_TRAINING || 0) / total) * 100}%` }} />
      </div>
    </div>
  );
}

// Thin mutation hook kept local to this page (single-use endpoint).
function useMutationSim(code: string, improvement: number, branch: string, semester: string) {
  return useMutation({
    mutationFn: () => api<SimResp>(`/tpo/interventions/simulate`, {
      body: {
        intervention_code: code,
        improvement,
        branch: branch || null,
        semester: semester ? Number(semester) : null,
      },
    }),
  });
}

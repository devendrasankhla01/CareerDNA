import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../lib/auth";
import { api } from "../../api/client";
import { fmt, fmt1 } from "../../lib/format";
import { STAGE_META } from "../../lib/placement";
import { Badge, Bar, Card, CategoryBadge, Disclaimer, ErrorBox, Spinner, Stat, Table } from "../../components/ui";

interface DeptStudent {
  student_id: number; name: string; usn: string; semester: number;
  readiness: number | null; category: string | null;
  career_best: string | null; career_score: number | null;
  cgpa: number | null; top_gap: string | null;
  verification_coverage: number; eligible_companies: number;
  placement_status: string | null;
}
interface Resp {
  status: string; department: string;
  population: { total: number; analyzed: number; not_analyzed: number };
  readiness: { ready: number; near_ready: number; needs_training: number; average: number | null };
  verification_coverage: number; placement_eligible: number;
  pipeline: { nominated: number; shortlisted: number; interview: number; selected: number; placed: number; not_selected: number };
  top_gaps: { label: string; count: number }[];
  students: DeptStudent[];
}

const CAREER_LABEL: Record<string, string> = { FULL_STACK: "Full-Stack", DATA_ANALYST: "Data Analyst" };

export default function DeptOverview() {
  const { user } = useAuth();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["dept-overview"],
    queryFn: () => api<Resp>("/dept/overview"),
  });

  if (isLoading) return <Spinner label="Computing department analytics…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  const r = data.readiness;
  const p = data.population;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">
          Department Overview · {data.department}
        </h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          {user?.department?.name || data.department} — readiness, verification, and placement
          progress for your students only.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Stat label="Students" value={fmt(p.total)} sub={`${fmt(p.analyzed)} analyzed · ${fmt(p.not_analyzed)} pending`} />
        <Stat label="Average readiness" value={fmt1(r.average)} sub="model-estimated (0–100)" />
        <Stat label="Ready / Near-Ready" value={`${fmt(r.ready)} / ${fmt(r.near_ready)}`} tone="good"
          sub={`${fmt(r.needs_training)} need training`} />
        <Stat label="Eligible for a company" value={fmt(data.placement_eligible)}
          sub={`of ${fmt(p.analyzed)} analyzed students`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Placement readiness distribution">
          {[
            { label: "Ready", value: r.ready, cls: "bg-teal-500" },
            { label: "Near-Ready", value: r.near_ready, cls: "bg-amber-500" },
            { label: "Needs Training", value: r.needs_training, cls: "bg-rose-500" },
          ].map((x) => (
            <div key={x.label} className="mb-3">
              <div className="flex items-center justify-between text-[13px]">
                <span className="text-slate-600">{x.label}</span>
                <span className="font-semibold tabular-nums text-slate-800">{fmt(x.value)}</span>
              </div>
              <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
                <div className={`h-full rounded-full ${x.cls}`}
                  style={{ width: `${p.analyzed ? (x.value / p.analyzed) * 100 : 0}%` }} />
              </div>
            </div>
          ))}
        </Card>

        <Card title="Pipeline" subtitle="Students currently in a placement drive">
          {Object.entries(data.pipeline).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between py-1.5 text-[13px]">
              <span className="text-slate-600">{STAGE_META[k.toUpperCase()]?.label || k}</span>
              <span className="font-semibold tabular-nums text-slate-800">{fmt(v)}</span>
            </div>
          ))}
        </Card>

        <Card title="Verification coverage" subtitle="Share of evidence verified by the institution">
          <div className="flex items-center gap-4">
            <div className="text-3xl font-semibold tabular-nums text-navy-800">{fmt(data.verification_coverage)}</div>
            <div className="w-full"><Bar value={data.verification_coverage} tone={data.verification_coverage >= 70 ? "teal" : "amber"} /></div>
          </div>
          <div className="mt-4">
            <div className="mb-1.5 text-[11.5px] font-medium text-slate-500">Top skill gaps</div>
            {data.top_gaps.length === 0 ? (
              <p className="text-[12.5px] text-slate-400">No dominant gaps detected.</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {data.top_gaps.map((g) => (
                  <span key={g.label} className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11.5px] font-medium text-slate-600">
                    {g.label} · {g.count}
                  </span>
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>

      <Card title="Students" subtitle="Your department only — other departments' data is not visible to this account">
        {data.students.length === 0 ? (
          <p className="py-6 text-center text-[13px] text-slate-400">
            No students in this department yet. They appear here once imported with this branch code.
          </p>
        ) : (
          <Table head={
            <tr>
              <th>Student</th><th>Year</th><th>Readiness</th><th>Category</th>
              <th>Top gap</th><th>Verified coverage</th><th>Eligible for</th><th>Placement</th>
            </tr>
          }>
            {data.students
              .sort((a, b) => (b.readiness ?? -1) - (a.readiness ?? -1))
              .map((s) => (
                <tr key={s.student_id}>
                  <td>
                    <div className="font-medium text-slate-800">{s.name}</div>
                    <div className="text-[11.5px] text-slate-400">{s.usn}</div>
                  </td>
                  <td className="text-[12.5px] text-slate-600">Sem {s.semester}</td>
                  <td className="w-40">
                    <div className="flex items-center gap-2">
                      <div className="w-16"><Bar value={s.readiness || 0}
                        tone={(s.readiness || 0) >= 80 ? "teal" : (s.readiness || 0) >= 60 ? "navy" : "amber"} /></div>
                      <span className="text-[12.5px] font-semibold tabular-nums text-slate-700">{fmt1(s.readiness)}</span>
                    </div>
                  </td>
                  <td>{s.category ? <CategoryBadge category={s.category} /> : <span className="text-[12px] text-slate-300">—</span>}</td>
                  <td className="text-[12.5px] text-slate-600">{s.top_gap || "—"}</td>
                  <td className="tabular-nums text-slate-600">{fmt(s.verification_coverage)}</td>
                  <td className="tabular-nums text-slate-600">
                    {fmt(s.eligible_companies)} drive{s.eligible_companies === 1 ? "" : "s"}
                  </td>
                  <td>
                    {s.placement_status ? (
                      <Badge cls={STAGE_META[s.placement_status]?.cls || ""}>
                        {STAGE_META[s.placement_status]?.label || s.placement_status}
                      </Badge>
                    ) : <span className="text-[12px] text-slate-300">—</span>}
                  </td>
                </tr>
              ))}
          </Table>
        )}
      </Card>

      <Disclaimer>
        This dashboard is scoped to {data.department}. Readiness is a model-estimated signal and
        eligibility is computed against each company drive's mandatory criteria — it is not a
        placement guarantee.
      </Disclaimer>
    </div>
  );
}

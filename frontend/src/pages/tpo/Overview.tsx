import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { AlertTriangle, ArrowUpRight, Flame } from "lucide-react";
import { api } from "../../api/client";
import { CATEGORY_COLORS, fmt, fmt1, timeAgo } from "../../lib/format";
import { Bar, Card, ErrorBox, Stat, Spinner, Table } from "../../components/ui";

interface BranchMetric {
  branch: string; student_count: number; average_readiness: number;
  ready_percentage: number; near_ready_percentage: number; needs_training_percentage: number;
}
interface Deficit {
  skill: string; evaluated_count: number; below_benchmark_count: number;
  below_benchmark_percentage: number; average_score: number; average_gap: number;
  average_readiness: number;
}
interface HeatCell {
  branch: string; skill: string; evaluated_count: number;
  below_benchmark_count: number; below_benchmark_percentage: number;
  average_score: number; average_readiness: number;
}
interface OverviewResp {
  status: string;
  message?: string;
  population: { total_students: number; analyzed_students: number; not_analyzed: number };
  readiness: {
    ready: number; near_ready: number; needs_training: number;
    ready_percentage: number | null; near_ready_percentage: number | null;
    needs_training_percentage: number | null; average_readiness: number | null;
  };
  quality: { high_trust: number; partial_trust: number; low_trust: number; coverage_note: string };
  branch_metrics: BranchMetric[];
  top_skill_deficits: Deficit[];
  vulnerable_students: number;
  vulnerable_threshold: number;
}
interface SkillsResp { status: string; deficits: Deficit[]; heatmap: HeatCell[]; skills: string[] }
interface VulnerableResp { status: string; cohorts: { label: string; count: number; average_readiness: number }[] }

const DIST = [
  { key: "ready", label: "Ready", cat: "READY" },
  { key: "near_ready", label: "Near-Ready", cat: "NEAR_READY" },
  { key: "needs_training", label: "Needs Training", cat: "NEEDS_TRAINING" },
] as const;

export default function Overview() {
  const navigate = useNavigate();
  const [branch, setBranch] = useState("");
  const [semester, setSemester] = useState("");

  const ov = useQuery({
    queryKey: ["tpo-overview", branch, semester],
    queryFn: () => api<OverviewResp>(
      `/tpo/overview${branch ? `?branch=${branch}` : ""}${semester ? (branch ? "&" : "?") + `semester=${semester}` : ""}`
    ),
  });
  const skills = useQuery({
    queryKey: ["tpo-skills", branch, semester],
    queryFn: () => api<SkillsResp>(
      `/tpo/skills${branch ? `?branch=${branch}` : ""}${semester ? (branch ? "&" : "?") + `semester=${semester}` : ""}`
    ),
  });
  const vulnerable = useQuery({
    queryKey: ["tpo-vulnerable", branch],
    queryFn: () => api<VulnerableResp>(`/tpo/cohorts/vulnerable${branch ? `?branch=${branch}` : ""}`),
  });

  const branchOptions = useMemo(
    () => (ov.data && !branch ? ov.data.branch_metrics.map((b) => b.branch) : []),
    [ov.data, branch]
  );
  const data = ov.data;
  const cellMap = useMemo(() => {
    const m = new Map<string, HeatCell>();
    (skills.data?.heatmap || []).forEach((c) => m.set(`${c.branch}|${c.skill}`, c));
    return m;
  }, [skills.data]);

  if (ov.isLoading || skills.isLoading) return <Spinner label="Computing institutional analytics…" />;
  if (ov.isError) return <ErrorBox message={(ov.error as Error).message} onRetry={() => ov.refetch()} />;
  if (!data) return null;
  if (data.status === "model_unavailable") {
    return <ErrorBox message={data.message || "Readiness model is not deployed."} />;
  }

  const dist = DIST.map((d) => ({ ...d, value: data.readiness[d.key] }));
  const analyzed = data.population.analyzed_students;
  const q = data.quality;
  const qTotal = q.high_trust + q.partial_trust + q.low_trust || 1;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Institutional Overview</h1>
          <p className="mt-0.5 text-[13px] text-slate-500">
            Placement readiness across the analyzed student cohort. All figures are computed from
            current verified-profile analyses.
          </p>
        </div>
        <div className="flex gap-2">
          <select className="input !w-auto" value={branch} onChange={(e) => setBranch(e.target.value)}>
            <option value="">All branches</option>
            {(branchOptions.length ? branchOptions : data.branch_metrics.map((b) => b.branch)).map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
          <select className="input !w-auto" value={semester} onChange={(e) => setSemester(e.target.value)}>
            <option value="">All semesters</option>
            {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => <option key={n} value={n}>Semester {n}</option>)}
          </select>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Stat label="Analyzed students" value={fmt(analyzed)}
          sub={`${fmt(data.population.total_students)} active · ${fmt(data.population.not_analyzed)} pending analysis`} />
        <Stat label="Average placement readiness" value={fmt1(data.readiness.average_readiness)} sub="Model-estimated score (0–100)" />
        <Stat label="Ready" value={fmt1(data.readiness.ready_percentage)} tone="good"
          sub={`${fmt(data.readiness.ready)} of ${fmt(analyzed)} students`} />
        <Stat label="Vulnerable (< 60)" value={fmt(data.vulnerable_students)} tone={data.vulnerable_students > 0 ? "bad" : "neutral"}
          sub={`Threshold: below ${data.vulnerable_threshold}`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Readiness distribution" subtitle={`Across ${fmt(analyzed)} analyzed students`}>
          <div className="flex items-center">
            <div className="h-44 w-1/2">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={dist} dataKey="value" nameKey="label" innerRadius={48} outerRadius={72}
                    paddingAngle={2} strokeWidth={0}>
                    {dist.map((d) => <Cell key={d.cat} fill={CATEGORY_COLORS[d.cat]} />)}
                  </Pie>
                  <Tooltip formatter={(v: any, name: any) => [`${fmt(Number(v))} students`, name]} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <ul className="w-1/2 space-y-3 pl-2">
              {dist.map((d) => (
                <li key={d.cat} className="flex items-center gap-2.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: CATEGORY_COLORS[d.cat] }} />
                  <span className="text-[13px] text-slate-600">{d.label}</span>
                  <span className="ml-auto text-[13px] font-semibold tabular-nums text-slate-800">
                    {fmt(d.value)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </Card>

        <Card title="Verification quality" subtitle={q.coverage_note}>
          <div className="flex h-3 w-full overflow-hidden rounded-full bg-slate-100">
            <div className="bg-teal-500" style={{ width: `${(q.high_trust / qTotal) * 100}%` }} />
            <div className="bg-amber-400" style={{ width: `${(q.partial_trust / qTotal) * 100}%` }} />
            <div className="bg-rose-400" style={{ width: `${(q.low_trust / qTotal) * 100}%` }} />
          </div>
          <ul className="mt-4 space-y-2.5">
            <li className="flex items-center gap-2.5 text-[13px]">
              <span className="h-2.5 w-2.5 rounded-full bg-teal-500" />
              <span className="text-slate-600">High profile trust (≥ 75)</span>
              <span className="ml-auto font-semibold tabular-nums text-slate-800">{fmt(q.high_trust)}</span>
            </li>
            <li className="flex items-center gap-2.5 text-[13px]">
              <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
              <span className="text-slate-600">Partial trust (40–74)</span>
              <span className="ml-auto font-semibold tabular-nums text-slate-800">{fmt(q.partial_trust)}</span>
            </li>
            <li className="flex items-center gap-2.5 text-[13px]">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-400" />
              <span className="text-slate-600">Low trust (&lt; 40)</span>
              <span className="ml-auto font-semibold tabular-nums text-slate-800">{fmt(q.low_trust)}</span>
            </li>
          </ul>
          <p className="mt-4 text-[11.5px] leading-relaxed text-slate-400">
            Profile trust reflects the share of evidence verified by the institution. Low-trust
            students are prioritised in the faculty verification queue.
          </p>
        </Card>

        <Card title="Vulnerable cohorts" subtitle={`Cohorts with readiness below ${data.vulnerable_threshold}`}>
          {vulnerable.isLoading ? (
            <Spinner label="Loading…" />
          ) : (vulnerable.data?.cohorts || []).length === 0 ? (
            <p className="text-[13px] text-slate-400">No cohorts below the vulnerable threshold in this view.</p>
          ) : (
            <ul className="space-y-3">
              {(vulnerable.data!.cohorts.slice(0, 6)).map((c) => (
                <li key={c.label}>
                  <div className="flex items-center justify-between text-[13px]">
                    <span className="flex items-center gap-1.5 text-slate-700">
                      <AlertTriangle className="h-3.5 w-3.5 text-rose-500" />{c.label}
                    </span>
                    <span className="font-semibold tabular-nums text-slate-800">{c.count}</span>
                  </div>
                  <div className="mt-1.5"><Bar value={100 - c.average_readiness} max={100} tone="rose" /></div>
                  <div className="mt-0.5 text-[11px] text-slate-400">avg readiness {fmt1(c.average_readiness)}</div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="Branch × skill deficit heatmap"
        subtitle="Share of students below the skill benchmark in each cell · click a cell to drill down"
        className="overflow-x-auto">
        <div className="min-w-[760px]">
          <div className="grid" style={{ gridTemplateColumns: `90px repeat(${skills.data?.skills.length || 8}, minmax(72px, 1fr))` }}>
            <div />
            {(skills.data?.skills || []).map((sk) => (
              <div key={sk} className="pb-2 text-center text-[11px] font-semibold tracking-wide text-slate-500">{sk}</div>
            ))}
            {data.branch_metrics.map((b) => (
              <FragmentRow key={b.branch} branch={b.branch} skillsList={skills.data?.skills || []} cellMap={cellMap}
                onCell={(sk) => navigate(`/tpo/skills?skill=${sk}&branch=${b.branch}`)} />
            ))}
          </div>
        </div>
        <div className="mt-4 flex items-center gap-2 text-[11.5px] text-slate-500">
          <span>0% below benchmark</span>
          <div className="h-2 w-36 rounded-full" style={{
            background: "linear-gradient(to right, rgba(30,64,124,0.06), rgba(30,64,124,0.8))",
          }} />
          <span>100% below benchmark</span>
          <span className="ml-4 text-slate-400">Cells need at least 5 evaluated students; blank = insufficient data.</span>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Branch comparison">
          <Table head={
            <tr><th>Branch</th><th>Students</th><th>Avg readiness</th><th>Ready</th><th>Needs Training</th></tr>
          }>
            {data.branch_metrics.map((b) => (
              <tr key={b.branch}>
                <td className="font-medium text-slate-800">{b.branch}</td>
                <td className="tabular-nums text-slate-600">{fmt(b.student_count)}</td>
                <td className="w-48">
                  <div className="flex items-center gap-2">
                    <div className="w-24"><Bar value={b.average_readiness} tone={b.average_readiness >= 70 ? "teal" : b.average_readiness >= 60 ? "navy" : "amber"} /></div>
                    <span className="text-[12.5px] font-semibold tabular-nums text-slate-700">{fmt1(b.average_readiness)}</span>
                  </div>
                </td>
                <td className="tabular-nums text-teal-700">{fmt(b.ready_percentage)}%</td>
                <td className="tabular-nums text-rose-600">{fmt(b.needs_training_percentage)}%</td>
              </tr>
            ))}
          </Table>
        </Card>

        <Card title="Top skill deficits"
          subtitle="Skills with the largest share of students below benchmark"
          actions={<button className="flex items-center gap-1 text-[12.5px] font-medium text-navy-700 hover:underline"
            onClick={() => navigate("/tpo/skills")}>All skills <ArrowUpRight className="h-3.5 w-3.5" /></button>}>
          <ul className="space-y-3.5">
            {(data.top_skill_deficits || []).map((d, i) => (
              <li key={d.skill}>
                <div className="flex items-center gap-2 text-[13px]">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 text-[11px] font-semibold text-slate-500">{i + 1}</span>
                  <span className="font-medium text-slate-800">{d.skill}</span>
                  <span className="ml-auto tabular-nums text-slate-500">
                    {fmt(d.below_benchmark_percentage)}% below benchmark · n={fmt(d.evaluated_count)}
                  </span>
                </div>
                <div className="mt-1.5"><Bar value={d.below_benchmark_percentage} tone={d.below_benchmark_percentage >= 80 ? "rose" : d.below_benchmark_percentage >= 60 ? "amber" : "navy"} /></div>
                <div className="mt-0.5 text-[11px] text-slate-400">
                  avg score {fmt1(d.average_score)} · avg gap {fmt1(d.average_gap)} pts · avg readiness {fmt1(d.average_readiness)}
                </div>
              </li>
            ))}
            {(data.top_skill_deficits || []).length === 0 && (
              <p className="text-[13px] text-slate-400">No skill evaluated enough students for deficit analysis.</p>
            )}
          </ul>
        </Card>
      </div>
    </div>
  );
}

function FragmentRow({ branch, skillsList, cellMap, onCell }: {
  branch: string; skillsList: string[];
  cellMap: Map<string, HeatCell>; onCell: (skill: string) => void;
}) {
  return (
    <>
      <div className="flex items-center pr-3 text-[12.5px] font-semibold text-slate-700">{branch}</div>
      {skillsList.map((sk) => {
        const c = cellMap.get(`${branch}|${sk}`);
        if (!c) return <div key={sk} className="flex items-center justify-center border-l border-slate-100 text-[11px] text-slate-300">—</div>;
        const pct = c.below_benchmark_percentage;
        return (
          <button
            key={sk}
            onClick={() => onCell(sk)}
            title={`${branch} · ${sk}: ${fmt(c.below_benchmark_percentage)}% of ${fmt(c.evaluated_count)} students below benchmark (avg ${fmt1(c.average_score)}) — click to drill down`}
            className="m-0.5 flex flex-col items-center rounded-md py-1.5 transition hover:ring-2 hover:ring-navy-400"
            style={{
              backgroundColor: `rgba(30, 64, 124, ${0.06 + (pct / 100) * 0.72})`,
              color: pct > 55 ? "#fff" : "#334155",
            }}
          >
            <span className="text-[12px] font-semibold tabular-nums leading-tight">{fmt(pct)}%</span>
            <span className="text-[10px] opacity-75 tabular-nums">n={fmt(c.evaluated_count)}</span>
          </button>
        );
      })}
    </>
  );
}

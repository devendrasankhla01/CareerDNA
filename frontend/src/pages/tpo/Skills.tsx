import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Crosshair } from "lucide-react";
import { api } from "../../api/client";
import { fmt, fmt1 } from "../../lib/format";
import { Bar, Card, CategoryBadge, ErrorBox, Spinner, Table } from "../../components/ui";

interface Deficit {
  skill: string; feature: string; evaluated_count: number; below_benchmark_count: number;
  below_benchmark_percentage: number; average_score: number; average_gap: number;
  average_readiness: number;
}
interface SkillsResp { status: string; deficits: Deficit[]; heatmap: unknown[]; skills: string[] }
interface DrillResp {
  status: string; skill: string; branch: string | null; benchmark: number | null;
  count: number; average_score: number | null; average_readiness: number | null;
  students: {
    student_id: number; name: string; usn: string; branch: string; semester: number;
    score: number; gap: number; readiness: number; category: string;
  }[];
}

export default function Skills() {
  const [params, setParams] = useSearchParams();
  const [branch, setBranch] = useState<string>(params.get("branch") || "");
  const [semester, setSemester] = useState<string>("");

  const skills = useQuery({
    queryKey: ["tpo-skills", branch, semester],
    queryFn: () => api<SkillsResp>(
      `/tpo/skills${branch ? `?branch=${branch}` : ""}${semester ? (branch ? "&" : "?") + `semester=${semester}` : ""}`
    ),
  });

  const selected = params.get("skill") || skills.data?.deficits[0]?.skill || skills.data?.skills[0] || "";
  const drill = useQuery({
    queryKey: ["skill-drill", selected, branch],
    queryFn: () => api<DrillResp>(`/tpo/skills/${selected}/drilldown${branch ? `?branch=${branch}` : ""}`),
    enabled: !!selected,
  });

  const selectSkill = (sk: string) => {
    const next = new URLSearchParams(params);
    next.set("skill", sk);
    setParams(next);
  };

  const branchOptions = useMemo(() => {
    const set = new Set<string>();
    (drill.data?.students || []).forEach((s) => set.add(s.branch));
    if (branch) set.add(branch);
    return [...set];
  }, [drill.data, branch]);

  if (skills.isLoading) return <Spinner label="Computing skill deficits…" />;
  if (skills.isError) return <ErrorBox message={(skills.error as Error).message} onRetry={() => skills.refetch()} />;
  if (!skills.data) return null;

  const deficits = skills.data.deficits;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Skill Deficits</h1>
          <p className="mt-0.5 text-[13px] text-slate-500">
            Benchmarks are per-skill institutional targets. A “below benchmark” student scores
            under that target on the latest verified-profile analysis.
          </p>
        </div>
        <div className="flex gap-2">
          <select className="input !w-auto" value={branch} onChange={(e) => setBranch(e.target.value)}>
            <option value="">All branches</option>
            {branchOptions.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
          <select className="input !w-auto" value={semester} onChange={(e) => setSemester(e.target.value)}>
            <option value="">All semesters</option>
            {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => <option key={n} value={n}>Semester {n}</option>)}
          </select>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card title="Ranked deficits" subtitle={`${deficits.length} skills evaluated (cells with ≥ 5 students)`}
          className="lg:col-span-2">
          {deficits.length === 0 ? (
            <p className="text-[13px] text-slate-400">Not enough evaluated students in this filter.</p>
          ) : (
            <ol className="space-y-1">
              {deficits.map((d, i) => {
                const active = d.skill === selected;
                return (
                  <li key={d.skill}>
                    <button
                      onClick={() => selectSkill(d.skill)}
                      className={`w-full rounded-lg border px-3.5 py-2.5 text-left transition ${
                        active ? "border-navy-300 bg-navy-50" : "border-transparent hover:bg-slate-50"
                      }`}
                    >
                      <div className="flex items-center gap-2 text-[13px]">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 text-[11px] font-semibold text-slate-500">{i + 1}</span>
                        <span className={`font-medium ${active ? "text-navy-800" : "text-slate-800"}`}>{d.skill}</span>
                        <span className="ml-auto tabular-nums text-slate-500">{fmt(d.below_benchmark_percentage)}%</span>
                      </div>
                      <div className="mt-1.5"><Bar value={d.below_benchmark_percentage}
                        tone={d.below_benchmark_percentage >= 80 ? "rose" : d.below_benchmark_percentage >= 60 ? "amber" : "navy"} /></div>
                      <div className="mt-0.5 text-[11px] text-slate-400">
                        {fmt(d.below_benchmark_count)} of {fmt(d.evaluated_count)} below benchmark · avg gap {fmt1(d.average_gap)} pts
                      </div>
                    </button>
                  </li>
                );
              })}
            </ol>
          )}
        </Card>

        <Card
          className="lg:col-span-3"
          title={selected ? `${selected} — students below benchmark` : "Skill drill-down"}
          subtitle={drill.data
            ? `Benchmark ${fmt1(drill.data.benchmark)} · ${fmt(drill.data.count)} students${branch ? ` in ${branch}` : ""}`
            : "Select a skill to inspect the affected students"}
          actions={<Crosshair className="h-4 w-4 text-slate-400" />}
        >
          {drill.isLoading ? (
            <Spinner label="Loading students…" />
          ) : drill.isError ? (
            <ErrorBox message={(drill.error as Error).message} onRetry={() => drill.refetch()} />
          ) : !drill.data || drill.data.count === 0 ? (
            <p className="text-[13px] text-slate-400">No students below benchmark for this skill in the current filter.</p>
          ) : (
            <>
              <div className="mb-4 grid grid-cols-3 gap-3">
                <div className="rounded-lg bg-slate-50 px-3.5 py-2.5">
                  <div className="label !text-[10.5px]">Students below</div>
                  <div className="mt-0.5 text-lg font-semibold tabular-nums text-slate-900">{fmt(drill.data.count)}</div>
                </div>
                <div className="rounded-lg bg-slate-50 px-3.5 py-2.5">
                  <div className="label !text-[10.5px]">Avg skill score</div>
                  <div className="mt-0.5 text-lg font-semibold tabular-nums text-slate-900">{fmt1(drill.data.average_score)}</div>
                </div>
                <div className="rounded-lg bg-slate-50 px-3.5 py-2.5">
                  <div className="label !text-[10.5px]">Avg readiness</div>
                  <div className="mt-0.5 text-lg font-semibold tabular-nums text-slate-900">{fmt1(drill.data.average_readiness)}</div>
                </div>
              </div>
              <Table head={
                <tr><th>Student</th><th>Branch / Sem</th><th>Skill score</th><th>Gap</th><th>Readiness</th><th>Category</th></tr>
              }>
                {drill.data.students.slice(0, 30).map((s) => (
                  <tr key={s.student_id}>
                    <td>
                      <div className="text-[13px] font-medium text-slate-800">{s.name}</div>
                      <div className="text-[11px] text-slate-400">{s.usn}</div>
                    </td>
                    <td className="text-[12.5px] text-slate-500">{s.branch} · {s.semester}</td>
                    <td className="tabular-nums text-slate-700">{fmt1(s.score)}</td>
                    <td className="tabular-nums text-rose-600">−{fmt1(s.gap)}</td>
                    <td className="tabular-nums text-slate-700">{fmt1(s.readiness)}</td>
                    <td><CategoryBadge category={s.category} /></td>
                  </tr>
                ))}
              </Table>
              {drill.data.count > 30 && (
                <p className="mt-2 text-[11.5px] text-slate-400">Showing the 30 most affected students (lowest scores first).</p>
              )}
            </>
          )}
        </Card>
      </div>
    </div>
  );
}

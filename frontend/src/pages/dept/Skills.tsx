import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { fmt, fmt1 } from "../../lib/format";
import { skillLabel } from "../../lib/placement";
import { Bar, Card, Disclaimer, ErrorBox, Spinner, Table } from "../../components/ui";

interface Deficit {
  skill: string; evaluated_count: number; below_benchmark_count: number;
  below_benchmark_percentage: number; average_score: number; average_gap: number;
}
interface HeatCell { semester: string; skill: string; n: number; below_benchmark_count: number; below_benchmark_percentage: number }
interface Resp { status: string; deficits: Deficit[]; heatmap: HeatCell[]; skills: string[] }

export default function DeptSkills() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["dept-skills"],
    queryFn: () => api<Resp>("/dept/skills"),
  });

  if (isLoading) return <Spinner label="Computing department skill gaps…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  const sems = [...new Set(data.heatmap.map((h) => h.semester))].sort();
  const cellMap = new Map(data.heatmap.map((h) => [`${h.semester}|${h.skill}`, h]));

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Skill Gaps</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          Where your department's students fall below institutional skill benchmarks — computed
          from verified/assessed scores only.
        </p>
      </header>

      <Card title="Largest skill deficits">
        {data.deficits.length === 0 ? (
          <p className="py-6 text-center text-[13px] text-slate-400">Not enough evaluated students for deficit analysis.</p>
        ) : (
          <ul className="space-y-3.5">
            {data.deficits.map((d, i) => (
              <li key={d.skill}>
                <div className="flex items-center gap-2 text-[13px]">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 text-[11px] font-semibold text-slate-500">{i + 1}</span>
                  <span className="font-medium text-slate-800">{skillLabel(d.skill)}</span>
                  <span className="ml-auto tabular-nums text-slate-500">
                    {fmt(d.below_benchmark_percentage)}% below benchmark · n={fmt(d.evaluated_count)}
                  </span>
                </div>
                <div className="mt-1.5">
                  <Bar value={d.below_benchmark_percentage} tone={d.below_benchmark_percentage >= 80 ? "rose" : d.below_benchmark_percentage >= 60 ? "amber" : "navy"} />
                </div>
                <div className="mt-0.5 text-[11px] text-slate-400">
                  avg score {fmt1(d.average_score)} · avg gap {fmt1(d.average_gap)} pts
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {data.heatmap.length > 0 && (
        <Card title="Semester × skill" subtitle="Share of students below benchmark · blank cells have < 3 evaluated students">
          <div className="overflow-x-auto">
            <div className="min-w-[680px]">
              <div className="grid" style={{ gridTemplateColumns: `80px repeat(${data.skills.length}, minmax(64px, 1fr))` }}>
                <div />
                {data.skills.map((sk) => (
                  <div key={sk} className="pb-2 text-center text-[11px] font-semibold tracking-wide text-slate-500">
                    {skillLabel(sk)}
                  </div>
                ))}
                {sems.map((sem) => (
                  <SemRow key={sem} sem={sem} skills={data.skills} cellMap={cellMap} />
                ))}
              </div>
            </div>
          </div>
        </Card>
      )}

      <Disclaimer>
        Deficits highlight where upskilling would help most. They are descriptive, not a ranking
        of individual students — no student leaderboard is produced.
      </Disclaimer>
    </div>
  );
}

function SemRow({ sem, skills, cellMap }: { sem: string; skills: string[]; cellMap: Map<string, HeatCell> }) {
  return (
    <>
      <div className="flex items-center pr-3 text-[12.5px] font-semibold text-slate-700">Sem {sem}</div>
      {skills.map((sk) => {
        const c = cellMap.get(`${sem}|${sk}`);
        if (!c) return <div key={sk} className="flex items-center justify-center border-l border-slate-100 text-[11px] text-slate-300">—</div>;
        const pct = c.below_benchmark_percentage;
        return (
          <div key={sk} title={`Sem ${sem} · ${sk}: ${pct}% of ${c.n} students below benchmark`}
            className="m-0.5 flex flex-col items-center rounded-md py-1.5"
            style={{
              backgroundColor: `rgba(30, 64, 124, ${0.06 + (pct / 100) * 0.72})`,
              color: pct > 55 ? "#fff" : "#334155",
            }}>
            <span className="text-[12px] font-semibold tabular-nums">{fmt(pct)}%</span>
            <span className="text-[10px] opacity-75 tabular-nums">n={c.n}</span>
          </div>
        );
      })}
    </>
  );
}

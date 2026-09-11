import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { fmt, fmt1 } from "../../lib/format";
import { skillLabel } from "../../lib/placement";
import { Bar, Card, ErrorBox, Spinner, Stat, Table } from "../../components/ui";

interface Academic {
  avg_cgpa: number | null; avg_tenth: number | null; avg_twelfth: number | null;
  avg_backlogs: number | null; records: number;
}
interface Resp {
  status: string;
  academic: Academic;
  skills: Record<string, number>;
  readiness_distribution: { ready: number; near_ready: number; needs_training: number };
  career_alignment: Record<string, number>;
}

const CAREER_LABEL: Record<string, string> = { FULL_STACK: "Full-Stack Developer", DATA_ANALYST: "Data Analyst" };

export default function DeptPerformance() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["dept-performance"],
    queryFn: () => api<Resp>("/dept/performance"),
  });

  if (isLoading) return <Spinner label="Computing department performance…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  const a = data.academic;
  const skills = Object.entries(data.skills).sort((x, y) => y[1] - x[1]);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Performance</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          Academic and assessed-skill averages for your department. Model outputs (readiness) are
          shown for monitoring — they cannot be edited from this dashboard.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Avg CGPA" value={fmt1(a.avg_cgpa)} sub={`${a.records} academic records`} />
        <Stat label="Avg 10th %" value={fmt1(a.avg_tenth)} />
        <Stat label="Avg 12th %" value={fmt1(a.avg_twelfth)} />
        <Stat label="Avg backlogs" value={fmt1(a.avg_backlogs)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Assessed skill averages" subtitle="Verified/institution-assessed scores only (min 3 students)">
          {skills.length === 0 ? (
            <p className="py-6 text-center text-[13px] text-slate-400">No assessed skills with enough coverage yet.</p>
          ) : (
            <Table head={<tr><th>Skill</th><th>Average score</th></tr>}>
              {skills.map(([code, v]) => (
                <tr key={code}>
                  <td className="font-medium text-slate-800">{skillLabel(code)}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="w-32"><Bar value={v} tone={v >= 70 ? "teal" : v >= 55 ? "navy" : "amber"} /></div>
                      <span className="text-[12.5px] font-semibold tabular-nums text-slate-700">{fmt1(v)}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </Table>
          )}
        </Card>

        <div className="flex flex-col gap-4">
          <Card title="Readiness distribution">
            <div className="space-y-2.5">
              {[
                { label: "Ready", value: data.readiness_distribution.ready, tone: "good" as const },
                { label: "Near-Ready", value: data.readiness_distribution.near_ready, tone: "neutral" as const },
                { label: "Needs Training", value: data.readiness_distribution.needs_training, tone: "bad" as const },
              ].map((x) => (
                <div key={x.label} className="flex items-center justify-between text-[13px]">
                  <span className="text-slate-600">{x.label}</span>
                  <span className="font-semibold tabular-nums text-slate-800">{fmt(x.value)}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card title="Career-track alignment" subtitle="Students whose best career match is each track">
            {Object.keys(data.career_alignment).length === 0 ? (
              <p className="text-[13px] text-slate-400">No career matches computed yet.</p>
            ) : (
              <div className="space-y-2.5">
                {Object.entries(data.career_alignment).map(([code, n]) => (
                  <div key={code} className="flex items-center justify-between text-[13px]">
                    <span className="text-slate-600">{CAREER_LABEL[code] || code}</span>
                    <span className="font-semibold tabular-nums text-slate-800">{fmt(n)} students</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

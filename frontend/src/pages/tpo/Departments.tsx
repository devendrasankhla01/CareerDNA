import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Building2 } from "lucide-react";
import { api } from "../../api/client";
import { fmt, fmt1 } from "../../lib/format";
import { Bar, Card, ErrorBox, Spinner, Stat, Table } from "../../components/ui";

interface Dept {
  code: string; name: string; students: number; analyzed: number;
  average_readiness: number | null; ready_pct: number | null;
  needs_training_pct: number | null; placed: number; in_process: number;
}
interface Resp { status: string; departments: Dept[] }

export default function TpoDepartments() {
  const navigate = useNavigate();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["tpo-departments"],
    queryFn: () => api<Resp>("/tpo/departments"),
  });

  if (isLoading) return <Spinner label="Loading departments…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  const d = data.departments;
  const totalStudents = d.reduce((s, x) => s + x.students, 0);
  const totalPlaced = d.reduce((s, x) => s + x.placed, 0);
  const totalProcess = d.reduce((s, x) => s + x.in_process, 0);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Departments</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          Cross-department readiness and placement comparison. Each department also gets its own
          scoped analytics dashboard.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Departments" value={fmt(d.length)} sub="active academic departments" />
        <Stat label="Students" value={fmt(totalStudents)} sub="active students" />
        <Stat label="In placement process" value={fmt(totalProcess)} tone="neutral"
          sub="nominated → selected (not yet placed)" />
        <Stat label="Placed (confirmed)" value={fmt(totalPlaced)} tone="good"
          sub="TPO-confirmed placements" />
      </div>

      <Card title="Department comparison">
        {d.length === 0 ? (
          <p className="py-6 text-center text-[13px] text-slate-400">No departments configured.</p>
        ) : (
          <Table head={
            <tr>
              <th>Department</th><th>Students</th><th>Analyzed</th><th>Avg readiness</th>
              <th>Ready</th><th>Needs Training</th><th>In process</th><th>Placed</th>
            </tr>
          }>
            {d.map((x) => (
              <tr key={x.code} className="cursor-pointer hover:bg-slate-50/60"
                onClick={() => navigate("/department")}>
                <td>
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-navy-50 text-navy-700">
                      <Building2 className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="font-medium text-slate-800">{x.code}</div>
                      <div className="text-[11.5px] text-slate-400">{x.name}</div>
                    </div>
                  </div>
                </td>
                <td className="tabular-nums text-slate-600">{fmt(x.students)}</td>
                <td className="tabular-nums text-slate-600">{fmt(x.analyzed)}</td>
                <td>
                  <div className="flex items-center gap-2">
                    <div className="w-24"><Bar value={x.average_readiness || 0}
                      tone={(x.average_readiness || 0) >= 70 ? "teal" : (x.average_readiness || 0) >= 60 ? "navy" : "amber"} /></div>
                    <span className="text-[12.5px] font-semibold tabular-nums text-slate-700">{fmt1(x.average_readiness)}</span>
                  </div>
                </td>
                <td className="tabular-nums text-teal-700">{x.ready_pct != null ? `${fmt(x.ready_pct)}%` : "—"}</td>
                <td className="tabular-nums text-rose-600">{x.needs_training_pct != null ? `${fmt(x.needs_training_pct)}%` : "—"}</td>
                <td className="tabular-nums text-navy-700">{fmt(x.in_process)}</td>
                <td className="tabular-nums text-teal-700">{fmt(x.placed)}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}

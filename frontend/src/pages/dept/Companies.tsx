import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { fmt, fmt1 } from "../../lib/format";
import { Badge, Card, Disclaimer, ErrorBox, Spinner, Stat, Table } from "../../components/ui";

interface DriveElig {
  drive_id: number; company: string; role: string; title: string; status: string;
  drive_date: string | null; analyzed: number;
  eligible: number; almost_eligible: number; not_eligible: number; one_actionable_gap: number;
  top_blocker: string | null; top_blocker_count: number;
}
interface Resp { status: string; drives: DriveElig[] }

export default function DeptCompanies() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["dept-companies"],
    queryFn: () => api<Resp>("/dept/companies"),
  });

  if (isLoading) return <Spinner label="Evaluating your students against open drives…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  const totalEligible = data.drives.reduce((s, d) => s + d.eligible, 0);
  const totalAlmost = data.drives.reduce((s, d) => s + d.almost_eligible, 0);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Company Eligibility</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          For each open drive, how many of your students are eligible, how many are
          <span className="font-medium"> almost eligible</span> (a small, improvable gap), and the
          most common blocker.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <Stat label="Open drives evaluated" value={fmt(data.drives.length)} />
        <Stat label="Eligible (student × drive)" value={fmt(totalEligible)} tone="good"
          sub="meet every mandatory requirement" />
        <Stat label="Almost eligible" value={fmt(totalAlmost)} sub="1–2 improvable gaps remaining" />
      </div>

      <Card>
        {data.drives.length === 0 ? (
          <p className="py-6 text-center text-[13px] text-slate-400">No open or draft drives yet.</p>
        ) : (
          <Table head={
            <tr>
              <th>Drive</th><th>Company</th><th>Status</th><th>Analyzed</th>
              <th>Eligible</th><th>Almost</th><th>Not eligible</th><th>Top blocker</th>
            </tr>
          }>
            {data.drives.map((d) => (
              <tr key={d.drive_id}>
                <td>
                  <div className="font-medium text-slate-800">{d.role}</div>
                  <div className="text-[11.5px] text-slate-400">
                    {d.title}{d.drive_date ? ` · ${d.drive_date}` : ""}
                  </div>
                </td>
                <td className="text-[13px] text-slate-700">{d.company}</td>
                <td><Badge cls={d.status === "OPEN"
                  ? "bg-teal-50 text-teal-700 border-teal-200"
                  : "bg-slate-100 text-slate-500 border-slate-200"}>{d.status}</Badge></td>
                <td className="tabular-nums text-slate-600">{fmt(d.analyzed)}</td>
                <td className="font-semibold tabular-nums text-teal-700">{fmt(d.eligible)}</td>
                <td>
                  <span className="font-semibold tabular-nums text-amber-700">{fmt(d.almost_eligible)}</span>
                  {d.one_actionable_gap > 0 && (
                    <div className="text-[11px] text-slate-400">{fmt(d.one_actionable_gap)} with just one gap</div>
                  )}
                </td>
                <td className="tabular-nums text-rose-600">{fmt(d.not_eligible)}</td>
                <td>
                  {d.top_blocker ? (
                    <span className="text-[12.5px] text-slate-600">
                      {d.top_blocker}
                      <span className="ml-1 text-[11px] text-slate-400">({fmt(d.top_blocker_count)})</span>
                    </span>
                  ) : <span className="text-[12px] text-slate-300">—</span>}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Disclaimer>
        Eligibility is mandatory: a student fails the drive if any mandatory requirement is unmet,
        and no score can compensate for that. "Almost eligible" students are the highest-leverage
        upskilling targets.
      </Disclaimer>
    </div>
  );
}

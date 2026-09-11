import { useQuery } from "@tanstack/react-query";
import { Handshake } from "lucide-react";
import { api } from "../../api/client";
import { timeAgo } from "../../lib/format";
import { Badge, Card, Disclaimer, ErrorBox, Spinner, Table } from "../../components/ui";

interface Row {
  drive: string; role: string; name: string | null; usn: string | null; branch: string | null;
  status: string; selected_at: string | null; confirmed: boolean; confirmed_at: string | null;
}
interface Resp { status: string; rows: Row[] }

export default function CompanySelections() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["company-selections"],
    queryFn: () => api<Resp>("/company/selections"),
  });

  if (isLoading) return <Spinner label="Loading selections…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Selections</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          Candidates you selected (or did not select), and whether the TPO has confirmed the
          official placement.
        </p>
      </header>

      <Card>
        {data.rows.length === 0 ? (
          <div className="flex flex-col items-center py-10 text-center">
            <Handshake className="h-8 w-8 text-slate-300" />
            <div className="mt-3 text-sm font-medium text-slate-600">No selections yet</div>
            <div className="mt-1 text-[12.5px] text-slate-400">Select candidates from your drives and they will appear here.</div>
          </div>
        ) : (
          <Table head={
            <tr>
              <th>Candidate</th><th>Branch</th><th>Drive</th><th>Result</th>
              <th>Selected</th><th>Institution record</th>
            </tr>
          }>
            {data.rows.map((r, i) => (
              <tr key={i}>
                <td>
                  <div className="font-medium text-slate-800">{r.name || "—"}</div>
                  <div className="text-[11.5px] text-slate-400">{r.usn}</div>
                </td>
                <td className="text-[12.5px] text-slate-600">{r.branch || "—"}</td>
                <td>
                  <div className="text-[13px] text-slate-700">{r.role}</div>
                  <div className="text-[11.5px] text-slate-400">{r.drive}</div>
                </td>
                <td>
                  <Badge cls={r.status === "NOT_SELECTED"
                    ? "bg-rose-50 text-rose-700 border-rose-200"
                    : r.status === "PLACED"
                      ? "bg-teal-50 text-teal-700 border-teal-200"
                      : "bg-amber-50 text-amber-700 border-amber-200"}>
                    {r.status === "NOT_SELECTED" ? "Not Selected" : r.status === "PLACED" ? "Placed" : "Selected"}
                  </Badge>
                </td>
                <td className="text-[12px] text-slate-500">{r.selected_at ? timeAgo(r.selected_at) : "—"}</td>
                <td>
                  {r.status === "NOT_SELECTED"
                    ? <span className="text-[12px] text-slate-300">n/a</span>
                    : r.confirmed
                      ? <span className="text-[12px] font-medium text-teal-700">Confirmed {r.confirmed_at ? timeAgo(r.confirmed_at) : ""}</span>
                      : <span className="text-[12px] text-slate-500">Awaiting TPO confirmation</span>}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Disclaimer>
        A "Selected" result is your company's decision. The institution's official placement record
        is created only when the TPO confirms it.
      </Disclaimer>
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { timeAgo } from "../../lib/format";
import { STAGE_META } from "../../lib/placement";
import { Badge, Card, Disclaimer, ErrorBox, Spinner, Table } from "../../components/ui";

interface Row {
  student_id: number; name: string; usn: string; semester: number;
  company: string | null; role: string | null; drive: string | null;
  status: string; updated_at: string;
}
interface Resp { status: string; rows: Row[] }

export default function DeptPlacements() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["dept-placements"],
    queryFn: () => api<Resp>("/dept/placements"),
  });

  if (isLoading) return <Spinner label="Loading department placement status…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Placement Status</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          Every drive participation by your students, with the current pipeline stage.
        </p>
      </header>

      <Card>
        {data.rows.length === 0 ? (
          <p className="py-6 text-center text-[13px] text-slate-400">
            No students from this department are in a placement drive yet.
          </p>
        ) : (
          <Table head={
            <tr>
              <th>Student</th><th>Company</th><th>Role</th><th>Stage</th><th>Updated</th>
            </tr>
          }>
            {data.rows.map((r, i) => {
              const m = STAGE_META[r.status];
              return (
                <tr key={`${r.student_id}-${r.drive}-${i}`}>
                  <td>
                    <div className="font-medium text-slate-800">{r.name}</div>
                    <div className="text-[11.5px] text-slate-400">{r.usn} · Sem {r.semester}</div>
                  </td>
                  <td className="text-[13px] text-slate-700">{r.company || "—"}</td>
                  <td className="text-[12.5px] text-slate-600">{r.role || "—"}</td>
                  <td><Badge cls={m?.cls || ""}>{m?.label || r.status}</Badge></td>
                  <td className="text-[12px] text-slate-400">{timeAgo(r.updated_at)}</td>
                </tr>
              );
            })}
          </Table>
        )}
      </Card>

      <Disclaimer>
        You monitor placement progress for your students; nominations and confirmations remain
        with the TPO and companies respectively.
      </Disclaimer>
    </div>
  );
}

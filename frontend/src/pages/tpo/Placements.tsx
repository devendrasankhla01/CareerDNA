import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck } from "lucide-react";
import { api } from "../../api/client";
import { fmt, fmt1, timeAgo } from "../../lib/format";
import { STAGE_META } from "../../lib/placement";
import { Badge, Card, Disclaimer, ErrorBox, Spinner, Stat, Table } from "../../components/ui";

interface Row {
  candidate_id: number; student_id: number; name: string; usn: string;
  branch: string; semester: number; readiness: number | null;
  company: string; drive: string; role: string; ctc: string | null;
  status: string; selected_at: string | null; confirmed_at: string | null;
}
interface Resp {
  status: string; rows: Row[];
  counts: { placed: number; selected: number; not_selected: number };
  participating_students: number;
}

export default function TpoPlacements() {
  const qc = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["tpo-placements"],
    queryFn: () => api<Resp>("/tpo/placements"),
  });
  const confirm = useMutation({
    mutationFn: (id: number) =>
      api(`/tpo/placements/${id}/confirm`, { method: "POST", body: {} }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tpo-placements"] }),
  });

  if (isLoading) return <Spinner label="Loading placements…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  const c = data.counts;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Placements</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          Company selections and official (TPO-confirmed) placement records for the institution.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Placed (confirmed)" value={fmt(c.placed)} tone="good"
          sub="Official institutional record" />
        <Stat label="Selected by company" value={fmt(c.selected)} sub="Awaiting TPO confirmation" />
        <Stat label="Not selected" value={fmt(c.not_selected)} sub="In drives this cycle" />
        <Stat label="Students in process" value={fmt(data.participating_students)}
          sub="Ever entered a drive pipeline" />
      </div>

      <Card title="Selection & confirmation queue">
        {data.rows.length === 0 ? (
          <p className="py-6 text-center text-[13px] text-slate-400">
            No company selections yet. Nominate candidates in Candidate Matching and companies will
            shortlist & select from their authorized pool.
          </p>
        ) : (
          <Table head={
            <tr>
              <th>Student</th><th>Branch · Sem</th><th>Readiness</th><th>Company</th>
              <th>Role</th><th>Status</th><th>Selected</th><th>Action</th>
            </tr>
          }>
            {data.rows.map((r) => {
              const m = STAGE_META[r.status];
              return (
                <tr key={r.candidate_id}>
                  <td>
                    <div className="font-medium text-slate-800">{r.name}</div>
                    <div className="text-[11.5px] text-slate-400">{r.usn}</div>
                  </td>
                  <td className="text-[12.5px] text-slate-600">{r.branch} · S{r.semester}</td>
                  <td className="tabular-nums text-slate-600">{fmt1(r.readiness)}</td>
                  <td className="text-[13px] text-slate-700">{r.company}</td>
                  <td className="text-[12.5px] text-slate-600">{r.role}</td>
                  <td><Badge cls={m?.cls || ""}>{m?.label || r.status}</Badge></td>
                  <td className="text-[12px] text-slate-500">
                    {r.selected_at ? timeAgo(r.selected_at) : "—"}
                    {r.confirmed_at && <div className="text-teal-700">confirmed {timeAgo(r.confirmed_at)}</div>}
                  </td>
                  <td>
                    {r.status === "SELECTED" ? (
                      <button
                        className="btn-primary !px-3 !py-1.5 !text-[12.5px]"
                        disabled={confirm.isPending}
                        onClick={() => confirm.mutate(r.candidate_id)}>
                        <BadgeCheck className="mr-1 h-4 w-4" /> Confirm Placement
                      </button>
                    ) : (
                      <span className="text-[12px] text-slate-400">
                        {r.status === "PLACED" ? "Recorded" : "—"}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </Table>
        )}
      </Card>

      <Disclaimer>
        Selected ≠ Placed. A company's selection is a recruiter action; the institution's official
        placement record is created only when you confirm it here.
      </Disclaimer>
    </div>
  );
}

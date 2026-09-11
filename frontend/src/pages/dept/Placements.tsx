import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Award, Clock, ThumbsUp, Send } from "lucide-react";
import { api } from "../../api/client";
import { fmt, fmt1, timeAgo } from "../../lib/format";
import { STAGE_META } from "../../lib/placement";
import { Badge, Card, Disclaimer, ErrorBox, Spinner, Stat, Table } from "../../components/ui";

interface Row {
  candidate_id: number;
  student_id: number;
  name: string;
  usn: string;
  semester: number;
  readiness?: number | null;
  category?: string | null;
  cgpa?: number | null;
  company: string | null;
  role: string | null;
  drive: string | null;
  status: string;
  match_score?: number | null;
  hod_endorsed: boolean;
  hod_note?: string | null;
  hod_endorsed_at?: string | null;
  can_endorse: boolean;
  updated_at: string;
}

interface Counts {
  total: number;
  pending_endorsement: number;
  hod_endorsed: number;
  nominated: number;
  placed: number;
}

interface Resp {
  status: string;
  rows: Row[];
  counts: Counts;
}

export default function DeptPlacements() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<"ALL" | "PENDING" | "ENDORSED" | "PLACED">("ALL");
  const [activeCandidate, setActiveCandidate] = useState<Row | null>(null);
  const [note, setNote] = useState("");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["dept-placements"],
    queryFn: () => api<Resp>("/dept/placements"),
  });

  const endorse = useMutation({
    mutationFn: (candId: number) =>
      api(`/dept/candidates/${candId}/endorse`, {
        method: "POST",
        body: { note: note.trim() || "Recommended by Department / HOD" },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dept-placements"] });
      setActiveCandidate(null);
      setNote("");
    },
  });

  if (isLoading) return <Spinner label="Loading department placement & endorsement status…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  const counts = data.counts || {
    total: data.rows.length,
    pending_endorsement: data.rows.filter((r) => r.status === "INTERESTED").length,
    hod_endorsed: data.rows.filter((r) => r.hod_endorsed || r.status === "HOD_APPROVED").length,
    nominated: data.rows.filter((r) => ["NOMINATED", "SHORTLISTED", "INTERVIEW", "SELECTED", "PLACED"].includes(r.status)).length,
    placed: data.rows.filter((r) => r.status === "PLACED").length,
  };

  const filteredRows = data.rows.filter((r) => {
    if (filter === "PENDING") return r.status === "INTERESTED";
    if (filter === "ENDORSED") return r.hod_endorsed || r.status === "HOD_APPROVED";
    if (filter === "PLACED") return r.status === "PLACED";
    return true;
  });

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Placement & Student Endorsement Portal</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          Review student interest expressions, verify readiness, and endorse top candidates to the TPO for company drives.
        </p>
      </header>

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Total Applications" value={fmt(counts.total)} />
        <Stat
          label="Pending HOD Review"
          value={fmt(counts.pending_endorsement)}
          tone={counts.pending_endorsement > 0 ? "bad" : "neutral"}
          sub="awaiting your endorsement"
        />
        <Stat label="HOD Endorsed" value={fmt(counts.hod_endorsed)} tone="good" sub="forwarded to TPO" />
        <Stat label="Confirmed Placed" value={fmt(counts.placed)} tone="good" />
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 border-b border-slate-200 pb-2">
        {(
          [
            ["ALL", `All Applications (${counts.total})`],
            ["PENDING", `Pending Endorsement (${counts.pending_endorsement})`],
            ["ENDORSED", `Endorsed by HOD (${counts.hod_endorsed})`],
            ["PLACED", `Placed (${counts.placed})`],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
              filter === key
                ? "bg-navy-800 text-white shadow-sm"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <Card>
        {filteredRows.length === 0 ? (
          <p className="py-8 text-center text-[13px] text-slate-400">
            {filter === "PENDING"
              ? "No pending student requests awaiting HOD endorsement."
              : "No students match this filter."}
          </p>
        ) : (
          <Table
            head={
              <tr>
                <th>Student</th>
                <th>Company & Drive</th>
                <th>Readiness / CGPA</th>
                <th>Current Stage</th>
                <th>HOD Recommendation</th>
                <th>Action</th>
              </tr>
            }
          >
            {filteredRows.map((r, i) => {
              const m = STAGE_META[r.status];
              return (
                <tr key={`${r.candidate_id}-${i}`}>
                  <td>
                    <div className="font-semibold text-slate-900">{r.name}</div>
                    <div className="text-[11.5px] text-slate-400">
                      {r.usn} · Sem {r.semester}
                    </div>
                  </td>
                  <td>
                    <div className="font-medium text-slate-800">{r.company || "—"}</div>
                    <div className="text-[11.5px] text-slate-500">{r.role || r.drive || "—"}</div>
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold tabular-nums text-navy-800">
                        {r.readiness ? `${fmt1(r.readiness)}%` : "—"}
                      </span>
                      {r.cgpa && (
                        <span className="text-xs text-slate-500">
                          (CGPA {fmt1(r.cgpa)})
                        </span>
                      )}
                    </div>
                    {r.category && (
                      <span className="text-[10.5px] font-medium text-slate-400">
                        {r.category.replace("_", " ")}
                      </span>
                    )}
                  </td>
                  <td>
                    <Badge cls={m?.cls || ""}>{m?.label || r.status}</Badge>
                    <div className="mt-0.5 text-[10.5px] text-slate-400">{timeAgo(r.updated_at)}</div>
                  </td>
                  <td>
                    {r.hod_endorsed ? (
                      <div className="space-y-0.5">
                        <span className="inline-flex items-center gap-1 rounded bg-teal-50 px-2 py-0.5 text-[11px] font-semibold text-teal-700 border border-teal-200">
                          <ThumbsUp className="h-3 w-3" /> Endorsed
                        </span>
                        {r.hod_note && (
                          <p className="text-[11px] text-slate-600 italic line-clamp-1">{r.hod_note}</p>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400 italic">Pending review</span>
                    )}
                  </td>
                  <td>
                    {r.status === "INTERESTED" ? (
                      <button
                        className="btn-primary !py-1 !px-2.5 !text-xs"
                        onClick={() => {
                          setActiveCandidate(r);
                          setNote(`High academic standing & strong readiness. Recommended for ${r.company}.`);
                        }}
                      >
                        <Award className="mr-1 h-3.5 w-3.5" /> Endorse for TPO
                      </button>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-500">
                        <CheckCircle2 className="h-3.5 w-3.5 text-teal-600" /> Forwarded
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </Table>
        )}
      </Card>

      {/* Endorsement Modal */}
      {activeCandidate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-4">
            <div className="flex items-center gap-2">
              <Award className="h-6 w-6 text-amber-600" />
              <h3 className="text-lg font-bold text-slate-900">Endorse Student Application</h3>
            </div>
            <p className="text-sm text-slate-600">
              Endorse <span className="font-semibold text-slate-800">{activeCandidate.name}</span> ({activeCandidate.usn}) for the <span className="font-semibold text-slate-800">{activeCandidate.company}</span> ({activeCandidate.role}) drive.
            </p>
            <div className="rounded-lg bg-slate-50 p-3 text-xs space-y-1 text-slate-600">
              <div><strong>Placement Readiness:</strong> {activeCandidate.readiness ? `${fmt1(activeCandidate.readiness)}%` : "—"}</div>
              <div><strong>CGPA:</strong> {activeCandidate.cgpa ? fmt1(activeCandidate.cgpa) : "—"}</div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                HOD Recommendation Note for TPO
              </label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                className="w-full rounded-lg border border-slate-300 p-2 text-sm focus:border-navy-500 focus:outline-hidden"
                placeholder="Add recommendation remarks for the Training & Placement Officer..."
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                className="btn-outline !py-1.5"
                onClick={() => setActiveCandidate(null)}
                disabled={endorse.isPending}
              >
                Cancel
              </button>
              <button
                className="btn-primary !py-1.5"
                disabled={endorse.isPending}
                onClick={() => endorse.mutate(activeCandidate.candidate_id)}
              >
                {endorse.isPending ? "Endorsing…" : <><Send className="mr-1 h-4 w-4" />Confirm Endorsement</>}
              </button>
            </div>
          </div>
        </div>
      )}

      <Disclaimer>
        <Award className="mr-1 inline h-3.5 w-3.5" />
        Department endorsements help the TPO prioritize students with strong academic merit and practical skills during formal company nomination.
      </Disclaimer>
    </div>
  );
}

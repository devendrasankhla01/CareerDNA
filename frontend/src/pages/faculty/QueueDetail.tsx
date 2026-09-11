import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft, CheckCircle2, ExternalLink, FileText, History, XCircle,
} from "lucide-react";
import { api } from "../../api/client";
import { fmt1, timeAgo } from "../../lib/format";
import { Badge, Card, ErrorBox, Spinner, StatusBadge } from "../../components/ui";

interface DetailResp {
  status: string;
  request: {
    id: number; student_id: number; student_name: string; usn: string; branch: string;
    semester: number; entity_type: string; entity_id: number; category: string;
    status: string; resubmission: boolean; submitted_at: string;
  };
  item: Record<string, any>;
  history: { verifier: string; previous_status: string; new_status: string; note: string | null; at: string }[];
  student_verified_count: number; student_pending_count: number;
}

const ENTITY_LABEL: Record<string, string> = {
  project: "Project", internship: "Internship", certification: "Certification",
  activity: "Activity", open_source: "Open Source", skill: "Skill Claim",
};

export default function QueueDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const [correctionScore, setCorrectionScore] = useState<string>("");
  const [correctionComplexity, setCorrectionComplexity] = useState<string>("");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["queue-detail", id],
    queryFn: () => api<DetailResp>(`/faculty/queue/${id}`),
  });

  const decide = useMutation({
    mutationFn: (decision: "VERIFIED" | "CORRECTION_REQUIRED" | "REJECTED") => {
      const corrections: Record<string, unknown> = {};
      if (data?.request.entity_type === "skill" && correctionScore.trim() !== "") {
        corrections.score = Number(correctionScore);
      }
      if (data?.request.entity_type === "project" && correctionComplexity) {
        corrections.complexity = correctionComplexity;
      }
      return api(`/faculty/queue/${id}/decide`, {
        body: { decision, note: note.trim() || null, corrections: Object.keys(corrections).length ? corrections : null },
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["queue-detail", id] });
      qc.invalidateQueries({ queryKey: ["queue"] });
    },
  });

  if (isLoading) return <Spinner label="Loading request…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  const { request, item } = data;
  const decided = request.status !== "PENDING";
  const isSkill = request.entity_type === "skill";
  const isProject = request.entity_type === "project";

  return (
    <div className="space-y-5">
      <button className="flex items-center gap-1.5 text-[13px] font-medium text-navy-700 hover:underline"
        onClick={() => navigate("/verifier/queue")}>
        <ArrowLeft className="h-4 w-4" /> Back to queue
      </button>

      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">
            {ENTITY_LABEL[request.entity_type]} — {item.name || "item"}
          </h1>
          <p className="mt-0.5 text-[13px] text-slate-500">
            {request.student_name} · {request.usn} · {request.branch} · Semester {request.semester}
            {" · "}submitted {timeAgo(request.submitted_at)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={request.status} />
          {request.resubmission && <Badge cls="bg-orange-50 text-orange-600 border-orange-200">resubmission</Badge>}
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card title="Claimed evidence" subtitle="As submitted by the student">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3">
              {Object.entries(item).filter(([k, v]) => v !== null && v !== "" && v !== undefined && k !== "name").map(([k, v]) => (
                <div key={k}>
                  <dt className="label">{pretty(k)}</dt>
                  <dd className="mt-0.5 break-words text-[13.5px] text-slate-700">
                    {Array.isArray(v) ? v.join(", ") : typeof v === "string" && v.startsWith("http")
                      ? <a className="inline-flex items-center gap-1 text-navy-700 hover:underline" href={v} target="_blank" rel="noreferrer">{v} <ExternalLink className="h-3 w-3" /></a>
                      : String(v)}
                  </dd>
                </div>
              ))}
              {isSkill && (
                <>
                  <div>
                    <dt className="label">Claimed score</dt>
                    <dd className="mt-0.5 text-[13.5px] font-semibold tabular-nums text-slate-800">{item.score ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="label">Provenance</dt>
                    <dd className="mt-0.5 text-[13.5px] text-slate-700">{item.source_label || item.source || "Self-reported"}</dd>
                  </div>
                </>
              )}
            </dl>
          </Card>

          <Card title="Review history" subtitle="Full audit trail of decisions">
            {data.history.length === 0 ? (
              <p className="text-[13px] text-slate-400">No prior decisions on this item.</p>
            ) : (
              <ol className="relative space-y-4 border-l border-slate-200 pl-5">
                {[...data.history].reverse().map((h, i) => (
                  <li key={i} className="relative">
                    <span className={`absolute -left-[26.5px] top-1 h-3 w-3 rounded-full border-2 border-white ${
                      h.new_status === "VERIFIED" ? "bg-teal-500" : h.new_status === "REJECTED" ? "bg-rose-500" : "bg-amber-500"
                    }`} />
                    <div className="flex flex-wrap items-center gap-2 text-[13px]">
                      <span className="font-medium text-slate-800">{h.verifier}</span>
                      <span className="text-slate-400">{h.previous_status} →</span>
                      <StatusBadge status={h.new_status} />
                      <span className="text-[11.5px] text-slate-400">{timeAgo(h.at)}</span>
                    </div>
                    {h.note && <p className="mt-1 text-[12.5px] italic text-slate-500">“{h.note}”</p>}
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="Student context">
            <div className="space-y-2 text-[13px]">
              <div className="flex justify-between">
                <span className="text-slate-500">Verified items (passport)</span>
                <span className="font-semibold tabular-nums text-teal-700">{data.student_verified_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Other items pending</span>
                <span className="font-semibold tabular-nums text-amber-600">{data.student_pending_count}</span>
              </div>
            </div>
            <p className="mt-3 text-[11.5px] leading-relaxed text-slate-400">
              Verifying this item updates the student’s trusted profile and recomputes their
              placement readiness analysis.
            </p>
          </Card>

          <Card title="Decision">
            {decided ? (
              <div className="rounded-lg bg-slate-50 px-4 py-3 text-[13px] text-slate-600">
                This request has already been reviewed. A new review round starts if the student
                resubmits.
              </div>
            ) : (
              <div className="space-y-4">
                {isSkill && (
                  <div>
                    <label className="label" htmlFor="cscore">Corrected score (optional)</label>
                    <input id="cscore" type="number" min={0} max={100} className="input mt-1.5"
                      placeholder={item.score ? `leave blank to keep ${item.score}` : "0–100"}
                      value={correctionScore} onChange={(e) => setCorrectionScore(e.target.value)} />
                  </div>
                )}
                {isProject && (
                  <div>
                    <label className="label" htmlFor="ccomplexity">Verified complexity (optional)</label>
                    <select id="ccomplexity" className="input mt-1.5" value={correctionComplexity}
                      onChange={(e) => setCorrectionComplexity(e.target.value)}>
                      <option value="">keep claimed ({item.claimed_complexity || "n/a"})</option>
                      <option value="Basic">Basic</option>
                      <option value="Intermediate">Intermediate</option>
                      <option value="Advanced">Advanced</option>
                    </select>
                  </div>
                )}
                <div>
                  <label className="label" htmlFor="note">Note to student</label>
                  <textarea id="note" rows={3} className="input mt-1.5"
                    placeholder="Required for corrections and rejections…"
                    value={note} onChange={(e) => setNote(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <button className="btn-teal w-full" disabled={decide.isPending}
                    onClick={() => decide.mutate("VERIFIED")}>
                    <CheckCircle2 className="h-4 w-4" /> Verify
                  </button>
                  <button
                    className="btn w-full border border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100"
                    disabled={decide.isPending || !note.trim()}
                    onClick={() => decide.mutate("CORRECTION_REQUIRED")}
                    title={!note.trim() ? "A note is required" : undefined}
                  >
                    <FileText className="h-4 w-4" /> Request correction
                  </button>
                  <button
                    className="btn-danger w-full"
                    disabled={decide.isPending || !note.trim()}
                    onClick={() => decide.mutate("REJECTED")}
                    title={!note.trim() ? "A note is required" : undefined}
                  >
                    <XCircle className="h-4 w-4" /> Reject
                  </button>
                  {decide.isError && (
                    <p className="text-[12px] text-rose-600">{(decide.error as Error).message}</p>
                  )}
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

function pretty(k: string) {
  return k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

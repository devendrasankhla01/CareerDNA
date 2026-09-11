import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ClipboardCheck, Clock } from "lucide-react";
import { api } from "../../api/client";
import { useAuth } from "../../lib/auth";
import { timeAgo } from "../../lib/format";
import { Badge, Card, ErrorBox, Spinner, StatusBadge, Table } from "../../components/ui";

interface QueueItem {
  request_id: number; student_id: number; student_name: string; usn: string;
  branch: string; semester: number; entity_type: string; entity_id: number;
  category: string; status: string; resubmission: boolean;
  submitted_at: string; updated_at: string;
  summary: Record<string, any>; last_review: { verifier: string; status: string; note: string; at: string } | null;
}
interface QueueResp {
  status: string; total: number; page: number; page_size: number; items: QueueItem[];
}

const ENTITY_LABEL: Record<string, string> = {
  project: "Project", internship: "Internship", certification: "Certification",
  activity: "Activity", open_source: "Open Source", skill: "Skill Claim",
};

const CATEGORY_LABEL: Record<string, string> = {
  TECHNICAL_SKILL: "Technical Skill", PROJECT: "Project", CERTIFICATION: "Certification",
  INTERNSHIP: "Internship", ACTIVITY: "Activity",
};

export default function Queue() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [category, setCategory] = useState<string>("");
  const [status, setStatus] = useState<string>("PENDING");
  const [page, setPage] = useState(1);

  const cats = user?.categories || [];
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["queue", category, status, page],
    queryFn: () => api<QueueResp>(
      `/faculty/queue?status=${status}${category ? `&category=${category}` : ""}&page=${page}&page_size=15`
    ),
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">My Verification Queue</h1>
          <p className="mt-0.5 text-[13px] text-slate-500">
            Requests the TPO assigned to you. Review student evidence and set the verified state —
            decisions are audited. The TPO retains full oversight of all verifications.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select className="input !w-auto" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }}>
            <option value="">All my categories</option>
            {cats.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c] || c}</option>)}
          </select>
          <select className="input !w-auto" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="PENDING">Pending</option>
            <option value="VERIFIED">Verified</option>
            <option value="CORRECTION_REQUIRED">Correction Required</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </div>
      </header>

      <Card>
        {isLoading ? (
          <Spinner label="Loading queue…" />
        ) : isError ? (
          <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />
        ) : !data || data.items.length === 0 ? (
          <div className="flex flex-col items-center py-10 text-center">
            <ClipboardCheck className="h-8 w-8 text-slate-300" />
            <div className="mt-3 text-sm font-medium text-slate-600">Queue is clear</div>
            <div className="mt-1 text-[12.5px] text-slate-400">No items match the current filters.</div>
          </div>
        ) : (
          <>
            <Table
              head={
                <tr>
                  <th>Student</th><th>Item</th><th>Summary</th><th>Category</th>
                  <th>Status</th><th>Submitted</th><th>Last review</th>
                </tr>
              }
            >
              {data.items.map((q) => (
                <tr key={q.request_id} className="cursor-pointer hover:bg-slate-50/70"
                  onClick={() => navigate(`/verifier/queue/${q.request_id}`)}>
                  <td>
                    <div className="font-medium text-slate-800">{q.student_name}</div>
                    <div className="text-[11.5px] text-slate-400">{q.usn} · {q.branch} · Sem {q.semester}</div>
                  </td>
                  <td className="whitespace-nowrap">
                    <span className="text-[13px] font-medium text-navy-800">{ENTITY_LABEL[q.entity_type] || q.entity_type}</span>
                    {q.resubmission && <Badge cls="ml-1.5 bg-orange-50 text-orange-600 border-orange-200">resubmission</Badge>}
                  </td>
                  <td className="max-w-[260px]">
                    <div className="truncate text-[13px] text-slate-600">{q.summary?.name || "—"}</div>
                    {q.summary?.score !== undefined && (
                      <div className="text-[11.5px] text-slate-400">
                        claimed {q.summary.score ?? "—"}{q.summary.claimed_level ? ` · ${q.summary.claimed_level}` : ""}
                      </div>
                    )}
                  </td>
                  <td className="whitespace-nowrap text-[12.5px] text-slate-500">{CATEGORY_LABEL[q.category] || q.category}</td>
                  <td><StatusBadge status={q.status} /></td>
                  <td className="whitespace-nowrap text-[12px] text-slate-400">
                    <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" />{timeAgo(q.submitted_at)}</span>
                  </td>
                  <td className="max-w-[200px]">
                    {q.last_review ? (
                      <>
                        <div className="truncate text-[12px] text-slate-500">{q.last_review.verifier}</div>
                        <div className="text-[11px] text-slate-400">{q.last_review.status}</div>
                      </>
                    ) : <span className="text-[12px] text-slate-300">—</span>}
                  </td>
                </tr>
              ))}
            </Table>
            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-between text-[12.5px] text-slate-500">
                <span>{data.total} items · page {data.page} of {totalPages}</span>
                <div className="flex gap-2">
                  <button className="btn-outline !py-1.5" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
                  <button className="btn-outline !py-1.5" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}

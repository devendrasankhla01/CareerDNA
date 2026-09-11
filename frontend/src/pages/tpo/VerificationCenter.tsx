import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ClipboardCheck, UserPlus } from "lucide-react";
import { api } from "../../api/client";
import { timeAgo } from "../../lib/format";
import { Badge, Card, Disclaimer, ErrorBox, Spinner, Stat, Table } from "../../components/ui";

interface CenterItem {
  request_id: number; status: string;
  student_name: string | null; usn: string | null; branch: string | null;
  entity_type: string; category: string;
  submitted_at: string; age_days: number; escalated: boolean;
  verifier: string | null; verifier_id: number | null;
}
interface CenterResp {
  status: string;
  counts: {
    pending: number; assigned: number; unassigned: number;
    correction_required: number; verified: number; verified_today: number;
    escalated: number; rejected: number;
  };
  escalation_days: number;
  items: CenterItem[];
}
interface Verifier { id: number; name: string; email: string; categories: string[]; is_active: boolean }

const ENTITY_LABEL: Record<string, string> = {
  project: "Project", internship: "Internship", certification: "Certification",
  activity: "Activity", open_source: "Open Source", skill: "Skill Claim",
};
const CATEGORY_LABEL: Record<string, string> = {
  TECHNICAL_SKILL: "Technical Skill", PROJECT: "Project", CERTIFICATION: "Certification",
  INTERNSHIP: "Internship", ACTIVITY: "Activity",
};

export default function VerificationCenter() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [department, setDepartment] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [verifierId, setVerifierId] = useState<number | null>(null);

  const center = useQuery({
    queryKey: ["tpo-verification-center", status, department],
    queryFn: () => {
      const p = new URLSearchParams();
      if (status) p.set("status", status);
      if (department) p.set("department", department);
      const q = p.toString();
      return api<CenterResp>(`/tpo/verification-center${q ? `?${q}` : ""}`);
    },
  });
  const verifiersQ = useQuery({
    queryKey: ["tpo-verifiers"],
    queryFn: () => api<{ verifiers: Verifier[] }>("/tpo/verifiers"),
  });
  const departmentsQ = useQuery({
    queryKey: ["tpo-departments"],
    queryFn: () => api<{ departments: { code: string }[] }>("/tpo/departments"),
  });

  const assign = useMutation({
    mutationFn: (body: { request_ids: number[]; verifier_id: number }) =>
      api("/tpo/verification-center/assign", { method: "POST", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tpo-verification-center"] });
      setSelected(new Set());
    },
  });

  if (center.isLoading) return <Spinner label="Loading verification center…" />;
  if (center.isError) return <ErrorBox message={(center.error as Error).message} onRetry={() => center.refetch()} />;
  if (!center.data) return null;

  const c = center.data.counts;
  const pending = center.data.items.filter((i) => i.status === "PENDING");

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Verification Center</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          TPO oversight of the verification workflow: route requests to verifiers, watch aging,
          and escalate. Verifiers only see what you assign them.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Pending" value={c.pending} sub={`${c.assigned} assigned · ${c.unassigned} unassigned`} />
        <Stat label="Escalated" value={c.escalated} tone={c.escalated > 0 ? "bad" : "neutral"}
          sub={`Pending > ${center.data.escalation_days} days`} />
        <Stat label="Correction required" value={c.correction_required} sub="awaiting student resubmission" />
        <Stat label="Verified" value={c.verified} tone="good" sub={`${c.verified_today} today`} />
      </div>

      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-navy-200 bg-navy-50/60 px-4 py-3 card">
          <span className="text-[13px] font-semibold text-navy-800">{selected.size} request(s) selected</span>
          <select className="input !w-auto" value={verifierId ?? ""} onChange={(e) => setVerifierId(Number(e.target.value))}>
            <option value="">Assign to verifier…</option>
            {(verifiersQ.data?.verifiers || []).map((v) => (
              <option key={v.id} value={v.id}>
                {v.name} ({v.categories.map((x) => CATEGORY_LABEL[x] || x).join(", ") || "any"})
              </option>
            ))}
          </select>
          <button className="btn-primary" disabled={verifierId == null || assign.isPending}
            onClick={() => assign.mutate({ request_ids: [...selected], verifier_id: verifierId! })}>
            <UserPlus className="mr-1.5 h-4 w-4" />
            {assign.isPending ? "Assigning…" : "Assign"}
          </button>
          {assign.isSuccess && <span className="text-[12.5px] font-medium text-teal-700">Assigned.</span>}
          {assign.isError && <span className="text-[12.5px] text-rose-600">{(assign.error as Error).message}</span>}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <select className="input !w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="PENDING">Pending</option>
          <option value="VERIFIED">Verified</option>
          <option value="CORRECTION_REQUIRED">Correction Required</option>
          <option value="REJECTED">Rejected</option>
        </select>
        <select className="input !w-auto" value={department} onChange={(e) => setDepartment(e.target.value)}>
          <option value="">All departments</option>
          {(departmentsQ.data?.departments || []).map((d) => (
            <option key={d.code} value={d.code}>{d.code}</option>
          ))}
        </select>
      </div>

      <Card title={status === "PENDING" || !status ? "Requests (pending first)" : "Requests"}>
        {center.data.items.length === 0 ? (
          <div className="flex flex-col items-center py-10 text-center">
            <ClipboardCheck className="h-8 w-8 text-slate-300" />
            <div className="mt-3 text-sm font-medium text-slate-600">Nothing here</div>
            <div className="mt-1 text-[12.5px] text-slate-400">No verification requests match the current filters.</div>
          </div>
        ) : (
          <Table head={
            <tr>
              {status === "PENDING" || !status ? <th className="w-8"></th> : null}
              <th>Student</th><th>Item</th><th>Category</th><th>Status</th>
              <th>Age</th><th>Verifier</th>
            </tr>
          }
        >
            {center.data.items.map((r) => {
              const showCheck = status === "PENDING" || !status;
              return (
                <tr key={r.request_id} className={r.escalated ? "bg-rose-50/40" : ""}>
                  {showCheck && (
                    <td>
                      <input type="checkbox" className="h-4 w-4 accent-navy-700"
                        checked={selected.has(r.request_id)}
                        onChange={(e) => {
                          const n = new Set(selected);
                          if (e.target.checked) n.add(r.request_id); else n.delete(r.request_id);
                          setSelected(n);
                        }} />
                    </td>
                  )}
                  <td>
                    <div className="font-medium text-slate-800">{r.student_name || "—"}</div>
                    <div className="text-[11.5px] text-slate-400">{r.usn} · {r.branch}</div>
                  </td>
                  <td className="text-[13px] font-medium text-navy-800">{ENTITY_LABEL[r.entity_type] || r.entity_type}</td>
                  <td className="text-[12.5px] text-slate-500">{CATEGORY_LABEL[r.category] || r.category}</td>
                  <td>
                    <Badge cls={
                      r.status === "PENDING" ? "bg-amber-50 text-amber-700 border-amber-200"
                        : r.status === "VERIFIED" ? "bg-teal-50 text-teal-700 border-teal-200"
                        : r.status === "CORRECTION_REQUIRED" ? "bg-orange-50 text-orange-700 border-orange-200"
                        : "bg-rose-50 text-rose-700 border-rose-200"}>
                      {r.status === "CORRECTION_REQUIRED" ? "Correction Required" : r.status}
                    </Badge>
                  </td>
                  <td className="whitespace-nowrap text-[12px] text-slate-500">
                    {timeAgo(r.submitted_at)}
                    {r.escalated && (
                      <Badge cls="ml-1.5 bg-rose-50 text-rose-700 border-rose-200">
                        <AlertTriangle className="h-3 w-3" /> escalated
                      </Badge>
                    )}
                  </td>
                  <td className="text-[12.5px] text-slate-600">{r.verifier || <span className="text-slate-300">unassigned</span>}</td>
                </tr>
              );
            })}
          </Table>
        )}
      </Card>

      <Disclaimer>
        Verification coverage is what makes the readiness model trustworthy. Requests pending
        longer than {center.data.escalation_days} days are flagged for escalation. Verifiers only
        ever see the requests you assign to them.
      </Disclaimer>
    </div>
  );
}

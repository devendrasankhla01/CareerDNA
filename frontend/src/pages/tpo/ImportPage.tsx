import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, FileSpreadsheet, UploadCloud, UserPlus } from "lucide-react";
import { api, getToken, API_BASE } from "../../api/client";
import { fmt, timeAgo } from "../../lib/format";
import { Badge, Card, ErrorBox, Spinner, Table } from "../../components/ui";

interface ValidateResp {
  status: string; job_id: number; rows_detected: number; valid_rows: number;
  new_students: number; update_rows: number; rejected_rows: number;
  ignored_columns: string[];
  errors: { row: number; usn: string; errors: string[] }[];
  message: string;
}
interface ConfirmResp {
  status: string; job_id: number; imported_rows: number;
  new_students: number; updated_students: number; analyzed: number; message: string;
}
interface Job {
  id: number; file_name: string; status: string; rows_detected: number; valid_rows: number;
  update_rows: number; rejected_rows: number; created_at: string; completed_at: string | null;
  errors: { row: number; usn: string; errors: string[] }[];
}

export default function ImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ValidateResp | null>(null);
  const [confirmed, setConfirmed] = useState<ConfirmResp | null>(null);
  const [busy, setBusy] = useState<"idle" | "validate" | "confirm">("idle");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const jobs = useQuery({
    queryKey: ["import-jobs"],
    queryFn: () => api<{ status: string; jobs: Job[] }>("/tpo/import/jobs"),
  });
  const queryClient = useQueryClient();

  async function downloadTemplate() {
    try {
      const res = await fetch(`${API_BASE}/api/tpo/import/template`, {
        headers: { Authorization: `Bearer ${getToken() || ""}` },
      });
      if (!res.ok) throw new Error("Template download failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "student_data_template.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setUploadError((e as Error).message);
    }
  }

  async function validate() {
    if (!file) return;
    setBusy("validate");
    setReport(null);
    setConfirmed(null);
    setUploadError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const data = await api<ValidateResp>("/tpo/import/validate", { formData: fd });
      setReport(data);
    } catch (e) {
      setUploadError((e as Error).message);
    } finally {
      setBusy("idle");
    }
  }

  async function confirm() {
    if (!report) return;
    setBusy("confirm");
    setUploadError(null);
    try {
      const data = await api<ConfirmResp>(`/tpo/import/confirm/${report.job_id}`, { body: {} });
      setConfirmed(data);
      setReport(null);
      setFile(null);
      jobs.refetch();
      // a fresh roster changes every dashboard — drop all cached queries so
      // every menu (Overview, Students, Departments, Matching, …) refetches
      // and syncs immediately after the import
      await queryClient.invalidateQueries();
      if (inputRef.current) inputRef.current.value = "";
    } catch (e) {
      setUploadError((e as Error).message);
    } finally {
      setBusy("idle");
    }
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Student Data Import</h1>
        <p className="mt-0.5 max-w-2xl text-[13px] text-slate-500">
          The institutional data path: upload your students as CSV. A USN not yet in the system
          <span className="font-medium text-slate-600"> creates the student account</span> (they sign in with
          their USN + OTP); existing USNs are updated. Institution-provided skill scores count as
          verified. Two phases: validate first, then confirm.
        </p>
      </header>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Upload CSV" subtitle="Required: usn, semester, cgpa · Everything else is optional (name, email, branch, 10th/12th %, backlogs, skill scores 0–100, open_source / hackathon / leadership as 0/1)">
          <div className="space-y-4">
            <button className="btn-outline" onClick={downloadTemplate}>
              <Download className="h-4 w-4" /> Download CSV template
            </button>
            <label
              className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-slate-50/50 px-6 py-8 text-center transition hover:border-navy-300 hover:bg-navy-50/40"
            >
              <UploadCloud className="h-7 w-7 text-slate-400" />
              <span className="mt-2 text-[13.5px] font-medium text-slate-600">
                {file ? file.name : "Choose a CSV file"}
              </span>
              <span className="mt-1 text-[11.5px] text-slate-400">CSV · max 5 MB</span>
              <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0] || null;
                  setFile(f); setReport(null); setConfirmed(null); setUploadError(null);
                }} />
            </label>
            {uploadError && <ErrorBox message={uploadError} />}
            <button className="btn-teal flex w-full items-center justify-center gap-2" disabled={!file || busy !== "idle"} onClick={validate}>
              <FileSpreadsheet className="h-4 w-4" />
              {busy === "validate" ? "Validating…" : "Validate file"}
            </button>
          </div>
        </Card>

        <Card title="Validation report" subtitle="Review before confirming — rejected rows are never imported">
          {confirmed ? (
            <div className="flex flex-col items-center py-8 text-center">
              <CheckCircle2 className="h-9 w-9 text-teal-500" />
              <p className="mt-3 text-[14px] font-semibold text-slate-800">Import complete</p>
              <p className="mt-1 text-[13px] text-slate-500">{confirmed.message}</p>
              <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-navy-50 px-3 py-1 text-[12px] text-navy-700">
                <UserPlus className="h-3.5 w-3.5" />
                {confirmed.analyzed} student(s) scored immediately
              </div>
            </div>
          ) : report ? (
            <div className="space-y-4">
              <div className="grid grid-cols-4 gap-2.5">
                <MiniStat label="Rows" value={fmt(report.rows_detected)} />
                <MiniStat label="Valid" value={fmt(report.valid_rows)} tone="good" />
                <MiniStat label="New / Updated" value={`${fmt(report.new_students)} / ${fmt(report.update_rows)}`} />
                <MiniStat label="Rejected" value={fmt(report.rejected_rows)} tone={report.rejected_rows ? "bad" : "neutral"} />
              </div>
              <p className="rounded-lg bg-slate-50 px-3.5 py-2.5 text-[12px] text-slate-600">{report.message}</p>
              {(report.ignored_columns || []).length > 0 && (
                <p className="text-[11.5px] text-slate-400">
                  Ignored columns (not recognized): {report.ignored_columns.join(", ")}
                </p>
              )}
              {report.errors.length > 0 && (
                <div className="max-h-56 overflow-y-auto rounded-lg border border-slate-200">
                  <Table head={<tr><th>Row</th><th>USN</th><th>Problem</th></tr>}>
                    {report.errors.slice(0, 50).map((e) => (
                      <tr key={e.row}>
                        <td className="tabular-nums text-slate-500">{e.row}</td>
                        <td className="text-slate-600">{e.usn}</td>
                        <td className="text-[12px] text-rose-600">{e.errors.join("; ")}</td>
                      </tr>
                    ))}
                  </Table>
                </div>
              )}
              <button className="btn-teal w-full" disabled={report.valid_rows === 0 || busy !== "idle"} onClick={confirm}>
                {busy === "confirm" ? "Importing…" : `Confirm import (${fmt(report.valid_rows)} valid rows)`}
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center py-10 text-center">
              <FileSpreadsheet className="h-8 w-8 text-slate-300" />
              <p className="mt-3 text-[13px] text-slate-500">Validate a file to see the report here.</p>
            </div>
          )}
        </Card>
      </div>

      <Card title="Import history" subtitle="Most recent jobs (audited)">
        {jobs.isLoading ? (
          <Spinner label="Loading…" />
        ) : !jobs.data || jobs.data.jobs.length === 0 ? (
          <p className="text-[13px] text-slate-400">No imports yet.</p>
        ) : (
          <Table head={
            <tr><th>File</th><th>Status</th><th>Rows</th><th>Valid</th><th>Updates</th><th>Rejected</th><th>When</th></tr>
          }>
            {jobs.data.jobs.map((j) => (
              <tr key={j.id}>
                <td className="max-w-[240px] truncate text-[13px] font-medium text-slate-800">{j.file_name}</td>
                <td>
                  <Badge cls={j.status === "IMPORTED" ? "bg-teal-50 text-teal-700 border-teal-200"
                    : j.status === "VALIDATED" ? "bg-amber-50 text-amber-700 border-amber-200"
                    : "bg-slate-100 text-slate-600 border-slate-200"}>
                    {j.status}
                  </Badge>
                </td>
                <td className="tabular-nums text-slate-600">{fmt(j.rows_detected)}</td>
                <td className="tabular-nums text-slate-600">{fmt(j.valid_rows)}</td>
                <td className="tabular-nums text-slate-600">{fmt(j.update_rows)}</td>
                <td className={`tabular-nums ${j.rejected_rows ? "text-rose-600" : "text-slate-400"}`}>{fmt(j.rejected_rows)}</td>
                <td className="text-[12px] text-slate-400">{timeAgo(j.created_at)}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}

function MiniStat({ label, value, tone }: { label: string; value: React.ReactNode; tone?: "good" | "bad" | "neutral" }) {
  const cls = tone === "good" ? "text-teal-700" : tone === "bad" ? "text-rose-700" : "text-slate-900";
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2.5 text-center">
      <div className="label !text-[10.5px]">{label}</div>
      <div className={`mt-0.5 text-lg font-semibold tabular-nums ${cls}`}>{value}</div>
    </div>
  );
}

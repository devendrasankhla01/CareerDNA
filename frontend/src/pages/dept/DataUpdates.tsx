import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Upload, UserCog } from "lucide-react";
import { api } from "../../api/client";
import { Card, Disclaimer, ErrorBox, Spinner } from "../../components/ui";

interface BulkResp { status: string; updated: number; errors: { row: number; usn: string; errors: string[] }[] }

// minimal robust CSV parser (handles quotes)
function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let cur = "", row: string[] = [], inQ = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQ) {
      if (ch === '"') {
        if (text[i + 1] === '"') { cur += '"'; i++; }
        else inQ = false;
      } else cur += ch;
    } else if (ch === '"') inQ = true;
    else if (ch === ",") { row.push(cur); cur = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cur); cur = "";
      if (row.some((c) => c.trim() !== "")) rows.push(row);
      row = [];
    } else cur += ch;
  }
  if (cur !== "" || row.length) { row.push(cur); if (row.some((c) => c.trim() !== "")) rows.push(row); }
  if (!rows.length) return [];
  const head = rows[0].map((h) => h.trim().toLowerCase());
  return rows.slice(1).map((r) => {
    const o: Record<string, string> = {};
    head.forEach((h, idx) => { o[h] = (r[idx] ?? "").trim(); });
    return o;
  });
}

const ALLOWED = ["usn", "cgpa", "semester", "backlog_history_count", "backlogs",
  "tenth_percentage", "twelfth_percentage", "coding", "aptitude", "logical",
  "communication", "presentation"];

export default function DeptDataUpdates() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<Record<string, string>[] | null>(null);
  const [fileName, setFileName] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);

  const bulk = useMutation({
    mutationFn: (rows: Record<string, string>[]) =>
      api<BulkResp>("/dept/bulk", { method: "POST", body: { rows } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dept-overview"] });
      qc.invalidateQueries({ queryKey: ["dept-skills"] });
      qc.invalidateQueries({ queryKey: ["dept-performance"] });
      setPreview(null); setFileName("");
    },
  });

  const onFile = (f: File) => {
    setParseError(null);
    f.text().then((txt) => {
      const rows = parseCsv(txt);
      if (!rows.length) { setParseError("The file has no data rows."); setPreview(null); return; }
      const head = Object.keys(rows[0]);
      const usable = head.filter((h) => ALLOWED.includes(h));
      if (!usable.includes("usn")) { setParseError('Every row needs a "usn" column.'); setPreview(null); return; }
      setPreview(rows); setFileName(f.name);
    });
  };

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Data Updates</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          Maintain institution-owned data for <span className="font-medium">your department only</span>:
          semester, CGPA, backlogs, 10th/12th percentages, and assessed scores
          (coding, aptitude, logical, communication, presentation). Every change is audited and
          triggers re-analysis. You cannot edit model outputs or verify evidence.
        </p>
      </header>

      <Card title="Bulk update (CSV)"
        subtitle={`Allowed columns: ${ALLOWED.join(", ")}`}>
        <input ref={fileRef} type="file" accept=".csv" className="hidden"
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
        <button className="btn-primary" onClick={() => fileRef.current?.click()}>
          <Upload className="mr-1.5 h-4 w-4" /> Choose CSV file
        </button>

        {parseError && <p className="mt-4 text-[13px] text-rose-600">{parseError}</p>}

        {preview && (
          <div className="mt-4 space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-[13px]">
              <span className="font-medium text-slate-700">{fileName}</span>
              <span className="text-slate-400">· {preview.length} row(s) parsed</span>
              <span className="text-[11.5px] text-slate-400">rows must belong to your department</span>
            </div>
            <div className="max-h-56 overflow-auto rounded-lg border border-slate-200">
              <table className="w-full text-[12px]">
                <thead className="sticky top-0 bg-slate-50">
                  <tr>{Object.keys(preview[0]).map((h) => (
                    <th key={h} className="whitespace-nowrap px-2.5 py-1.5 text-left font-semibold text-slate-500">{h}</th>
                  ))}</tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {preview.slice(0, 50).map((r, i) => (
                    <tr key={i}>{Object.keys(preview[0]).map((h) => (
                      <td key={h} className="whitespace-nowrap px-2.5 py-1.5 text-slate-600">{r[h] || "—"}</td>
                    ))}</tr>
                  ))}
                </tbody>
              </table>
            </div>
            {bulk.isPending ? <Spinner label="Updating & re-analyzing…" /> : (
              <button className="btn-primary" onClick={() => bulk.mutate(preview)}>
                <UserCog className="mr-1.5 h-4 w-4" /> Apply {preview.length} update(s)
              </button>
            )}
            {bulk.isSuccess && (
              <div className="rounded-lg border border-teal-200 bg-teal-50 px-4 py-3 text-[13px] text-teal-800">
                Updated {bulk.data?.updated} student(s).
                {(bulk.data?.errors || []).length > 0 && (
                  <ul className="mt-2 space-y-0.5 text-[12px]">
                    {bulk.data!.errors.slice(0, 8).map((e) => (
                      <li key={e.row}>row {e.row} ({e.usn}): {e.errors.join("; ")}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            {bulk.isError && <p className="text-[13px] text-rose-600">{(bulk.error as Error).message}</p>}
          </div>
        )}
      </Card>

      <Disclaimer>
        <UserCog className="mr-1 inline h-3.5 w-3.5" />
        Assessed scores you enter are recorded as institution-sourced (VERIFIED). Student-owned
        evidence (projects, internships, self-reported skills) is not editable here and is handled
        through the verification workflow.
      </Disclaimer>
    </div>
  );
}

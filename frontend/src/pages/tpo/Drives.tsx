import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Target } from "lucide-react";
import { api } from "../../api/client";
import { SKILL_LABELS } from "../../lib/placement";
import { Badge, Card, Disclaimer, ErrorBox, Spinner, Table } from "../../components/ui";

interface Drive {
  id: number; company_id: number; company: string; title: string; role: string;
  location: string | null; ctc: string | null; drive_date: string | null;
  deadline: string | null; open_positions: number | null; status: string;
  criteria_version: number; min_cgpa: number | null; min_readiness: number | null;
  required_skills: string[] | null; preferred_skills: string[] | null;
  nominated: number; shortlisted: number; selected: number;
}
interface DrivesResp { status: string; drives: Drive[] }
interface Company { id: number; name: string }
interface Skill { code: string; name: string }

const STATUS_CLS: Record<string, string> = {
  OPEN: "bg-teal-50 text-teal-700 border-teal-200",
  DRAFT: "bg-slate-100 text-slate-600 border-slate-200",
  CLOSED: "bg-amber-50 text-amber-700 border-amber-200",
  COMPLETED: "bg-slate-100 text-slate-500 border-slate-200",
};

export default function TpoDrives() {
  const qc = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["tpo-drives"],
    queryFn: () => api<DrivesResp>("/tpo/drives"),
  });
  const companiesQ = useQuery({
    queryKey: ["tpo-companies"],
    queryFn: () => api<{ companies: Company[] }>("/tpo/companies"),
  });
  const skillsQ = useQuery({
    queryKey: ["skills"],
    queryFn: () => api<{ skills: Skill[] }>("/tpo/skills/catalog"),
  });
  const [show, setShow] = useState(false);
  const [filter, setFilter] = useState<number | null>(null);

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      api(`/tpo/drives/${id}/status`, { method: "POST", body: { status } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tpo-drives"] }),
  });

  if (isLoading) return <Spinner label="Loading placement drives…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  const drives = filter ? data.drives.filter((d) => d.company_id === filter) : data.drives;
  const companies = companiesQ.data?.companies || [];

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Placement Drives</h1>
          <p className="mt-0.5 text-[13px] text-slate-500">
            A drive bundles a company's role with its structured eligibility criteria and
            match-quality inputs. Changing criteria bumps the criteria version and re-evaluations
            apply automatically.
          </p>
        </div>
        <div className="flex gap-2">
          <select className="input !w-auto" value={filter ?? ""} onChange={(e) => setFilter(e.target.value ? Number(e.target.value) : null)}>
            <option value="">All companies</option>
            {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <button className="btn-primary" onClick={() => setShow(!show)}>
            <Plus className="mr-1.5 h-4 w-4" /> New Drive
          </button>
        </div>
      </header>

      {show && (
        <DriveForm
          companies={companies}
          skills={skillsQ.data?.skills || []}
          onCreate={(b) =>
            api("/tpo/drives", { method: "POST", body: b }).then(() => {
              qc.invalidateQueries({ queryKey: ["tpo-drives"] });
              setShow(false);
            })
          }
          busy={false}
        />
      )}

      <Card>
        {drives.length === 0 ? (
          <p className="py-6 text-center text-[13px] text-slate-400">No drives yet — create one.</p>
        ) : (
          <Table head={
            <tr>
              <th>Drive</th><th>Company</th><th>Dates</th><th>Key criteria</th>
              <th>Pipeline</th><th>Status</th><th>Action</th>
            </tr>
          }>
            {drives.map((d) => (
              <tr key={d.id}>
                <td>
                  <div className="font-medium text-slate-800">{d.title}</div>
                  <div className="text-[11.5px] text-slate-400">
                    {d.role}{d.open_positions ? ` · ${d.open_positions} positions` : ""} · v{d.criteria_version}
                  </div>
                </td>
                <td className="text-[13px] text-slate-700">{d.company}</td>
                <td className="text-[12px] text-slate-500">
                  <div>Drive: {d.drive_date || "—"}</div>
                  <div>Deadline: {d.deadline || "—"}</div>
                </td>
                <td className="text-[12px] text-slate-600">
                  <div>{d.min_cgpa != null ? `CGPA ≥ ${d.min_cgpa}` : "No CGPA gate"}</div>
                  <div>
                    {(d.required_skills || []).slice(0, 3).map((s) => SKILL_LABELS[s] || s).join(", ")}
                    {(d.required_skills || []).length > 3 && ` +${d.required_skills!.length - 3}`}
                  </div>
                </td>
                <td className="text-[12px] tabular-nums text-slate-600">
                  <div>Nominated {d.nominated}</div>
                  <div>Shortlisted {d.shortlisted}</div>
                  <div>Selected {d.selected}</div>
                </td>
                <td><Badge cls={STATUS_CLS[d.status] || "bg-slate-100 text-slate-600 border-slate-200"}>{d.status}</Badge></td>
                <td>
                  <div className="flex gap-2">
                    {d.status === "DRAFT" && (
                      <button className="text-[12px] font-medium text-teal-700 hover:underline"
                        onClick={() => setStatus.mutate({ id: d.id, status: "OPEN" })}>Open</button>
                    )}
                    {d.status === "OPEN" && (
                      <button className="text-[12px] font-medium text-amber-700 hover:underline"
                        onClick={() => setStatus.mutate({ id: d.id, status: "CLOSED" })}>Close</button>
                    )}
                    {d.status === "CLOSED" && (
                      <button className="text-[12px] font-medium text-teal-700 hover:underline"
                        onClick={() => setStatus.mutate({ id: d.id, status: "COMPLETED" })}>Complete</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Disclaimer>
        <Target className="mr-1 inline h-3.5 w-3.5" />
        Package/CTC is shown only when you enter it and is never used to rank candidates.
      </Disclaimer>
    </div>
  );
}

function num(v: string): number | null {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : null;
}

function DriveForm({ companies, skills, onCreate }: {
  companies: Company[]; skills: Skill[];
  onCreate: (b: Record<string, unknown>) => void; busy: boolean;
}) {
  const [f, setF] = useState({
    company_id: companies[0]?.id ? String(companies[0].id) : "",
    title: "", role: "", job_description: "", location: "", ctc: "", employment_type: "",
    drive_date: "", deadline: "", open_positions: "",
    min_cgpa: "", min_tenth: "", min_twelfth: "", max_backlogs: "",
    min_readiness: "", min_coding: "", min_aptitude: "", min_communication: "",
    project_required: false, internship_required: false,
    target_branches: "", eligible_semesters: "",
    required_skills: [] as string[], preferred_skills: [] as string[],
    preferred_career_code: "", status: "DRAFT",
  });
  const set = (k: string, v: unknown) => setF({ ...f, [k]: v });
  const toggleSkill = (k: "required_skills" | "preferred_skills") => (code: string) => {
    const cur = f[k];
    set(k, cur.includes(code) ? cur.filter((c) => c !== code) : [...cur, code]);
  };
  const skillChips = (k: "required_skills" | "preferred_skills") => (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {skills.map((s) => (
        <button key={s.code} type="button"
          onClick={() => toggleSkill(k)(s.code)}
          className={`rounded-full border px-2.5 py-1 text-[11.5px] font-medium ${
            f[k].includes(s.code)
              ? "border-navy-600 bg-navy-800 text-white"
              : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50"
          }`}>
          {s.name}
        </button>
      ))}
    </div>
  );

  const submit = () => {
    onCreate({
      company_id: Number(f.company_id),
      title: f.title, role: f.role,
      job_description: f.job_description || null,
      location: f.location || null,
      ctc: f.ctc || null,
      employment_type: f.employment_type || null,
      drive_date: f.drive_date || null,
      deadline: f.deadline || null,
      open_positions: f.open_positions ? Number(f.open_positions) : null,
      min_cgpa: num(f.min_cgpa), min_tenth: num(f.min_tenth), min_twelfth: num(f.min_twelfth),
      max_backlogs: f.max_backlogs ? Number(f.max_backlogs) : null,
      min_readiness: num(f.min_readiness), min_coding: num(f.min_coding),
      min_aptitude: num(f.min_aptitude), min_communication: num(f.min_communication),
      project_required: f.project_required, internship_required: f.internship_required,
      target_branches: f.target_branches ? f.target_branches.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean) : null,
      eligible_semesters: f.eligible_semesters ? f.eligible_semesters.split(",").map((s) => Number(s.trim())).filter((n) => n > 0) : null,
      required_skills: f.required_skills, preferred_skills: f.preferred_skills,
      preferred_career_code: f.preferred_career_code || null,
      status: f.status,
    });
  };

  return (
    <Card title="New placement drive" subtitle="Mandatory criteria define eligibility; skills define match quality">
      <div className="grid gap-3 md:grid-cols-3">
        <div><label className="label">Company *</label>
          <select className="input mt-1.5" value={f.company_id} onChange={(e) => set("company_id", e.target.value)}>
            {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select></div>
        <div><label className="label">Drive title *</label>
          <input className="input mt-1.5" value={f.title} onChange={(e) => set("title", e.target.value)} placeholder="Software Engineer — Placement" /></div>
        <div><label className="label">Role *</label>
          <input className="input mt-1.5" value={f.role} onChange={(e) => set("role", e.target.value)} placeholder="Software Engineer" /></div>
        <div className="md:col-span-3"><label className="label">Job description</label>
          <textarea className="input mt-1.5" rows={2} value={f.job_description}
            onChange={(e) => set("job_description", e.target.value)} placeholder="What will they do?" /></div>
        <div><label className="label">Location</label>
          <input className="input mt-1.5" value={f.location} onChange={(e) => set("location", e.target.value)} /></div>
        <div><label className="label">Employment type</label>
          <input className="input mt-1.5" value={f.employment_type} onChange={(e) => set("employment_type", e.target.value)} placeholder="Full-time" /></div>
        <div><label className="label">CTC (optional, never used for ranking)</label>
          <input className="input mt-1.5" value={f.ctc} onChange={(e) => set("ctc", e.target.value)} placeholder="e.g. ₹6.5 LPA" /></div>
        <div><label className="label">Drive date</label>
          <input type="date" className="input mt-1.5" value={f.drive_date} onChange={(e) => set("drive_date", e.target.value)} /></div>
        <div><label className="label">Application deadline</label>
          <input type="date" className="input mt-1.5" value={f.deadline} onChange={(e) => set("deadline", e.target.value)} /></div>
        <div><label className="label">Open positions</label>
          <input type="number" className="input mt-1.5" value={f.open_positions} onChange={(e) => set("open_positions", e.target.value)} /></div>
      </div>

      <div className="mt-5 border-t border-slate-100 pt-4">
        <div className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-slate-500">
          Mandatory eligibility criteria (blank = no requirement)
        </div>
        <div className="grid gap-3 md:grid-cols-4">
          {([
            ["min_cgpa", "Min CGPA"], ["min_tenth", "Min 10th %"], ["min_twelfth", "Min 12th %"],
            ["max_backlogs", "Max backlogs"], ["min_readiness", "Min readiness"], ["min_coding", "Min coding score"],
            ["min_aptitude", "Min aptitude"], ["min_communication", "Min communication"],
          ] as [string, string][]).map(([k, label]) => (
            <div key={k}>
              <label className="label">{label}</label>
              <input className="input mt-1.5" value={(f as any)[k]}
                onChange={(e) => set(k, e.target.value)} placeholder="—" />
            </div>
          ))}
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <label className="flex items-center gap-2 text-[13px] text-slate-600">
            <input type="checkbox" className="h-4 w-4 accent-navy-700" checked={f.project_required}
              onChange={(e) => set("project_required", e.target.checked)} /> Verified project required
          </label>
          <label className="flex items-center gap-2 text-[13px] text-slate-600">
            <input type="checkbox" className="h-4 w-4 accent-navy-700" checked={f.internship_required}
              onChange={(e) => set("internship_required", e.target.checked)} /> Verified internship required
          </label>
          <div>
            <label className="label">Target branches (comma sep)</label>
            <input className="input mt-1.5" value={f.target_branches} onChange={(e) => set("target_branches", e.target.value)} placeholder="CSE, ISE" /></div>
          <div>
            <label className="label">Eligible semesters (comma sep)</label>
            <input className="input mt-1.5" value={f.eligible_semesters} onChange={(e) => set("eligible_semesters", e.target.value)} placeholder="6, 8" /></div>
        </div>
      </div>

      <div className="mt-5 border-t border-slate-100 pt-4">
        <div className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-slate-500">Match-quality inputs</div>
        <label className="label">Required skills (30% weight)</label>
        {skillChips("required_skills")}
        <div className="mt-4"><label className="label">Preferred skills (15% weight)</label></div>
        {skillChips("preferred_skills")}
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div><label className="label">Preferred career track</label>
            <select className="input mt-1.5" value={f.preferred_career_code}
              onChange={(e) => set("preferred_career_code", e.target.value)}>
              <option value="">Any (use student's best match)</option>
              <option value="FULL_STACK">Full-Stack Developer</option>
              <option value="DATA_ANALYST">Data Analyst</option>
            </select></div>
          <div><label className="label">Initial status</label>
            <select className="input mt-1.5" value={f.status} onChange={(e) => set("status", e.target.value)}>
              <option value="DRAFT">DRAFT</option>
              <option value="OPEN">OPEN</option>
            </select></div>
        </div>
      </div>

      <button className="btn-primary mt-5" disabled={!f.title.trim() || !f.role.trim() || !f.company_id} onClick={submit}>
        Create drive
      </button>
    </Card>
  );
}

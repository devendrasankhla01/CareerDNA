import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Building2, ChevronLeft, Eye } from "lucide-react";
import { api } from "../../api/client";
import { fmt, fmt1 } from "../../lib/format";
import { STAGE_META, skillLabel } from "../../lib/placement";
import { Badge, Bar, Card, Disclaimer, ErrorBox, Spinner, Table } from "../../components/ui";

interface Drive {
  id: number; title: string; role: string; status: string;
  location: string | null; ctc: string | null; drive_date: string | null; deadline: string | null;
  open_positions: number | null;
  criteria: {
    min_cgpa?: number | null; min_tenth?: number | null; min_twelfth?: number | null;
    max_backlogs?: number | null; min_readiness?: number | null; min_coding?: number | null;
    min_aptitude?: number | null; min_communication?: number | null;
    project_required?: boolean; internship_required?: boolean;
    target_branches?: string[] | null; eligible_semesters?: number[] | null;
    required_skills?: string[] | null; preferred_skills?: string[] | null;
  };
  counts: { nominated: number; shortlisted: number; interview: number; selected: number };
}
interface DrivesResp { status: string; drives: Drive[] }
interface CandRow {
  student_id: number; name: string; usn: string; branch: string; semester: number;
  cgpa: number | null; readiness: number | null; category: string | null;
  company_match: number | null; eligible: boolean | null;
  career_best: string | null; top_skills: string[];
  status: string; match_score: number | null; updated_at: string;
}
interface CandsResp { status: string; drive_id: number; role: string; rows: CandRow[]; tabs: Record<string, number> }
interface Detail {
  status: string;
  student: { id: number; name: string; usn: string; branch: string; semester: number; cgpa: number | null };
  analysis: {
    readiness: number | null; category: string | null; verification_coverage: number | null;
    company_match: number | null; eligible: boolean | null;
    career_best: string | null; career_score: number | null;
    top_strengths: string[]; development_areas: string[]; explanation: string[];
  };
  verified: {
    skills: Record<string, number>;
    projects: { title: string; tech_stack?: string[] | string | null; complexity?: string | null; type?: string | null }[];
    internships: { organization: string; role: string; domain?: string | null }[];
    certifications: { name: string; issuer: string | null }[];
  };
  candidate: { status: string; match_score: number | null; shortlisted_at: string | null; selected_at: string | null; selected_note: string | null };
}
const CAREER_LABEL: Record<string, string> = { FULL_STACK: "Full-Stack Developer", DATA_ANALYST: "Data Analyst" };

const TABS = [
  { key: "NOMINATED", label: "Nominated" },
  { key: "SHORTLISTED", label: "Shortlisted" },
  { key: "INTERVIEW", label: "Interview" },
  { key: "SELECTED", label: "Selected" },
  { key: "NOT_SELECTED", label: "Not Selected" },
];

export default function CompanyDrives() {
  const qc = useQueryClient();
  const drivesQ = useQuery({ queryKey: ["company-drives"], queryFn: () => api<DrivesResp>("/company/drives") });
  const [driveId, setDriveId] = useState<number | null>(null);
  const [tab, setTab] = useState("NOMINATED");
  const [viewing, setViewing] = useState<number | null>(null);

  const activeId = driveId ?? drivesQ.data?.drives.find((d) => d.status === "OPEN")?.id ?? drivesQ.data?.drives[0]?.id ?? null;

  const candsQ = useQuery({
    queryKey: ["company-cands", activeId, tab],
    queryFn: () => api<CandsResp>(`/company/drives/${activeId}/candidates?tab=${tab}`),
    enabled: activeId != null,
  });

  const transition = useMutation({
    mutationFn: (body: { student_id: number; status: string; note?: string }) =>
      api(`/company/drives/${activeId}/candidates/${body.student_id}/status`, {
        method: "POST", body: { status: body.status, note: body.note },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["company-cands", activeId] });
      qc.invalidateQueries({ queryKey: ["company-overview"] });
    },
  });

  if (drivesQ.isLoading) return <Spinner label="Loading your drives…" />;
  if (drivesQ.isError) return <ErrorBox message={(drivesQ.error as Error).message} onRetry={() => drivesQ.refetch()} />;
  if (!drivesQ.data || drivesQ.data.drives.length === 0) {
    return <Card><p className="text-sm text-slate-500">The TPO has not created any drives for your company yet.</p></Card>;
  }
  const drive = drivesQ.data.drives.find((d) => d.id === activeId) || drivesQ.data.drives[0];

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Drives & Candidates</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          Review the students the TPO nominated to your drives, shortlist, interview and select.
          Every action is recorded with your identity.
        </p>
      </header>

      <div className="flex flex-wrap gap-2">
        {drivesQ.data.drives.map((d) => (
          <button key={d.id} onClick={() => { setDriveId(d.id); setViewing(null); }}
            className={`rounded-lg border px-3.5 py-2 text-left transition ${
              d.id === activeId ? "border-navy-600 bg-navy-800 text-white" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}>
            <div className="text-[13px] font-semibold">{d.role}</div>
            <div className={`text-[11px] ${d.id === activeId ? "text-navy-200" : "text-slate-400"}`}>
              {d.title} · {d.status}
            </div>
          </button>
        ))}
      </div>

      <Card
        title={`${drive.title} — ${drive.role}`}
        subtitle={
          [drive.location, drive.ctc, drive.deadline && `deadline ${drive.deadline}`,
           drive.open_positions && `${drive.open_positions} positions`]
            .filter(Boolean).join(" · ") || undefined
        }
        actions={
          <div className="flex flex-wrap gap-1.5">
            {TABS.map((t) => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={`rounded-full border px-3 py-1 text-[12px] font-medium ${
                  tab === t.key ? "border-navy-700 bg-navy-800 text-white" : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50"
                }`}>
                {t.label} {fmt(candsQ.data?.tabs[t.key] ?? (drive.counts as Record<string, number>)[t.key.toLowerCase()] ?? 0)}
              </button>
            ))}
          </div>
        }>
        <div className="mb-4 flex flex-wrap gap-1.5">
          {(drive.criteria.required_skills || []).map((s) => (
            <span key={s} className="rounded-md border border-navy-200 bg-navy-50 px-2 py-0.5 text-[11px] font-medium text-navy-700">{skillLabel(s)}</span>
          ))}
          {(drive.criteria.preferred_skills || []).map((s) => (
            <span key={s} className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-500">pref: {skillLabel(s)}</span>
          ))}
          {drive.criteria.min_cgpa != null && <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-500">CGPA ≥ {drive.criteria.min_cgpa}</span>}
          {drive.criteria.min_readiness != null && <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-500">Readiness ≥ {drive.criteria.min_readiness}</span>}
          {drive.criteria.project_required && <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-500">Verified project req.</span>}
        </div>

        {viewing != null ? (
          <CandidateDetail
            driveId={drive.id} studentId={viewing}
            onBack={() => setViewing(null)}
            onAction={(status, note) => transition.mutate({ student_id: viewing, status, note })}
            busy={transition.isPending}
            error={transition.isError ? (transition.error as Error).message : null}
          />
        ) : (
          <>
            {candsQ.isLoading ? <Spinner label="Loading authorized candidates…" />
              : candsQ.isError ? <ErrorBox message={(candsQ.error as Error).message} onRetry={() => candsQ.refetch()} />
              : !candsQ.data || candsQ.data.rows.length === 0 ? (
                <p className="py-8 text-center text-[13px] text-slate-400">
                  {tab === "NOMINATED"
                    ? "No candidates nominated to this drive yet. The TPO nominates eligible students from Candidate Matching."
                    : `No candidates in the ${TABS.find((t) => t.key === tab)?.label.toLowerCase()} stage yet.`}
                </p>
              ) : (
                <Table head={
                  <tr>
                    <th>Student</th><th>Branch · Sem</th><th>CGPA</th><th>Readiness</th>
                    <th>Company Match</th><th>Career</th><th>Top skills</th><th>Stage</th><th></th>
                  </tr>
                }>
                  {candsQ.data.rows.map((r) => (
                    <CandidateRow key={r.student_id} r={r} onView={() => setViewing(r.student_id)} />
                  ))}
                </Table>
              )}
          </>
        )}
      </Card>

      <Disclaimer>
        You are seeing a TPO-authorized pool for your drives. Match scores are institution-computed
        and read-only for you. Selection is your decision; the TPO confirms official placements.
      </Disclaimer>
    </div>
  );
}

function CandidateRow({ r, onView }: { r: CandRow; onView: () => void }) {
  const m = STAGE_META[r.status];
  return (
    <tr>
      <td>
        <div className="font-medium text-slate-800">{r.name}</div>
        <div className="text-[11.5px] text-slate-400">{r.usn}</div>
      </td>
      <td className="text-[12.5px] text-slate-600">{r.branch} · S{r.semester}</td>
      <td className="tabular-nums text-slate-600">{fmt1(r.cgpa)}</td>
      <td className="tabular-nums text-slate-700">{fmt1(r.readiness)}</td>
      <td>
        <div className="flex items-center gap-2">
          <div className="w-14"><Bar value={r.company_match || 0} tone={(r.company_match || 0) >= 75 ? "teal" : "navy"} /></div>
          <span className="text-[12.5px] font-semibold tabular-nums text-slate-700">{fmt1(r.company_match)}</span>
        </div>
      </td>
      <td className="text-[12px] text-slate-600">{CAREER_LABEL[r.career_best || ""] || r.career_best || "—"}</td>
      <td className="max-w-[220px]">
        <div className="flex flex-wrap gap-1">
          {r.top_skills.slice(0, 4).map((s) => (
            <span key={s} className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10.5px] font-medium text-slate-600">{s}</span>
          ))}
        </div>
      </td>
      <td><Badge cls={m?.cls || ""}>{m?.label || r.status}</Badge></td>
      <td>
        <button className="text-navy-700 hover:underline text-[12.5px] font-medium" onClick={onView}>
          <Eye className="mr-1 inline h-3.5 w-3.5" />Review
        </button>
      </td>
    </tr>
  );
}

function CandidateDetail({ driveId, studentId, onBack, onAction, busy, error }: {
  driveId: number; studentId: number; onBack: () => void;
  onAction: (status: string, note?: string) => void; busy: boolean; error: string | null;
}) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["company-cand-detail", driveId, studentId],
    queryFn: () => api<Detail>(`/company/drives/${driveId}/candidates/${studentId}`),
  });
  const [note, setNote] = useState("");

  if (isLoading) return <Spinner label="Loading candidate profile…" />;
  if (isError || !data) return <ErrorBox message="Candidate profile unavailable." />;

  const st = data.student;
  const an = data.analysis;
  const v = data.verified;
  const acts: { to: string; label: string; kind: "primary" | "outline" | "danger" }[] = [];
  if (["NOMINATED", "COMPANY_REVIEWING"].includes(data.candidate.status))
    acts.push({ to: "SHORTLISTED", label: "Shortlist", kind: "primary" });
  if (["SHORTLISTED", "COMPANY_REVIEWING"].includes(data.candidate.status))
    acts.push({ to: "INTERVIEW", label: "Move to Interview", kind: "primary" });
  if (["SHORTLISTED", "INTERVIEW"].includes(data.candidate.status))
    acts.push({ to: "SELECTED", label: "Select", kind: "primary" });
  if (["SHORTLISTED", "INTERVIEW", "NOMINATED", "COMPANY_REVIEWING"].includes(data.candidate.status))
    acts.push({ to: "NOT_SELECTED", label: "Not Selected", kind: "danger" });

  return (
    <div className="space-y-4">
      <button className="flex items-center gap-1 text-[12.5px] font-medium text-navy-700 hover:underline" onClick={onBack}>
        <ChevronLeft className="h-4 w-4" /> Back to candidates
      </button>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-navy-800 text-[13px] font-semibold text-white">
              {st.name.split(" ").map((w) => w[0]).slice(0, 2).join("")}
            </div>
            <div>
              <div className="text-[16px] font-semibold text-slate-900">{st.name}</div>
              <div className="text-[12px] text-slate-400">{st.usn} · {st.branch} · Semester {st.semester} · CGPA {fmt1(st.cgpa)}</div>
            </div>
          </div>
          <div className="mt-2"><Badge cls={STAGE_META[data.candidate.status]?.cls || ""}>{STAGE_META[data.candidate.status]?.label || data.candidate.status}</Badge></div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">Company Match (read-only)</div>
          <div className="text-3xl font-semibold tabular-nums text-navy-800">{fmt1(an.company_match)}</div>
          <div className="w-40"><Bar value={an.company_match || 0} tone={(an.company_match || 0) >= 75 ? "teal" : "navy"} /></div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Analysis">
          <dl className="space-y-2 text-[13px]">
            <div className="flex justify-between"><dt className="text-slate-500">Placement Readiness</dt><dd className="font-semibold tabular-nums text-slate-800">{fmt1(an.readiness)}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Readiness band</dt><dd className="font-medium text-slate-700">{an.category || "—"}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Best career match</dt><dd className="font-medium text-slate-700">{CAREER_LABEL[an.career_best || ""] || "—"}{an.career_score ? ` (${fmt1(an.career_score)})` : ""}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Verification coverage</dt><dd className="font-semibold tabular-nums text-slate-800">{fmt(an.verification_coverage)}</dd></div>
          </dl>
          {an.top_strengths.length > 0 && (
            <div className="mt-3">
              <div className="mb-1 text-[11.5px] font-medium text-slate-500">Strengths for this role</div>
              <div className="flex flex-wrap gap-1.5">
                {an.top_strengths.map((s) => (
                  <span key={s} className="rounded-md border border-teal-200 bg-teal-50 px-2 py-0.5 text-[11px] font-medium text-teal-700">{s}</span>
                ))}
              </div>
            </div>
          )}
          {an.explanation.slice(0, 2).map((l, i) => (
            <p key={i} className="mt-2 text-[12px] leading-relaxed text-slate-500">{l}</p>
          ))}
        </Card>

        <Card title="Verified evidence">
          <div className="space-y-3">
            <div>
              <div className="mb-1.5 text-[11.5px] font-medium text-slate-500">Skills (verified)</div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(v.skills).slice(0, 10).map(([code, sc]) => (
                  <span key={code} className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                    {skillLabel(code)} {fmt(sc)}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-1.5 text-[11.5px] font-medium text-slate-500">Projects ({v.projects.length})</div>
              {v.projects.length === 0 ? <p className="text-[12px] text-slate-400">None verified.</p> : (
                <ul className="space-y-1.5">
                  {v.projects.map((p, i) => (
                    <li key={i} className="text-[12.5px] text-slate-600">
                      <span className="font-medium text-slate-700">{p.title}</span>
                      {p.complexity && <span className="text-slate-400"> · {p.complexity}</span>}
                      {p.tech_stack && <div className="text-[11px] text-slate-400">{Array.isArray(p.tech_stack) ? p.tech_stack.join(", ") : p.tech_stack}</div>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <div className="mb-1.5 text-[11.5px] font-medium text-slate-500">Internships ({v.internships.length})</div>
              {v.internships.length === 0 ? <p className="text-[12px] text-slate-400">None verified.</p> : (
                <ul className="space-y-1">
                  {v.internships.map((x, i) => (
                    <li key={i} className="text-[12.5px] text-slate-600">
                      {x.role} · <span className="text-slate-500">{x.organization}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            {v.certifications.length > 0 && (
              <div>
                <div className="mb-1.5 text-[11.5px] font-medium text-slate-500">Certifications</div>
                <ul className="space-y-1">
                  {v.certifications.map((x, i) => (
                    <li key={i} className="text-[12.5px] text-slate-600">{x.name}{x.issuer ? ` · ${x.issuer}` : ""}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Card>

        <Card title="Your decision" subtitle="Recorded with your identity and a note">
          {["PLACED", "NOT_SELECTED"].includes(data.candidate.status) ? (
            <div className="space-y-2 text-[13px] text-slate-600">
              <p>Stage: <Badge cls={STAGE_META[data.candidate.status]?.cls || ""}>{STAGE_META[data.candidate.status]?.label || data.candidate.status}</Badge></p>
              {data.candidate.selected_at && <p>Selected {new Date(data.candidate.selected_at).toLocaleDateString("en-IN")}</p>}
              {data.candidate.selected_note && <p className="text-slate-500">Note: {data.candidate.selected_note}</p>}
              {data.candidate.status === "PLACED" && (
                <p className="font-medium text-teal-700">Placement confirmed by the TPO.</p>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <textarea
                className="input" rows={2} placeholder="Decision note (required for select / not selected)"
                value={note} onChange={(e) => setNote(e.target.value)} />
              <div className="flex flex-wrap gap-2">
                {acts.map((a) => (
                  <button
                    key={a.to}
                    disabled={busy || (a.to === "SELECTED" || a.to === "NOT_SELECTED" ? !note.trim() : false)}
                    onClick={() => onAction(a.to, note || undefined)}
                    className={a.kind === "primary" ? "btn-primary !py-2" : a.kind === "danger"
                      ? "btn-outline !py-2 !border-rose-300 !text-rose-700 hover:!bg-rose-50"
                      : "btn-outline !py-2"}>
                    {a.to === "SELECTED" && <BadgeCheck className="mr-1.5 h-4 w-4" />}
                    {a.label}
                  </button>
                ))}
              </div>
              {error && <p className="text-[12.5px] text-rose-600">{error}</p>}
              <p className="text-[11.5px] leading-relaxed text-slate-400">
                Selecting does not create an official placement — the TPO confirms it afterwards.
              </p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

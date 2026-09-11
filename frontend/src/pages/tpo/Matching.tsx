import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Send, ShieldCheck } from "lucide-react";
import { api } from "../../api/client";
import { fmt, fmt1 } from "../../lib/format";
import { skillLabel } from "../../lib/placement";
import { Badge, Bar, Card, Disclaimer, ErrorBox, Spinner, Table } from "../../components/ui";

interface Blocker { key: string; label: string; required: string; actual: string; actionable: boolean }
interface Candidate {
  student_id: number; usn: string; name: string; branch: string; semester: number;
  readiness: number | null; category: string | null; cgpa: number | null;
  coding: number | null; aptitude: number | null; communication: number | null;
  career_best: string | null;
  eligible: boolean; almost_eligible: boolean; match_score: number;
  mandatory_blockers: Blocker[]; actionable_blockers: Blocker[];
  matched_requirements: string[]; improvement_opportunities: string[];
  explanation: string[];
  candidate_status: string | null;
}
interface Pipeline {
  eligible: number; almost_eligible: number; not_eligible: number; interested: number;
  nominated: number; reviewing: number; shortlisted: number; interview: number;
  selected: number; placed: number; not_selected: number; analyzed: number;
  common_blockers: { key: string; label: string; count: number }[];
}
interface DriveInfo { drive_id: number; company: { name: string }; title: string; role: string; status: string; deadline?: string | null }
interface MatchResp {
  status: string; drive: DriveInfo; weights: Record<string, number>;
  components: Record<string, string>; candidates: Candidate[]; pipeline: Pipeline;
}
interface DriveRow { id: number; title: string; company: string; status: string }

const TABS = [
  { key: "all", label: "All", pred: (c: Candidate) => true },
  { key: "eligible", label: "Eligible", pred: (c: Candidate) => c.eligible },
  { key: "almost", label: "Almost Eligible", pred: (c: Candidate) => !c.eligible && c.almost_eligible },
  { key: "not", label: "Not Eligible", pred: (c: Candidate) => !c.eligible && !c.almost_eligible },
];

export default function TpoMatching() {
  const qc = useQueryClient();
  const drivesQ = useQuery({
    queryKey: ["tpo-drives"],
    queryFn: () => api<{ drives: DriveRow[] }>("/tpo/drives"),
  });
  const [driveId, setDriveId] = useState<number | null>(null);
  const [tab, setTab] = useState("all");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [note, setNote] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  const activeDriveId = driveId || drivesQ.data?.drives.find((d) => d.status === "OPEN")?.id || drivesQ.data?.drives[0]?.id || null;

  const matchQ = useQuery({
    queryKey: ["tpo-matching", activeDriveId],
    queryFn: () => api<MatchResp>(`/tpo/matching/drives/${activeDriveId}`),
    enabled: activeDriveId != null,
  });

  const nominate = useMutation({
    mutationFn: () =>
      api(`/tpo/matching/drives/${activeDriveId}/nominate`, {
        method: "POST", body: { student_ids: [...selected], note: note || null },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tpo-matching", activeDriveId] });
      setSelected(new Set());
      setNote("");
    },
  });

  const data = matchQ.data;
  const visible = useMemo(() => {
    const t = TABS.find((t) => t.key === tab) || TABS[0];
    return (data?.candidates || []).filter(t.pred);
  }, [data, tab]);

  if (drivesQ.isLoading) return <Spinner label="Loading placement drives…" />;
  if (drivesQ.isError) return <ErrorBox message={(drivesQ.error as Error).message} onRetry={() => drivesQ.refetch()} />;
  if (!drivesQ.data || drivesQ.data.drives.length === 0) {
    return <ErrorBox message="No placement drives yet. Create one under Placement Drives first." />;
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Candidate Matching</h1>
          <p className="mt-0.5 text-[13px] text-slate-500">
            The Placement Match Engine evaluates every analyzed student against a drive's
            mandatory criteria, then ranks by a transparent weighted match score.
          </p>
        </div>
        <select
          className="input !w-auto min-w-72"
          value={activeDriveId ?? ""}
          onChange={(e) => { setDriveId(Number(e.target.value)); setSelected(new Set()); }}
        >
          {drivesQ.data.drives.map((d) => (
            <option key={d.id} value={d.id}>{d.company} — {d.title} ({d.status})</option>
          ))}
        </select>
      </header>

      {matchQ.isLoading ? <Spinner label="Evaluating eligibility & match for this drive…" />
        : matchQ.isError ? <ErrorBox message={(matchQ.error as Error).message} onRetry={() => matchQ.refetch()} />
        : data && (
          <>
            <PipelineStrip p={data.pipeline} />

            <Card
              title={`${data.drive.company.name} · ${data.drive.title}`}
              subtitle={`${data.drive.role} · ${data.pipeline.analyzed} analyzed students evaluated`}
              actions={
                <div className="flex flex-wrap gap-1.5">
                  {TABS.map((t) => (
                    <button key={t.key} onClick={() => setTab(t.key)}
                      className={`rounded-full border px-3 py-1 text-[12px] font-medium ${tab === t.key
                        ? "border-navy-700 bg-navy-800 text-white"
                        : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50"}`}>
                      {t.label}
                    </button>
                  ))}
                </div>
              }>
              {selected.size > 0 && (
                <div className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-navy-200 bg-navy-50/60 px-4 py-3">
                  <span className="text-[13px] font-semibold text-navy-800">{selected.size} eligible student(s) selected</span>
                  <input className="input !w-auto flex-1 min-w-48" placeholder="Nomination note (audited)"
                    value={note} onChange={(e) => setNote(e.target.value)} />
                  <button className="btn-primary" disabled={nominate.isPending} onClick={() => nominate.mutate()}>
                    <Send className="mr-1.5 h-4 w-4" />
                    {nominate.isPending ? "Nominating…" : `Nominate ${selected.size}`}
                  </button>
                </div>
              )}
              {nominate.isSuccess && (
                <div className="mb-4 rounded-lg border border-teal-200 bg-teal-50 px-4 py-3 text-[13px] text-teal-800">
                  Nominated. Skipped: {JSON.stringify((nominate.data as any).skipped || [])}
                </div>
              )}
              <Table head={
                <tr>
                  <th className="w-8"></th>
                  <th>Student</th><th>Branch · Sem</th><th>Readiness</th><th>CGPA</th>
                  <th>Coding</th><th>Aptitude</th><th>Comm.</th><th>Career (best)</th>
                  <th>Company Match</th><th>Status</th><th></th>
                </tr>
              }>
                {visible.map((c) => (
                  <CandidateRow key={c.student_id} c={c} expanded={expanded === c.student_id}
                    onExpand={() => setExpanded(expanded === c.student_id ? null : c.student_id)}
                    checked={selected.has(c.student_id)}
                    onCheck={(v) => {
                      const n = new Set(selected);
                      if (v) n.add(c.student_id); else n.delete(c.student_id);
                      setSelected(n);
                    }} />
                ))}
              </Table>
              {visible.length === 0 && (
                <p className="py-6 text-center text-[13px] text-slate-400">No students in this filter.</p>
              )}
            </Card>

            <div className="grid gap-4 md:grid-cols-2">
              <Card title="Match weight breakdown" subtitle="Configured in app config — transparent, not a black box">
                <ul className="space-y-2.5">
                  {Object.entries(data.weights).map(([k, w]) => (
                    <li key={k} className="flex items-center gap-3 text-[13px]">
                      <span className="w-44 text-slate-600">{data.components[k] || k}</span>
                      <div className="w-40"><Bar value={w * 100} tone="navy" /></div>
                      <span className="w-12 text-right font-semibold tabular-nums text-slate-700">{Math.round(w * 100)}%</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-[11.5px] text-slate-400">
                  Weights are prototype values, documented in the methodology. The ML readiness
                  model is one input only — mandatory eligibility is never averaged away.
                </p>
              </Card>
              <Card title="Common blockers" subtitle="Why students are not yet eligible for this drive">
                {(data.pipeline.common_blockers || []).length === 0 ? (
                  <p className="text-[13px] text-slate-500">No recurring blockers among analyzed students.</p>
                ) : (
                  <ul className="space-y-2.5">
                    {data.pipeline.common_blockers.map((b) => (
                      <li key={b.key} className="flex items-center gap-3 text-[13px]">
                        <span className="w-44 text-slate-600">{b.label}</span>
                        <div className="w-40"><Bar value={b.count} max={data.pipeline.analyzed} tone="rose" /></div>
                        <span className="w-12 text-right font-semibold tabular-nums text-slate-700">{b.count}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          </>
        )}

      <Disclaimer>
        <ShieldCheck className="mr-1 inline h-3.5 w-3.5" />
        The engine recommends; you choose. Nominations are institutional decisions and are
        recorded with your identity and the student's criteria state at nomination time. Only
        currently-eligible students can be nominated under the default policy.
      </Disclaimer>
    </div>
  );
}

function PipelineStrip({ p }: { p: Pipeline }) {
  const steps = [
    { label: "Eligible", value: p.eligible, cls: "text-teal-700" },
    { label: "Interested", value: p.interested, cls: "text-slate-700" },
    { label: "Nominated", value: p.nominated, cls: "text-navy-700" },
    { label: "Shortlisted", value: p.shortlisted, cls: "text-violet-700" },
    { label: "Interview", value: p.interview, cls: "text-sky-700" },
    { label: "Selected", value: p.selected, cls: "text-amber-700" },
    { label: "Placed", value: p.placed, cls: "text-teal-700" },
  ];
  return (
    <div className="card flex flex-wrap items-center gap-x-6 gap-y-3 px-5 py-4">
      {steps.map((s, i) => (
        <div key={s.label} className="flex items-center gap-6">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{s.label}</div>
            <div className={`text-xl font-semibold tabular-nums ${s.cls}`}>{fmt(s.value)}</div>
          </div>
          {i < steps.length - 1 && <div className="hidden h-8 w-px bg-slate-200 sm:block" />}
        </div>
      ))}
      <div className="ml-auto text-[11.5px] text-slate-400">
        {p.almost_eligible} almost eligible · {p.not_eligible} not eligible (of {p.analyzed} analyzed)
      </div>
    </div>
  );
}

function CandidateRow({ c, expanded, onExpand, checked, onCheck }: {
  c: Candidate; expanded: boolean; onExpand: () => void; checked: boolean; onCheck: (v: boolean) => void;
}) {
  return (
    <>
      <tr className={expanded ? "bg-navy-50/30" : ""}>
        <td>
          <input type="checkbox" className="h-4 w-4 accent-navy-700"
            disabled={!c.eligible} checked={checked} onChange={(e) => onCheck(e.target.checked)} />
        </td>
        <td>
          <div className="font-medium text-slate-800">{c.name}</div>
          <div className="text-[11.5px] text-slate-400">{c.usn}</div>
        </td>
        <td className="text-[12.5px] text-slate-600">{c.branch} · S{c.semester}</td>
        <td className="tabular-nums text-slate-700">{fmt1(c.readiness)}</td>
        <td className="tabular-nums text-slate-600">{fmt1(c.cgpa)}</td>
        <td className="tabular-nums text-slate-600">{fmt(c.coding)}</td>
        <td className="tabular-nums text-slate-600">{fmt(c.aptitude)}</td>
        <td className="tabular-nums text-slate-600">{fmt(c.communication)}</td>
        <td className="text-[12.5px] text-slate-600">{c.career_best || "—"}</td>
        <td>
          <div className="flex items-center gap-2">
            <div className="w-14"><Bar value={c.match_score} tone={c.eligible ? "teal" : "amber"} /></div>
            <span className="text-[12.5px] font-semibold tabular-nums text-slate-700">{fmt1(c.match_score)}</span>
          </div>
        </td>
        <td>
          <div className="space-y-1">
            {c.eligible
              ? <Badge cls="bg-teal-50 text-teal-700 border-teal-200">Eligible</Badge>
              : c.almost_eligible
                ? <Badge cls="bg-amber-50 text-amber-700 border-amber-200">Almost</Badge>
                : <Badge cls="bg-rose-50 text-rose-700 border-rose-200">Not eligible</Badge>}
            {c.candidate_status && (
              <div className="text-[11px] font-medium text-navy-600">{c.candidate_status}</div>
            )}
          </div>
        </td>
        <td>
          <button className="text-slate-400 hover:text-slate-700" onClick={onExpand}>
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={12} className="bg-slate-50/70">
            <div className="grid gap-4 px-2 py-3 md:grid-cols-3">
              <div>
                <div className="mb-1.5 text-[11.5px] font-semibold uppercase tracking-wide text-slate-500">Evaluation</div>
                {c.explanation.map((l, i) => (
                  <p key={i} className="text-[12.5px] leading-relaxed text-slate-600">{l}</p>
                ))}
              </div>
              <div>
                <div className="mb-1.5 text-[11.5px] font-semibold uppercase tracking-wide text-slate-500">Requirements met</div>
                <div className="flex flex-wrap gap-1.5">
                  {c.matched_requirements.length
                    ? c.matched_requirements.map((m) => (
                      <span key={m} className="rounded-md border border-teal-200 bg-teal-50 px-2 py-0.5 text-[11px] font-medium text-teal-700">{m}</span>
                    ))
                    : <span className="text-[12px] text-slate-400">None of the set mandatory criteria are met.</span>}
                </div>
              </div>
              <div>
                <div className="mb-1.5 text-[11.5px] font-semibold uppercase tracking-wide text-slate-500">Blockers / improvements</div>
                <ul className="space-y-1">
                  {c.mandatory_blockers.map((b) => (
                    <li key={b.key} className="text-[12.5px] text-slate-600">
                      <span className="font-medium text-slate-800">{b.label}</span>: {b.actual} vs {b.required}
                      <span className={`ml-1.5 text-[11px] font-medium ${b.actionable ? "text-amber-600" : "text-slate-400"}`}>
                        {b.actionable ? "· improvable" : "· fixed"}
                      </span>
                    </li>
                  ))}
                  {c.improvement_opportunities.map((m) => (
                    <li key={m} className="text-[12.5px] text-slate-500">→ {m}</li>
                  ))}
                </ul>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

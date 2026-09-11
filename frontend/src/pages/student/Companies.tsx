import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, CalendarDays, Check, ChevronDown, ChevronUp, MapPin, Target } from "lucide-react";
import { api } from "../../api/client";
import { fmt1 } from "../../lib/format";
import { skillLabel as sLabel } from "../../lib/placement";
import { Bar, Badge, Card, Disclaimer, ErrorBox, Spinner } from "../../components/ui";

interface Blocker { key: string; label: string; required: string; actual: string; actionable: boolean }
interface Opp {
  drive_id: number;
  company: { id: number; name: string; industry?: string | null; location?: string | null };
  title: string; role: string; location?: string | null; ctc?: string | null;
  drive_date?: string | null; deadline?: string | null;
  status: string;
  criteria: {
    min_cgpa?: number | null; min_tenth?: number | null; min_twelfth?: number | null;
    max_backlogs?: number | null; min_readiness?: number | null; min_coding?: number | null;
    min_aptitude?: number | null; min_communication?: number | null;
    project_required?: boolean; internship_required?: boolean;
    target_branches?: string[] | null; eligible_semesters?: number[] | null;
    required_skills?: string[] | null; preferred_skills?: string[] | null;
    preferred_career_code?: string | null;
  };
  eligible: boolean; almost_eligible: boolean; match_score: number;
  mandatory_blockers: Blocker[]; actionable_blockers: Blocker[];
  matched_requirements: string[]; required_matches: string[]; preferred_matches: string[];
  improvement_opportunities: string[]; explanation: string[];
}
interface Resp { status: string; opportunities: Opp[]; best_opportunities: Opp[]; message?: string }

const ELIG_BADGE: Record<string, string> = {
  eligible: "bg-teal-50 text-teal-700 border-teal-200",
  almost: "bg-amber-50 text-amber-700 border-amber-200",
  not: "bg-rose-50 text-rose-700 border-rose-200",
};

export default function Companies() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["student-companies"],
    queryFn: () => api<Resp>("/student/companies"),
  });
  const [open, setOpen] = useState<number | null>(null);

  if (isLoading) return <Spinner label="Matching you against open company drives…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  const opps = data.opportunities;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Company Opportunities</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          Open placement drives evaluated by the Placement Match Engine against your verified
          profile. <span className="font-medium">Eligible</span> means you satisfy every mandatory
          requirement; the match score is a separate 0–100 alignment estimate.
        </p>
      </header>

      {data.message && (
        <Card><p className="text-sm text-slate-600">{data.message}</p></Card>
      )}

      {opps.length === 0 && !data.message && (
        <Card>
          <p className="text-sm text-slate-500">
            No open placement drives right now. Check back after the TPO opens new drives.
          </p>
        </Card>
      )}

      <div className="space-y-4">
        {opps.map((o) => (
          <OpportunityCard
            key={o.drive_id}
            o={o}
            open={open === o.drive_id}
            onToggle={() => setOpen(open === o.drive_id ? null : o.drive_id)}
          />
        ))}
      </div>

      <Disclaimer>
        <Target className="mr-1 inline h-3.5 w-3.5" />
        Company Match is decision support, not a selection promise. The TPO nominates students and
        companies make their own recruitment decisions. Expressing interest does not guarantee a
        nomination.
      </Disclaimer>
    </div>
  );
}

function OpportunityCard({ o, open, onToggle }: { o: Opp; open: boolean; onToggle: () => void }) {
  const qc = useQueryClient();
  const interest = useMutation({
    mutationFn: () => api(`/student/companies/${o.drive_id}/interest`, { method: "POST", body: {} }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["student-companies"] }),
  });

  const badge = o.eligible ? "eligible" : o.almost_eligible ? "almost" : "not";
  const criteriaChips: string[] = [];
  if (o.criteria.min_cgpa != null) criteriaChips.push(`CGPA ≥ ${o.criteria.min_cgpa}`);
  if (o.criteria.min_readiness != null) criteriaChips.push(`Readiness ≥ ${o.criteria.min_readiness}`);
  if (o.criteria.min_coding != null) criteriaChips.push(`Coding ≥ ${o.criteria.min_coding}`);
  if (o.criteria.min_aptitude != null) criteriaChips.push(`Aptitude ≥ ${o.criteria.min_aptitude}`);
  if (o.criteria.min_communication != null) criteriaChips.push(`Communication ≥ ${o.criteria.min_communication}`);
  if (o.criteria.max_backlogs != null) criteriaChips.push(`Backlogs ≤ ${o.criteria.max_backlogs}`);
  if (o.criteria.project_required) criteriaChips.push("Verified project required");
  if (o.criteria.internship_required) criteriaChips.push("Verified internship required");
  if (o.criteria.target_branches?.length) criteriaChips.push(`Branches: ${o.criteria.target_branches.join(", ")}`);
  if (o.criteria.eligible_semesters?.length) criteriaChips.push(`Semesters: ${o.criteria.eligible_semesters.join(", ")}`);

  return (
    <Card className="!p-0 overflow-hidden">
      <div className="flex flex-col gap-4 p-5 md:flex-row md:items-start">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-navy-50 text-navy-700">
          <Building2 className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[15px] font-semibold text-slate-900">{o.company.name}</h3>
            <Badge cls={ELIG_BADGE[badge]}>
              {o.eligible ? "Eligible" : o.almost_eligible ? "Almost Eligible" : "Not Currently Eligible"}
            </Badge>
          </div>
          <div className="mt-0.5 text-[13.5px] font-medium text-navy-700">{o.role}</div>
          <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-slate-500">
            <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{o.location || o.company.location || "—"}</span>
            {o.deadline && <span className="flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" />Apply by {o.deadline}</span>}
            {o.ctc && <span>{o.ctc}</span>}
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {criteriaChips.map((c) => (
              <span key={c} className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600">{c}</span>
            ))}
            {(o.criteria.required_skills || []).map((s) => (
              <span key={s} className="rounded-md border border-navy-200 bg-navy-50 px-2 py-0.5 text-[11px] font-medium text-navy-700">{sLabel(s)}</span>
            ))}
          </div>
        </div>
        <div className="flex shrink-0 flex-row items-center gap-4 md:flex-col md:items-end md:gap-3">
          <div className="text-right">
            <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">Company Match</div>
            <div className="text-2xl font-semibold tabular-nums text-navy-800">{fmt1(o.match_score)}</div>
          </div>
          <div className="w-28"><Bar value={o.match_score} tone={o.match_score >= 75 ? "teal" : o.match_score >= 55 ? "navy" : "amber"} /></div>
          <div className="flex gap-2">
            <button className="btn-outline !py-1.5" onClick={onToggle}>
              {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              {open ? "Hide" : "Why?"}
            </button>
            <button
              className="btn-primary !py-1.5"
              disabled={interest.isPending || o.eligible === false && !o.almost_eligible}
              onClick={() => interest.mutate()}
            >
              {interest.isPending ? "…" : <><Check className="mr-1 h-4 w-4" />Express Interest</>}
            </button>
          </div>
          {interest.isSuccess && (
            <p className="text-[11.5px] font-medium text-teal-700">Interest recorded — TPO will review</p>
          )}
        </div>
      </div>

      {open && (
        <div className="border-t border-slate-100 bg-slate-50/60 px-5 py-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <div className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-slate-500">Why this evaluation</div>
              <ul className="space-y-1.5">
                {o.explanation.map((line, i) => (
                  <li key={i} className="flex gap-2 text-[13px] leading-relaxed text-slate-600">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-navy-400" />{line}
                  </li>
                ))}
              </ul>
              {o.matched_requirements.length > 0 && (
                <div className="mt-3">
                  <div className="mb-1.5 text-[11.5px] font-medium text-teal-700">Requirements you meet</div>
                  <div className="flex flex-wrap gap-1.5">
                    {o.matched_requirements.map((m) => (
                      <span key={m} className="rounded-md border border-teal-200 bg-teal-50 px-2 py-0.5 text-[11px] font-medium text-teal-700">{m}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div>
              {o.mandatory_blockers.length > 0 ? (
                <>
                  <div className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-rose-600">
                    Mandatory requirements currently unmet
                  </div>
                  <ul className="space-y-1.5">
                    {o.mandatory_blockers.map((b) => (
                      <li key={b.key} className="text-[13px] text-slate-600">
                        <span className="font-medium text-slate-800">{b.label}</span>: {b.actual} (required {b.required})
                        <Badge cls={b.actionable ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-slate-100 text-slate-500 border-slate-200"}>
                          {b.actionable ? "improvable" : "fixed by institution"}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="text-[13px] font-medium text-teal-700">
                  You meet every mandatory requirement for this drive.
                </p>
              )}
              {o.improvement_opportunities.length > 0 && (
                <div className="mt-3">
                  <div className="mb-1.5 text-[11.5px] font-medium text-slate-500">Largest improvement opportunities</div>
                  <div className="flex flex-wrap gap-1.5">
                    {o.improvement_opportunities.map((m) => (
                      <span key={m} className="rounded-md border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600">{m}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

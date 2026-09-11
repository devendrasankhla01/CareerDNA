import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Building2 } from "lucide-react";
import { api } from "../../api/client";
import { useAuth } from "../../lib/auth";
import { fmt } from "../../lib/format";
import { Card, Disclaimer, ErrorBox, Spinner, Stat } from "../../components/ui";

interface Pipeline {
  eligible: number; almost_eligible: number; not_eligible: number; interested: number;
  nominated: number; reviewing: number; shortlisted: number; interview: number;
  selected: number; placed: number; not_selected: number; analyzed: number;
}
interface Resp {
  status: string;
  company: { id: number; name: string };
  open_drives: number; total_drives: number;
  candidates: { nominated: number; shortlisted: number; interview: number; selected: number; placed: number; not_selected: number };
  open_pipeline: Record<string, Pipeline>;
}

export default function CompanyOverview() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["company-overview"],
    queryFn: () => api<Resp>("/company/overview"),
  });

  if (isLoading) return <Spinner label="Loading your recruitment overview…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  const c = data.candidates;
  const pipelines = Object.values(data.open_pipeline);
  const totalEligible = pipelines.reduce((s, p) => s + p.eligible, 0);

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Welcome, {data.company.name}</h1>
          <p className="mt-0.5 text-[13px] text-slate-500">
            You see only the students the institution's TPO has nominated to your drives —
            never the full student database.
          </p>
        </div>
        <button className="btn-primary" onClick={() => navigate("/company/drives")}>
          Review candidates <ArrowRight className="ml-1.5 h-4 w-4" />
        </button>
      </header>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Stat label="Open drives" value={fmt(data.open_drives)} sub={`${fmt(data.total_drives)} total`} />
        <Stat label="Nominated candidates" value={fmt(c.nominated)} sub="authorized to your drives by the TPO" />
        <Stat label="Shortlisted + interview" value={fmt(c.shortlisted + c.interview)} sub="in active evaluation" />
        <Stat label="Selected" value={fmt(c.selected)} tone="good" sub={`${fmt(c.placed)} confirmed by TPO`} />
      </div>

      {pipelines.length > 0 && (
        <Card title="Open drive funnel"
          subtitle="Eligible pool → your shortlist → interview → selection (per open drive)">
          <div className="space-y-4">
            {pipelines.map((p) => (
              <div key={p.analyzed} className="flex flex-wrap items-center gap-x-8 gap-y-2 text-[13px]">
                {[
                  ["Eligible pool", p.eligible, "text-teal-700"],
                  ["Nominated to you", p.nominated, "text-navy-700"],
                  ["Shortlisted", p.shortlisted, "text-violet-700"],
                  ["Interview", p.interview, "text-sky-700"],
                  ["Selected", p.selected, "text-amber-700"],
                  ["Placed", p.placed, "text-teal-700"],
                ].map(([label, v, cls]) => (
                  <div key={label as string} className="flex items-baseline gap-2">
                    <span className="text-slate-500">{label}</span>
                    <span className={`text-lg font-semibold tabular-nums ${cls}`}>{fmt(v as number)}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
          <p className="mt-4 text-[12px] text-slate-400">
            {totalEligible} analyzed students meet the mandatory criteria across your open drives.
            The TPO decides whom to nominate; you shortlist and select from your pool.
          </p>
        </Card>
      )}

      <Card title="How this works">
        <ol className="list-decimal space-y-2 pl-5 text-[13px] text-slate-600">
          <li>The TPO creates your drive and evaluates candidates with the Placement Match Engine.</li>
          <li>The TPO nominates eligible candidates to your drive — that is your candidate pool.</li>
          <li>You review profiles, shortlist, interview, and select (every action is audited).</li>
          <li>The TPO confirms official placements on the institution's record.</li>
        </ol>
      </Card>

      <Disclaimer>
        <Building2 className="mr-1 inline h-3.5 w-3.5" />
        Company Match scores are decision support provided by the institution; they are not
        editable by you and are not hiring guarantees. You will not see students who only expressed
        interest, other companies' decisions, or private contact details.
      </Disclaimer>
    </div>
  );
}

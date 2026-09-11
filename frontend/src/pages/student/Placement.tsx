import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, Building2, CircleDashed, MapPin } from "lucide-react";
import { api } from "../../api/client";
import { timeAgo } from "../../lib/format";
import { JOURNEY_STEPS, STAGE_META } from "../../lib/placement";
import { Badge, Card, Disclaimer, ErrorBox, Spinner, EmptyState } from "../../components/ui";

interface JourneyItem {
  candidate_id: number; drive_id: number | null;
  company: string | null; role: string | null; title: string | null;
  status: string; match_score: number | null;
  updated_at: string; confirmed_at: string | null;
}
interface Resp { status: string; journey: JourneyItem[]; current_stage: string | null }

export default function PlacementJourney() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["student-journey"],
    queryFn: () => api<Resp>("/student/placement-journey"),
  });

  if (isLoading) return <Spinner label="Loading your placement journey…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  const current = data.journey[0];

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Placement Journey</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          Every stage of your participation in placement drives. Only the TPO can mark a
          placement as officially confirmed.
        </p>
      </header>

      {data.journey.length === 0 ? (
        <Card>
          <EmptyState
            title="You haven't joined a placement drive yet"
            sub="Browse Company Opportunities and express interest — the TPO nominates students for drives."
          />
        </Card>
      ) : (
        <>
          {current && (
            <Card title="Current stage" subtitle={`${current.company} · ${current.role}`}>
              <div className="flex flex-wrap items-center gap-1.5">
                {JOURNEY_STEPS.map((step, i) => {
                  const reached = STAGE_META[current.status]?.step >= STAGE_META[step].step
                    && STAGE_META[current.status]?.step > 0;
                  const isCurrent = current.status === step;
                  return (
                    <div key={step} className="flex items-center gap-1.5">
                      <div className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-medium ${
                        isCurrent
                          ? "border-navy-300 bg-navy-800 text-white"
                          : reached
                            ? "border-teal-200 bg-teal-50 text-teal-700"
                            : "border-slate-200 bg-white text-slate-400"
                      }`}>
                        {reached ? <BadgeCheck className="h-3.5 w-3.5" /> : <CircleDashed className="h-3.5 w-3.5" />}
                        {STAGE_META[step].label}
                      </div>
                      {i < JOURNEY_STEPS.length - 1 && (
                        <div className={`h-px w-3 ${reached ? "bg-teal-400" : "bg-slate-200"}`} />
                      )}
                    </div>
                  );
                })}
              </div>
              {STAGE_META[current.status]?.step === 0 && (
                <div className="mt-3">
                  <Badge cls={STAGE_META[current.status]?.cls || ""}>
                    {STAGE_META[current.status]?.label || current.status}
                  </Badge>
                </div>
              )}
            </Card>
          )}

          <Card title="All drives">
            <div className="space-y-3">
              {data.journey.map((j) => {
                const m = STAGE_META[j.status];
                return (
                  <div key={j.candidate_id} className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-100 px-4 py-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-navy-50 text-navy-700">
                      <Building2 className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-[13.5px] font-semibold text-slate-800">
                        {j.company} <span className="font-normal text-slate-500">· {j.role}</span>
                      </div>
                      <div className="text-[12px] text-slate-400">
                        {j.match_score != null && <>Company match {j.match_score} · </>}
                        updated {timeAgo(j.updated_at)}
                        {j.confirmed_at && <> · confirmed {timeAgo(j.confirmed_at)}</>}
                      </div>
                    </div>
                    <Badge cls={m?.cls || ""}>{m?.label || j.status}</Badge>
                  </div>
                );
              })}
            </div>
          </Card>
        </>
      )}

      <Disclaimer>
        A company's "Selected" status is a recruiter decision. Your placement is officially
        recorded only after the TPO confirms it (Placement Confirmed).
      </Disclaimer>
    </div>
  );
}

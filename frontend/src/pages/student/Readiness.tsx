import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  ArrowDownRight, ArrowUpRight, BadgeCheck, Briefcase, Dna, RefreshCw,
} from "lucide-react";
import { api } from "../../api/client";
import { useAuth } from "../../lib/auth";
import { fmt1 } from "../../lib/format";
import { Card, CategoryBadge, Disclaimer, ErrorBox, Spinner, Stat } from "../../components/ui";
import { ScoreRing } from "../../components/ScoreRing";

interface MiniOpp {
  drive_id: number;
  company: { name: string };
  role: string;
  eligible: boolean;
  almost_eligible: boolean;
  match_score: number;
}

interface XaiItem { feature: string; label: string; value: number | null; contribution: number; direction: string; impact?: string }
interface Prediction {
  score: number; category: string; category_label: string; model_version: string;
  profile_trust: number; data_completeness: number; created_at: string;
  feature_snapshot: Record<string, number | null>;
}
interface ReadinessResp {
  status: string;
  prediction?: Prediction;
  xai?: { positive: XaiItem[]; limiting: XaiItem[]; baseline?: number; model_output?: number };
  career?: {
    target_code: string | null;
    target_match?: { career_code: string; name: string; match_score: number; alignment: string } | null;
  };
  trust?: { score: number; band: string };
  completeness?: { score: number; categories: { category: string; done: boolean; note?: string }[] };
  eligibility?: { eligible: boolean; missing: string[]; missing_recommended?: string[] };
  summary_sentence?: string;
}

export default function Readiness() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["readiness"],
    queryFn: () => api<ReadinessResp>("/student/readiness"),
  });
  const opps = useQuery({
    queryKey: ["student-companies"],
    queryFn: () => api<{ opportunities: MiniOpp[] }>("/student/companies"),
    staleTime: 5 * 60_000,
  });

  if (isLoading) return <Spinner label="Computing your placement readiness…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  const s = user?.student;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Placement Readiness</h1>
          <p className="mt-0.5 text-[13px] text-slate-500">
            {s?.name} · {s?.usn} · {s?.branch} · Semester {s?.semester}
          </p>
        </div>
        <button className="btn-outline" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </header>

      {data.status !== "ok" ? (
        <Card title="Insufficient verified data">
          <p className="text-sm text-slate-600">
            We need a little more verified information before we can give you a reliable readiness
            signal. This is expected early in the semester.
          </p>
          {data.eligibility && data.eligibility.missing.length > 0 && (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-[13px] text-slate-600">
              {data.eligibility.missing.map((m) => <li key={m}>{m}</li>)}
            </ul>
          )}
        </Card>
      ) : data.prediction ? (
        <>
          {data.eligibility && (data.eligibility.missing_recommended || []).length > 0 && (
            <Card>
              <p className="text-[13px] leading-relaxed text-slate-600">
                This score is a <span className="font-medium text-slate-800">model-estimate</span> from
                the data on file. It becomes more reliable once these are added:
              </p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px] text-slate-600">
                {data.eligibility.missing_recommended!.map((m) => <li key={m}>{m}</li>)}
              </ul>
            </Card>
          )}
          <div className="grid gap-4 md:grid-cols-3">
            <Card className="flex items-center justify-center py-6">
              <ScoreRing score={data.prediction.score} label="Placement Readiness" />
            </Card>

            <div className="flex flex-col gap-4">
              <Card>
                <div className="flex items-center justify-between">
                  <CategoryBadge category={data.prediction.category} />
                  <span className="text-[11px] text-slate-400">model {data.prediction.model_version}</span>
                </div>
                {data.summary_sentence && (
                  <p className="mt-3 text-[13.5px] leading-relaxed text-slate-600">
                    {data.summary_sentence}
                  </p>
                )}
              </Card>
              <div className="grid grid-cols-2 gap-4">
                <Stat label="Profile Trust" value={fmt(data.prediction.profile_trust)}
                  sub={data.trust ? data.trust.band : ""}
                  tone={data.prediction.profile_trust >= 75 ? "good" : "neutral"} />
                <Stat label="Data Completeness" value={fmt(data.prediction.data_completeness)}
                  sub="of required signals present" />
              </div>
            </div>

            <Card title="What's driving your score"
              subtitle="Contributions from your verified profile (model-estimated)">
              <XaiList title="Strengthening your score" items={data.xai?.positive || []} up />
              <div className="my-3 border-t border-slate-100" />
              <XaiList title="Your highest-impact opportunities" items={data.xai?.limiting || []} />
              <p className="mt-3 text-[11.5px] leading-relaxed text-slate-400">
                Contributions are relative model effects, not causal guarantees. Focus on the
                opportunities with the largest impact first.
              </p>
            </Card>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {data.career?.target_match && (
              <Card title="Your target career">
                <div className="text-[15px] font-semibold text-slate-900">
                  {data.career.target_match.name}
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-semibold tabular-nums text-navy-800">
                    {fmt(data.career.target_match.match_score)}
                  </span>
                  <span className="text-[12px] text-slate-400">match score</span>
                </div>
                <div className="mt-1 text-[12.5px] text-slate-500">{data.career.target_match.alignment} alignment</div>
              </Card>
            )}
            <Card title="Profile quality" className={data.career?.target_match ? "" : "md:col-span-2"}>
              <div className="space-y-2.5">
                {(data.completeness?.categories || []).map((c) => (
                  <div key={c.category} className="flex items-center justify-between gap-3 text-[13px]">
                    <span className="text-slate-600">{c.category}</span>
                    {c.done
                      ? <BadgeCheck className="h-4 w-4 text-teal-600" />
                      : <span className="text-[12px] font-medium text-amber-600">missing</span>}
                  </div>
                ))}
                {data.completeness?.categories.length === 0 && (
                  <p className="text-[13px] text-slate-500">Completeness details unavailable.</p>
                )}
              </div>
            </Card>
          </div>

          <Card title="Best company opportunities"
            subtitle="Eligible open drives with the highest company match for your verified profile"
            actions={
              <button className="flex items-center gap-1 text-[12.5px] font-medium text-navy-700 hover:underline"
                onClick={() => navigate("/student/companies")}>
                All opportunities <ArrowUpRight className="h-3.5 w-3.5" />
              </button>
            }>
            {(opps.data?.opportunities || []).filter((o) => o.eligible).length === 0 ? (
              <p className="text-[13px] text-slate-500">
                {opps.isLoading
                  ? "Checking open drives…"
                  : "No eligible open drives right now. You can still browse all opportunities and see how close you are."}
              </p>
            ) : (
              <div className="grid gap-3 md:grid-cols-3">
                {(opps.data?.opportunities || [])
                  .filter((o) => o.eligible)
                  .slice(0, 3)
                  .map((o) => (
                    <button
                      key={o.drive_id}
                      onClick={() => navigate("/student/companies")}
                      className="rounded-lg border border-slate-200 p-3.5 text-left transition hover:border-navy-300 hover:bg-navy-50/40"
                    >
                      <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                        <Briefcase className="h-3.5 w-3.5" /> Company match
                      </div>
                      <div className="mt-1 text-[15px] font-semibold text-slate-900">{fmt1(o.match_score)}</div>
                      <div className="mt-1 truncate text-[13px] font-medium text-navy-700">{o.company.name}</div>
                      <div className="truncate text-[12px] text-slate-500">{o.role}</div>
                    </button>
                  ))}
              </div>
            )}
          </Card>

          <Disclaimer>
            <Dna className="mr-1 inline h-3.5 w-3.5" />
            Your score is a <span className="font-medium">model-estimated readiness signal</span> based
            on your verified profile ({fmt(data.prediction.profile_trust)} trust, computed{" "}
            {new Date(data.prediction.created_at).toLocaleDateString("en-IN")}). It is not a placement
            guarantee, and it updates as your evidence is verified and your profile improves.
          </Disclaimer>
        </>
      ) : null}
    </div>
  );
}

function XaiList({ title, items, up = false }: { title: string; items: XaiItem[]; up?: boolean }) {
  if (!items.length) {
    return <p className="text-[12.5px] text-slate-400">No dominant factors in this direction right now.</p>;
  }
  return (
    <div>
      <div className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wide text-slate-500">
        {up ? <ArrowUpRight className="h-3.5 w-3.5 text-teal-600" /> : <ArrowDownRight className="h-3.5 w-3.5 text-amber-600" />}
        {title}
      </div>
      <ul className="space-y-2">
        {items.map((c) => (
          <li key={c.feature} className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate text-[13px] font-medium text-slate-700">{c.label}</div>
              {c.value !== null && (
                <div className="text-[11.5px] text-slate-400">current {fmt1(c.value)}</div>
              )}
            </div>
            <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11.5px] font-semibold tabular-nums ${
              up ? "bg-teal-50 text-teal-700" : "bg-amber-50 text-amber-700"
            }`}>
              {up ? "+" : ""}{c.contribution.toFixed(2)}
              {c.impact && <span className="ml-1 font-normal opacity-70">{c.impact}</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function fmt(n: number | null | undefined) {
  return n === null || n === undefined ? "—" : Math.round(n).toString();
}

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight, Beaker, CheckCircle2, Clock, Flag, ListChecks, Route,
} from "lucide-react";
import { api, ApiError } from "../../api/client";
import { fmt, fmt1 } from "../../lib/format";
import { Bar, Card, CategoryBadge, Disclaimer, ErrorBox, Spinner } from "../../components/ui";

interface OptAction {
  code: string; feature: string; label: string;
  current_value: number | null; target_value: number;
  estimated_weeks: number; difficulty: string;
  projected_readiness_after: number; marginal_impact_points: number;
  career_delta: number | null; priority: string; reason: string;
}
interface OptimizerResp {
  status: string;
  target_type: string; career_code: string | null;
  baseline_readiness: number; baseline_category: string;
  baseline_career_match: number | null; target: number;
  target_reached: boolean; actions: OptAction[];
  projected_readiness: number; projected_category?: string;
  projected_career_match?: number | null;
  estimated_duration: string; total_weeks: number; message?: string;
  disclaimer?: string;
}
interface RoadmapItem {
  id: number; seq: number; phase: string; title: string; description: string | null;
  starting_value: string | null; target_value: string | null; estimated_weeks: number | null;
  priority: string; status: string; tasks: string[]; milestone: string | null;
}
interface RoadmapResp {
  status: string; roadmap: {
    id: number; target_type: string; current_readiness: number; target_readiness: number;
    estimated_duration: string | null; items: RoadmapItem[];
  } | null;
}

type Mode = "GENERAL_READINESS" | "CAREER_TRACK";

export default function PathToReady() {
  const qc = useQueryClient();
  const [mode, setMode] = useState<Mode>("GENERAL_READINESS");
  const { data: career } = useQuery({ queryKey: ["career"], queryFn: () => api<{ target_code: string | null; matches: { career_code: string; name: string }[] }>("/student/career") });
  const targetCareer = career?.target_code || career?.matches?.[0]?.career_code || null;

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["optimizer", mode, targetCareer],
    queryFn: () => api<OptimizerResp>(`/student/optimizer?target_type=${mode}${mode === "CAREER_TRACK" && targetCareer ? `&career_code=${targetCareer}` : ""}`),
  });

  const { data: rmData, isLoading: rmLoading } = useQuery({
    queryKey: ["roadmap", mode, targetCareer],
    queryFn: () => api<RoadmapResp>("/student/roadmap"),
  });

  const genRoadmap = useMutation({
    mutationFn: () => api<RoadmapResp>("/student/roadmap/generate", {
      body: { target_type: mode, career_code: mode === "CAREER_TRACK" ? targetCareer : null },
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["roadmap"] }),
  });

  const careerName = career?.matches?.find((m) => m.career_code === targetCareer)?.name;

  if (isLoading) return <Spinner label="Searching your minimum-change path…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data || data.status !== "ok") return <ErrorBox message="Optimizer unavailable. The model may not be deployed." />;

  const isCareer = mode === "CAREER_TRACK";
  const targetLabel = isCareer
    ? `${fmt(data.target)} match for ${careerName || "your target career"}`
    : `${fmt(data.target)}+ Placement Readiness (Ready)`;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Path to Ready</h1>
          <p className="mt-0.5 text-[13px] text-slate-500">
            The smallest set of high-impact actions the model projects will get you there.
          </p>
        </div>
        <div className="flex rounded-lg border border-slate-200 bg-white p-0.5 text-[12.5px] font-medium">
          <button
            className={`rounded-md px-3 py-1.5 ${mode === "GENERAL_READINESS" ? "bg-navy-800 text-white" : "text-slate-500"}`}
            onClick={() => setMode("GENERAL_READINESS")}
          >
            Placement Readiness
          </button>
          <button
            className={`rounded-md px-3 py-1.5 ${mode === "CAREER_TRACK" ? "bg-navy-800 text-white" : "text-slate-500"}`}
            onClick={() => setMode("CAREER_TRACK")}
          >
            Career Track{careerName ? ` · ${careerName}` : ""}
          </button>
        </div>
      </header>

      <Card>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <div>
            <div className="label">Today</div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-3xl font-semibold tabular-nums text-slate-900">{fmt1(data.baseline_readiness)}</span>
              {!isCareer && <CategoryBadge category={data.baseline_category} />}
              {isCareer && data.baseline_career_match !== null && (
                <span className="text-[13px] text-slate-500">career match {fmt(data.baseline_career_match)}</span>
              )}
            </div>
          </div>
          <ArrowRight className="h-5 w-5 text-slate-300" />
          <div>
            <div className="label">Projected after actions</div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-3xl font-semibold tabular-nums text-teal-700">{fmt1(data.projected_readiness)}</span>
              {isCareer && data.projected_career_match !== undefined && data.projected_career_match !== null && (
                <span className="text-[13px] text-slate-500">career match {fmt(data.projected_career_match)}</span>
              )}
              {!isCareer && data.projected_category && <CategoryBadge category={data.projected_category} />}
            </div>
          </div>
          <div className="ml-auto text-right">
            <div className="label">Target</div>
            <div className="mt-1 text-[13.5px] font-medium text-slate-700">{targetLabel}</div>
            <div className="mt-0.5 flex items-center justify-end gap-1 text-[12px] text-slate-400">
              <Clock className="h-3.5 w-3.5" /> ~{data.estimated_duration}
            </div>
          </div>
        </div>
        {data.target_reached ? (
          <div className="mt-4 flex items-center gap-2 rounded-lg bg-teal-50 px-3.5 py-2.5 text-[13px] font-medium text-teal-800">
            <CheckCircle2 className="h-4 w-4" /> The projected path reaches your target.
          </div>
        ) : (
          <div className="mt-4 rounded-lg bg-amber-50 px-3.5 py-2.5 text-[13px] text-amber-800">
            {data.message || "The target may not be reachable through short-term skill changes alone."}
          </div>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card title="Recommended actions" subtitle={`${data.actions.length} action${data.actions.length === 1 ? "" : "s"} · minimum-change selection`}
          className="lg:col-span-3">
          {data.actions.length === 0 ? (
            <p className="text-[13.5px] text-slate-500">{data.message || "No actions required right now."}</p>
          ) : (
            <ol className="space-y-3">
              {data.actions.map((a, i) => (
                <li key={a.code} className="rounded-lg border border-slate-200 p-4">
                  <div className="flex items-start gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-navy-800 text-[12px] font-semibold text-white">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[14px] font-semibold text-slate-900">{a.label}</span>
                        <span className={`rounded-full px-2 py-0.5 text-[10.5px] font-semibold uppercase ${
                          a.priority === "High" ? "bg-rose-50 text-rose-600" : "bg-slate-100 text-slate-500"
                        }`}>{a.priority}</span>
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10.5px] font-medium text-slate-500">
                          {a.difficulty} · {a.estimated_weeks} wk
                        </span>
                      </div>
                      <div className="mt-2 flex items-center gap-2 text-[12.5px] text-slate-500">
                        <span className="tabular-nums">{a.current_value !== null ? fmt(a.current_value) : "0"}</span>
                        <ArrowRight className="h-3.5 w-3.5" />
                        <span className="font-semibold tabular-nums text-navy-800">{fmt(a.target_value)}</span>
                        <span className="ml-1 rounded bg-teal-50 px-1.5 py-0.5 text-[11px] font-semibold text-teal-700">
                          +{fmt1(a.marginal_impact_points)} pts projected
                        </span>
                        {a.career_delta !== null && a.career_delta !== 0 && (
                          <span className="rounded bg-navy-50 px-1.5 py-0.5 text-[11px] font-semibold text-navy-700">
                            {a.career_delta > 0 ? "+" : ""}{fmt(a.career_delta)} career match
                          </span>
                        )}
                      </div>
                      <p className="mt-2 text-[12.5px] leading-relaxed text-slate-500">{a.reason}</p>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
          <div className="mt-4">
            <Disclaimer>
              Projected outcomes are model-estimated from your verified profile and assumed skill
              improvement — they are not guaranteed results.
            </Disclaimer>
          </div>
        </Card>

        <div className="space-y-4 lg:col-span-2">
          <Card title="What-if simulation" subtitle="Hypothetical — never changes your profile">
            <WhatIf />
          </Card>
        </div>
      </div>

      <Card
        title="Your roadmap"
        subtitle="Structured phases generated from the recommended actions"
        actions={
          <button className="btn-outline" onClick={() => genRoadmap.mutate()} disabled={genRoadmap.isPending}>
            <Route className="h-4 w-4" /> {rmData?.roadmap ? "Regenerate" : "Generate roadmap"}
          </button>
        }
      >
        {rmLoading ? (
          <Spinner />
        ) : rmData?.roadmap ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[12.5px] text-slate-500">
              <span>Starts at <b className="tabular-nums text-slate-700">{fmt1(rmData.roadmap.current_readiness)}</b></span>
              <ArrowRight className="h-3.5 w-3.5" />
              <span>Target <b className="tabular-nums text-teal-700">{fmt(rmData.roadmap.target_readiness)}</b></span>
              {rmData.roadmap.estimated_duration && (
                <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> ~{rmData.roadmap.estimated_duration}</span>
              )}
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {rmData.roadmap.items.map((it) => (
                <RoadmapCard key={it.id} item={it} />
              ))}
            </div>
          </div>
        ) : (
          <p className="text-[13.5px] text-slate-500">
            No roadmap yet. Click “Generate roadmap” to build structured phases from your recommended actions.
          </p>
        )}
      </Card>
    </div>
  );
}

function RoadmapCard({ item }: { item: RoadmapItem }) {
  const [status, setStatus] = useState(item.status);
  const mut = useMutation({
    mutationFn: (s: string) => api(`/student/roadmap/items/${item.id}`, { method: "PATCH", body: { status: s } }),
    onSuccess: (d, s) => setStatus(s),
  });
  const done = status === "COMPLETED";
  return (
    <div className={`rounded-lg border p-4 ${done ? "border-teal-200 bg-teal-50/40" : "border-slate-200"}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Phase {item.seq}</div>
          <div className="mt-0.5 text-[14px] font-semibold text-slate-900">{item.phase}</div>
          <div className="text-[12.5px] text-slate-500">{item.title}</div>
        </div>
        <button
          className={`btn ${done ? "btn-outline" : "btn-teal"} !px-2.5 !py-1.5 !text-[12px]`}
          onClick={() => {
            const next = status === "NOT_STARTED" ? "IN_PROGRESS" : status === "IN_PROGRESS" ? "COMPLETED" : "NOT_STARTED";
            setStatus(next);
            mut.mutate(next);
          }}
        >
          {status === "NOT_STARTED" ? "Start" : status === "IN_PROGRESS" ? "Mark done" : "Reopen"}
        </button>
      </div>
      {item.description && <p className="mt-2 text-[12.5px] text-slate-500">{item.description}</p>}
      <ul className="mt-3 space-y-1.5">
        {item.tasks.map((t, i) => (
          <li key={i} className="flex items-start gap-2 text-[12.5px] text-slate-600">
            <ListChecks className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-300" /> {t}
          </li>
        ))}
      </ul>
      {item.milestone && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-navy-50 px-3 py-2 text-[12px] text-navy-800">
          <Flag className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span><b>Milestone:</b> {item.milestone}</span>
        </div>
      )}
      <div className="mt-2 text-[11.5px] text-slate-400">
        {item.estimated_weeks ? `~${item.estimated_weeks} week${item.estimated_weeks > 1 ? "s" : ""}` : ""}
        {item.priority ? ` · ${item.priority} priority` : ""}
      </div>
    </div>
  );
}

function WhatIf() {
  const [feature, setFeature] = useState("sql_score");
  const [value, setValue] = useState(70);
  const { data, isFetching, error } = useQuery({
    queryKey: ["whatif", feature, value],
    queryFn: () => api<{ baseline_readiness: number; projected_readiness: number; delta_points: number; career?: any }>(
      "/student/what-if/simulate", { body: { changes: [{ feature, value }] } }),
  });
  const options = useMemo(() => [
    { v: "sql_score", l: "SQL Proficiency" },
    { v: "dsa_score", l: "DSA & Problem Solving" },
    { v: "coding_score", l: "Coding Assessment" },
    { v: "communication_score", l: "Communication" },
    { v: "web_dev_score", l: "Web Development" },
    { v: "aptitude_score", l: "Aptitude" },
  ], []);

  return (
    <div className="space-y-3">
      <div>
        <label className="label" htmlFor="wf-feature">If I improved…</label>
        <select id="wf-feature" className="input mt-1.5" value={feature} onChange={(e) => setFeature(e.target.value)}>
          {options.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
        </select>
      </div>
      <div>
        <label className="label" htmlFor="wf-value">…to a score of {value}</label>
        <input id="wf-value" type="range" min={0} max={100} value={value}
          className="mt-2 w-full accent-teal-600" onChange={(e) => setValue(Number(e.target.value))} />
      </div>
      {error ? (
        <p className="text-[12.5px] text-rose-600">{error instanceof ApiError ? error.message : "Simulation failed"}</p>
      ) : data ? (
        <div className="rounded-lg bg-slate-50 px-3.5 py-3">
          <div className="flex items-center gap-2 text-[13px] text-slate-600">
            <Beaker className="h-4 w-4 text-navy-600" />
            Projected readiness:
            <span className="font-semibold tabular-nums text-slate-900">{fmt1(data.baseline_readiness)}</span>
            <ArrowRight className="h-3.5 w-3.5 text-slate-400" />
            <span className={`font-semibold tabular-nums ${data.delta_points >= 0 ? "text-teal-700" : "text-rose-600"}`}>
              {fmt1(data.projected_readiness)}
            </span>
            <span className={`text-[12px] font-medium ${data.delta_points >= 0 ? "text-teal-600" : "text-rose-500"}`}>
              ({data.delta_points >= 0 ? "+" : ""}{fmt1(data.delta_points)} pts)
            </span>
          </div>
          {data.career && (
            <div className="mt-1.5 text-[12px] text-slate-500">
              Career match {fmt(data.career.baseline)} → {fmt(data.career.projected)}
            </div>
          )}
        </div>
      ) : (
        <p className="text-[12.5px] text-slate-400">{isFetching ? "Simulating…" : ""}</p>
      )}
      <p className="text-[11.5px] leading-relaxed text-slate-400">
        Hypothetical only. This simulation never changes your profile or stored prediction.
      </p>
    </div>
  );
}

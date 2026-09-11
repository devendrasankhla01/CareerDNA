import { useQuery } from "@tanstack/react-query";
import {
  Award, BookOpenCheck, Briefcase, FileText, FlaskConical, GitBranch,
  GraduationCap, Hammer, ShieldCheck,
} from "lucide-react";
import { api } from "../../api/client";
import { STATUS_META } from "../../lib/format";
import { Bar, Card, EmptyState, ErrorBox, Spinner, StatusBadge } from "../../components/ui";

interface SkillRow {
  skill_code: string; skill_name: string; score: number | null; claimed_level: string | null;
  source: string; source_label: string; status: string; review_note: string | null; trust: string;
}
interface ProjectRow {
  id: number; title: string; description: string | null; tech_stack: string[] | null;
  team_type: string | null; student_role: string | null; claimed_complexity: string | null;
  verified_complexity: string | null; github_url: string | null; demo_url: string | null;
  status: string; review_note: string | null;
}
interface Passport {
  skills: SkillRow[]; projects: ProjectRow[]; internships: any[]; certifications: any[];
  activities: any[]; open_source: any[];
  passport: { state: string; counts: Record<string, number>; note: string };
  trust: { score: number; band: string; categories: Record<string, { weight: number; value: number }> };
  completeness: { score: number; categories: { category: string; done: boolean }[] };
}

const STATE_META: Record<string, { label: string; cls: string; icon: any }> = {
  PENDING: { label: "Awaiting Verification", cls: "bg-amber-50 text-amber-800 border-amber-200", icon: ShieldCheck },
  VERIFIED: { label: "Verified", cls: "bg-teal-50 text-teal-800 border-teal-200", icon: BadgeOk },
  CORRECTION_REQUIRED: { label: "Correction Required", cls: "bg-orange-50 text-orange-800 border-orange-200", icon: FileText },
  REJECTED: { label: "Needs Re-work", cls: "bg-rose-50 text-rose-800 border-rose-200", icon: FileText },
  NONE: { label: "No Submissions Yet", cls: "bg-slate-50 text-slate-600 border-slate-200", icon: BookOpenCheck },
};

function BadgeOk() { return <Award className="h-4 w-4" />; }

export default function Passport() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["passport"],
    queryFn: () => api<Passport>("/student/passport"),
  });

  if (isLoading) return <Spinner label="Loading your verified passport…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  const state = STATE_META[data.passport.state] || STATE_META.NONE;
  const trust = data.trust;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Verified Employability Passport</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">
          Your evidence, with provenance. Only verified items count toward your readiness signal.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <div className="flex items-center gap-3">
            <span className={`flex h-10 w-10 items-center justify-center rounded-lg border ${state.cls}`}>
              <state.icon className="h-5 w-5" />
            </span>
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Passport state</div>
              <div className="text-[15px] font-semibold text-slate-900">{state.label}</div>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-4 gap-2 text-center">
            {(["PENDING", "VERIFIED", "CORRECTION_REQUIRED", "REJECTED"] as const).map((k) => (
              <div key={k} className="rounded-lg bg-slate-50 py-2">
                <div className="text-[15px] font-semibold tabular-nums text-slate-800">
                  {data.passport.counts[k] || 0}
                </div>
                <div className="text-[10px] font-medium uppercase text-slate-400">
                  {STATUS_META[k]?.label || k}
                </div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-[12px] text-slate-500">{data.passport.note}</p>
        </Card>

        <Card title="Profile Trust" subtitle="How much of your profile is institution-verified">
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-semibold tabular-nums text-navy-800">{trust.score}</span>
            <span className="text-[12.5px] text-slate-400">/ 100 · {trust.band}</span>
          </div>
          <div className="mt-3 space-y-2">
            {Object.entries(trust.categories).map(([k, v]) => (
              <div key={k}>
                <div className="mb-1 flex justify-between text-[11.5px] text-slate-500">
                  <span>{k.replace("_", " ")}</span>
                  <span className="tabular-nums">{Math.round(v.value)}% · weight {v.weight}</span>
                </div>
                <Bar value={v.value} tone={v.value >= 75 ? "teal" : v.value >= 40 ? "amber" : "rose"} />
              </div>
            ))}
          </div>
        </Card>

        <Card title="Data Completeness" subtitle="Required signals present in your profile">
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-semibold tabular-nums text-navy-800">{data.completeness.score}</span>
            <span className="text-[12.5px] text-slate-400">/ 100</span>
          </div>
          <ul className="mt-4 space-y-2">
            {data.completeness.categories.map((c) => (
              <li key={c.category} className="flex items-center justify-between text-[13px]">
                <span className="text-slate-600">{c.category}</span>
                <span className={c.done ? "text-teal-600" : "text-amber-600"}>
                  {c.done ? "complete" : "missing"}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <PassportSection icon={GraduationCap} title="Skills & Assessments" empty="No skill signals yet." count={data.skills.length}>
        <div className="grid gap-2 md:grid-cols-2">
          {data.skills.map((s) => (
            <div key={s.skill_code} className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 bg-slate-50/60 px-3.5 py-2.5">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate text-[13.5px] font-medium text-slate-800">{s.skill_name}</span>
                  <Provenance source={s.source_label} />
                </div>
                <div className="mt-0.5 text-[11.5px] text-slate-400">
                  {s.score !== null ? `score ${s.score}` : s.claimed_level ? `claimed ${s.claimed_level}` : "no score"}
                  {s.claimed_level && s.score !== null && ` · claimed ${s.claimed_level}`}
                </div>
              </div>
              <StatusBadge status={s.status} />
            </div>
          ))}
        </div>
      </PassportSection>

      <PassportSection icon={Hammer} title="Projects" empty="No projects listed." count={data.projects.length}>
        <div className="grid gap-3 md:grid-cols-2">
          {data.projects.map((p) => (
            <div key={p.id} className="rounded-lg border border-slate-100 px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-[14px] font-medium text-slate-800">{p.title}</div>
                  <div className="mt-0.5 text-[12px] text-slate-400">
                    {p.student_role}{p.team_type ? ` · ${p.team_type}` : ""} · {p.claimed_complexity || "complexity n/a"}
                  </div>
                </div>
                <StatusBadge status={p.status} />
              </div>
              {p.tech_stack?.length ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {p.tech_stack.map((t) => (
                    <span key={t} className="rounded bg-navy-50 px-1.5 py-0.5 text-[11px] font-medium text-navy-700">{t}</span>
                  ))}
                </div>
              ) : null}
              {p.verified_complexity && (
                <div className="mt-2 text-[11.5px] text-teal-700">Faculty-verified complexity: {p.verified_complexity}</div>
              )}
              {p.review_note && <div className="mt-2 text-[12px] italic text-slate-500">“{p.review_note}”</div>}
            </div>
          ))}
        </div>
      </PassportSection>

      <div className="grid gap-5 lg:grid-cols-2">
        <PassportSection icon={Briefcase} title="Internships" empty="No internships listed." count={data.internships.length}>
          {data.internships.map((i: any) => (
            <ItemRow key={i.id} title={i.organization} sub={`${i.role || ""}${i.domain ? ` · ${i.domain}` : ""} · ${i.start_date || ""} → ${i.end_date || ""}`}
              status={i.status} note={i.review_note} />
          ))}
        </PassportSection>

        <PassportSection icon={Award} title="Certifications" empty="No certifications listed." count={data.certifications.length}>
          {data.certifications.map((c: any) => (
            <ItemRow key={c.id} title={c.name} sub={`${c.issuer || ""}${c.issue_date ? ` · issued ${c.issue_date}` : ""}`}
              status={c.status} note={c.review_note} />
          ))}
        </PassportSection>

        <PassportSection icon={FlaskConical} title="Activities & Competitions" empty="No activities listed." count={data.activities.length}>
          {data.activities.map((a: any) => (
            <ItemRow key={a.id} title={a.event_name} sub={`${a.event_type}${a.achievement ? ` · ${a.achievement}` : ""} · ${a.event_date || ""}`}
              status={a.status} note={a.review_note} />
          ))}
        </PassportSection>

        <PassportSection icon={GitBranch} title="Open Source" empty="No open-source contributions listed." count={data.open_source.length}>
          {data.open_source.map((o: any) => (
            <ItemRow key={o.id} title={o.repository_url.replace("https://github.com/", "")}
              sub={o.contribution_type || ""} status={o.status} note={o.review_note} />
          ))}
        </PassportSection>
      </div>
    </div>
  );
}

function Provenance({ source }: { source: string }) {
  const cls =
    source === "Institution" ? "bg-navy-50 text-navy-700"
    : source === "Assessment" ? "bg-blue-50 text-blue-700"
    : source === "Faculty Verified" ? "bg-teal-50 text-teal-700"
    : "bg-slate-100 text-slate-500";
  return <span className={`rounded px-1.5 py-0.5 text-[10.5px] font-medium ${cls}`}>{source}</span>;
}

function ItemRow({ title, sub, status, note }: { title: string; sub: string; status: string; note: string | null }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 px-3.5 py-2.5">
      <div className="min-w-0">
        <div className="truncate text-[13.5px] font-medium text-slate-800">{title}</div>
        <div className="mt-0.5 truncate text-[11.5px] text-slate-400">{sub}</div>
        {note && <div className="mt-1 truncate text-[12px] italic text-slate-500">“{note}”</div>}
      </div>
      <StatusBadge status={status} />
    </div>
  );
}

function PassportSection({ icon: Icon, title, empty, count, children }: {
  icon: any; title: string; empty: string; count: number; children: React.ReactNode;
}) {
  return (
    <Card title={title} actions={<Icon className="h-4 w-4 text-slate-300" />}>
      {count === 0 ? <EmptyState title={empty} /> : children}
    </Card>
  );
}

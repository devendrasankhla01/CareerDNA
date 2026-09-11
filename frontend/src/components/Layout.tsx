import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  BarChart3, BookOpenCheck, Briefcase, Building2, CheckSquare, ClipboardCheck,
  FlaskConical, Gauge, GraduationCap, Handshake, LayoutDashboard, LineChart,
  LogOut, SearchCheck, SlidersHorizontal, Target, Upload, Users,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { homeFor } from "../App";

const NAV: Record<string, { to: string; label: string; icon: any; end?: boolean }[]> = {
  STUDENT: [
    { to: "/student", label: "Placement Readiness", icon: Gauge, end: true },
    { to: "/student/companies", label: "Company Opportunities", icon: Briefcase },
    { to: "/student/placement", label: "Placement Journey", icon: LineChart },
    { to: "/student/passport", label: "Verified Passport", icon: BookOpenCheck },
    { to: "/student/career", label: "Career Match", icon: LineChart },
    { to: "/student/path", label: "Path to Ready", icon: SlidersHorizontal },
    { to: "/model", label: "About the Model", icon: FlaskConical },
  ],
  FACULTY: [
    { to: "/verifier/queue", label: "My Verification Queue", icon: ClipboardCheck, end: true },
    { to: "/model", label: "About the Model", icon: FlaskConical },
  ],
  VERIFIER: [
    { to: "/verifier/queue", label: "My Verification Queue", icon: ClipboardCheck, end: true },
    { to: "/model", label: "About the Model", icon: FlaskConical },
  ],
  TPO_ADMIN: [
    { to: "/tpo", label: "Institution Overview", icon: LayoutDashboard, end: true },
    { to: "/tpo/matching", label: "Candidate Matching", icon: SearchCheck },
    { to: "/tpo/placements", label: "Placements", icon: CheckSquare },
    { to: "/tpo/verification", label: "Verification Center", icon: ClipboardCheck },
    { to: "/tpo/departments", label: "Departments", icon: Users },
    { to: "/tpo/companies", label: "Companies", icon: Building2 },
    { to: "/tpo/drives", label: "Placement Drives", icon: Target },
    { to: "/tpo/skills", label: "Skill Deficits", icon: Users },
    { to: "/tpo/interventions", label: "Interventions", icon: FlaskConical },
    { to: "/tpo/import", label: "Data Import", icon: Upload },
    { to: "/model", label: "Model Information", icon: GraduationCap },
  ],
  DEPARTMENT: [
    { to: "/department", label: "Department Overview", icon: LayoutDashboard, end: true },
    { to: "/department/skills", label: "Skill Gaps", icon: Users },
    { to: "/department/performance", label: "Performance", icon: BarChart3 },
    { to: "/department/companies", label: "Company Eligibility", icon: Building2 },
    { to: "/department/placements", label: "Placement Status", icon: CheckSquare },
    { to: "/department/data", label: "Data Updates", icon: Upload },
    { to: "/model", label: "About the Model", icon: FlaskConical },
  ],
  COMPANY: [
    { to: "/company", label: "Overview", icon: LayoutDashboard, end: true },
    { to: "/company/drives", label: "Drives & Candidates", icon: Briefcase },
    { to: "/company/selections", label: "Selections", icon: Handshake },
  ],
};

const ROLE_LABEL: Record<string, string> = {
  STUDENT: "Student Portal",
  FACULTY: "Verifier",
  VERIFIER: "Verifier",
  TPO_ADMIN: "TPO Placement Intelligence",
  DEPARTMENT: "Department Analytics",
  COMPANY: "Company Recruitment Portal",
};

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;
  const nav = NAV[user.role] || [];

  return (
    <div className="min-h-screen lg:flex">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="flex items-center gap-2.5 border-b border-slate-100 px-5 py-4">
          <Logo />
          <div>
            <div className="text-[15px] font-semibold leading-tight text-navy-900">CareerDNA</div>
            <div className="text-[11px] text-slate-400">AI Placement Predictor</div>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto p-3">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13.5px] font-medium transition-colors ${
                  isActive
                    ? "bg-navy-50 text-navy-800"
                    : "text-slate-500 hover:bg-slate-50 hover:text-slate-800"
                }`
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-100 p-3">
          <div className="mb-2 flex items-center gap-2.5 rounded-lg bg-slate-50 px-3 py-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-navy-800 text-[12px] font-semibold text-white">
              {(user.display_name || "?").split(" ").map((w) => w[0]).slice(0, 2).join("")}
            </div>
            <div className="min-w-0">
              <div className="truncate text-[13px] font-medium text-slate-800">{user.display_name}</div>
              <div className="truncate text-[11px] text-slate-400">{ROLE_LABEL[user.role]}</div>
            </div>
          </div>
          <button
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium text-slate-500 hover:bg-slate-50 hover:text-slate-800"
            onClick={() => { logout(); navigate("/login"); }}
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* mobile top nav */}
        <div className="sticky top-0 z-20 flex items-center gap-1 overflow-x-auto border-b border-slate-200 bg-white px-3 py-2 lg:hidden">
          <Logo />
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-full px-3 py-1.5 text-[12.5px] font-medium ${
                  isActive ? "bg-navy-800 text-white" : "text-slate-500"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
          <button
            className="ml-auto whitespace-nowrap rounded-full px-3 py-1.5 text-[12.5px] font-medium text-slate-500"
            onClick={() => { logout(); navigate("/login"); }}
          >
            Sign out
          </button>
        </div>

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
        <footer className="border-t border-slate-200 px-6 py-4 text-[11.5px] text-slate-400">
          CareerDNA predicts <span className="font-medium">placement readiness</span>, not placement outcomes.
          All data in this demo is synthetic.
        </footer>
      </div>
    </div>
  );
}

export function Logo({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="7" fill="#17293f" />
      <path d="M9 20c4-1 5-9 9-9 3 0 4 2 4 2" stroke="#2fbcae" strokeWidth="2.4" fill="none" strokeLinecap="round" />
      <circle cx="9" cy="20" r="2" fill="#5cd5c8" />
      <circle cx="22" cy="13" r="2" fill="#5cd5c8" />
    </svg>
  );
}

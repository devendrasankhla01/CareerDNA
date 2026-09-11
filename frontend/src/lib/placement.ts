import { STATUS_META } from "./format";

// ---------------------------------------------------------------- stage meta
export const STAGE_META: Record<string, { label: string; cls: string; step: number }> = {
  INTERESTED: { label: "Interested", cls: "bg-slate-100 text-slate-600 border-slate-200", step: 1 },
  HOD_APPROVED: { label: "HOD Endorsed", cls: "bg-amber-50 text-amber-700 border-amber-200", step: 2 },
  NOMINATED: { label: "Nominated", cls: "bg-navy-50 text-navy-700 border-navy-200", step: 3 },
  COMPANY_REVIEWING: { label: "Company Reviewing", cls: "bg-indigo-50 text-indigo-700 border-indigo-200", step: 4 },
  SHORTLISTED: { label: "Shortlisted", cls: "bg-violet-50 text-violet-700 border-violet-200", step: 5 },
  INTERVIEW: { label: "Interview", cls: "bg-sky-50 text-sky-700 border-sky-200", step: 6 },
  SELECTED: { label: "Selected", cls: "bg-emerald-50 text-emerald-700 border-emerald-200", step: 7 },
  PLACED: { label: "Placement Confirmed", cls: "bg-teal-50 text-teal-700 border-teal-200", step: 8 },
  NOT_SELECTED: { label: "Not Selected", cls: "bg-rose-50 text-rose-700 border-rose-200", step: 0 },
  WITHDRAWN: { label: "Withdrawn", cls: "bg-slate-100 text-slate-500 border-slate-200", step: 0 },
};

export function stageBadge(status: string) {
  return STAGE_META[status] || STATUS_META[status] || { label: status };
}

export const SKILL_LABELS: Record<string, string> = {
  PYTHON: "Python", JAVA: "Java", JAVASCRIPT: "JavaScript", C_CPP: "C/C++",
  SQL: "SQL", DSA: "DSA", GIT: "Git", CLOUD: "Cloud", CODING: "Coding",
  APTITUDE: "Aptitude", LOGICAL: "Logical Reasoning", COMMUNICATION: "Communication",
  INTERVIEW: "Interview", PRESENTATION: "Presentation", REACT: "React",
  NODE_JS: "Node.js", BACKEND: "Backend", REST_API: "REST API", HTML_CSS: "HTML/CSS",
  PANDAS: "Pandas", STATISTICS: "Statistics", EXCEL: "Excel", POWER_BI: "Power BI",
  DBMS: "DBMS",
};

export function skillLabel(code: string): string {
  return SKILL_LABELS[code] || code;
}

// pipeline steps shown on the student journey
export const JOURNEY_STEPS = [
  "INTERESTED", "HOD_APPROVED", "NOMINATED", "SHORTLISTED", "INTERVIEW", "SELECTED", "PLACED",
];

// TPO → verifier categories
export const VERIFY_CATEGORIES = [
  "TECHNICAL_SKILL", "PROJECT", "CERTIFICATION", "INTERNSHIP", "ACTIVITY",
];

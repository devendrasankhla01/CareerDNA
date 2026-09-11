import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Plus } from "lucide-react";
import { api } from "../../api/client";
import { fmt } from "../../lib/format";
import { Badge, Card, Disclaimer, ErrorBox, Spinner, Table } from "../../components/ui";

interface Company {
  id: number; name: string; industry: string | null; website: string | null;
  location: string | null; status: string;
  active_drives: number; total_drives: number;
  nominated: number; shortlisted: number; selected: number;
}
interface Resp { status: string; companies: Company[] }

export default function TpoCompanies() {
  const qc = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["tpo-companies"],
    queryFn: () => api<Resp>("/tpo/companies"),
  });
  const [show, setShow] = useState(false);

  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api("/tpo/companies", { method: "POST", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tpo-companies"] });
      setShow(false);
    },
  });
  const toggle = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      api(`/tpo/companies/${id}`, { method: "PUT", body: { status } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tpo-companies"] }),
  });

  if (isLoading) return <Spinner label="Loading companies…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Companies</h1>
          <p className="mt-0.5 text-[13px] text-slate-500">
            Placement companies onboarded by the TPO. No public registration — companies are
            institution-approved and each gets one recruiter account.
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShow(!show)}>
          <Plus className="mr-1.5 h-4 w-4" /> Onboard Company
        </button>
      </header>

      {show && (
        <CompanyForm
          onCreate={(b) => create.mutate(b)}
          busy={create.isPending}
          error={create.isError ? (create.error as Error).message : null}
        />
      )}

      <Card>
        {data.companies.length === 0 ? (
          <p className="py-6 text-center text-[13px] text-slate-400">No companies onboarded yet.</p>
        ) : (
          <Table head={
            <tr>
              <th>Company</th><th>Industry</th><th>Drives</th><th>Nominated</th>
              <th>Shortlisted</th><th>Selected</th><th>Status</th><th></th>
            </tr>
          }>
            {data.companies.map((c) => (
              <tr key={c.id}>
                <td>
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-navy-50 text-navy-700">
                      <Building2 className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="font-medium text-slate-800">{c.name}</div>
                      <div className="text-[11.5px] text-slate-400">{c.location || "—"}</div>
                    </div>
                  </div>
                </td>
                <td className="text-[12.5px] text-slate-600">{c.industry || "—"}</td>
                <td className="tabular-nums text-slate-600">{fmt(c.active_drives)} / {fmt(c.total_drives)}</td>
                <td className="tabular-nums text-slate-600">{fmt(c.nominated)}</td>
                <td className="tabular-nums text-slate-600">{fmt(c.shortlisted)}</td>
                <td className="tabular-nums text-slate-600">{fmt(c.selected)}</td>
                <td>
                  <Badge cls={c.status === "ACTIVE"
                    ? "bg-teal-50 text-teal-700 border-teal-200"
                    : "bg-slate-100 text-slate-500 border-slate-200"}>
                    {c.status}
                  </Badge>
                </td>
                <td>
                  <button className="text-[12px] font-medium text-slate-500 hover:text-slate-800"
                    onClick={() => toggle.mutate({ id: c.id, status: c.status === "ACTIVE" ? "INACTIVE" : "ACTIVE" })}>
                    {c.status === "ACTIVE" ? "Deactivate" : "Activate"}
                  </button>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Disclaimer>
        Companies see only the students the TPO nominates to their drives — never the full student
        list, never students who merely expressed interest, and never private contact data.
      </Disclaimer>
    </div>
  );
}

function CompanyForm({ onCreate, busy, error }: {
  onCreate: (b: Record<string, unknown>) => void; busy: boolean; error: string | null;
}) {
  const [f, setF] = useState({
    name: "", industry: "", location: "", website: "",
    recruiter_email: "", recruiter_name: "", recruiter_password: "",
  });
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF({ ...f, [k]: e.target.value });
  return (
    <Card title="Onboard a new company" subtitle="Creates the company record and (optionally) its recruiter login">
      <div className="grid gap-3 md:grid-cols-3">
        <div><label className="label">Company name *</label>
          <input className="input mt-1.5" value={f.name} onChange={set("name")} placeholder="Acme Technologies" /></div>
        <div><label className="label">Industry</label>
          <input className="input mt-1.5" value={f.industry} onChange={set("industry")} placeholder="Software Products" /></div>
        <div><label className="label">Location</label>
          <input className="input mt-1.5" value={f.location} onChange={set("location")} placeholder="Bengaluru" /></div>
        <div><label className="label">Website</label>
          <input className="input mt-1.5" value={f.website} onChange={set("website")} placeholder="https://…" /></div>
        <div><label className="label">Recruiter email</label>
          <input className="input mt-1.5" value={f.recruiter_email} onChange={set("recruiter_email")} placeholder="recruiter@company.example" /></div>
        <div><label className="label">Recruiter name</label>
          <input className="input mt-1.5" value={f.recruiter_name} onChange={set("recruiter_name")} placeholder="Full name" /></div>
        <div><label className="label">Recruiter password</label>
          <input className="input mt-1.5" value={f.recruiter_password} onChange={set("recruiter_password")} placeholder="Minimum 8 characters" /></div>
      </div>
      {error && <p className="mt-3 text-[12.5px] text-rose-600">{error}</p>}
      <button
        className="btn-primary mt-4"
        disabled={busy || !f.name.trim() || !f.recruiter_email.trim() || f.recruiter_password.length < 8}
        onClick={() => onCreate({ ...f })}>
        {busy ? "Creating…" : "Create company"}
      </button>
    </Card>
  );
}

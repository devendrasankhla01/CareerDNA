import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, GraduationCap, ShieldCheck, User } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuth } from "../lib/auth";
import { ApiError } from "../api/client";
import { Logo } from "../components/Layout";
import { homeFor } from "../App";

const usnSchema = z.object({
  usn: z.string().min(4, "Enter your institutional USN").max(30),
});
const otpSchema = z.object({
  usn: z.string(),
  otp: z.string().min(4, "Enter the 6-digit code").max(10),
});
const staffSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(6, "Minimum 6 characters"),
});

type Tab = "student" | "staff";

export default function Login() {
  const [tab, setTab] = useState<Tab>("student");
  const navigate = useNavigate();
  const { loginStudent, loginStaff, requestOtp } = useAuth();

  const usnForm = useForm<{ usn: string }>({ resolver: zodResolver(usnSchema) });
  const otpForm = useForm<{ usn: string; otp: string }>({ resolver: zodResolver(otpSchema) });
  const staffForm = useForm<{ email: string; password: string }>({ resolver: zodResolver(staffSchema) });

  const [step, setStep] = useState<"usn" | "otp">("usn");
  const [hint, setHint] = useState<string | null>(null);
  const [demoOtp, setDemoOtp] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const go = (role: string) => navigate(homeFor(role), { replace: true });

  const sendOtp = async (d: { usn: string }) => {
    setError(null); setBusy(true);
    try {
      const r = await requestOtp(d.usn.trim().toUpperCase());
      setHint(r.email_hint); setDemoOtp(r.demo_otp);
      otpForm.setValue("usn", d.usn.trim().toUpperCase());
      setStep("otp");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not send code");
    } finally { setBusy(false); }
  };

  const verify = async (d: { usn: string; otp: string }) => {
    setError(null); setBusy(true);
    try {
      await loginStudent(d.usn.trim().toUpperCase(), d.otp.trim());
      go("STUDENT");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Login failed");
    } finally { setBusy(false); }
  };

  const staffLogin = async (d: { email: string; password: string }) => {
    setError(null); setBusy(true);
    try {
      const u = await loginStaff(d.email.trim(), d.password);
      go(u.role); // each role lands on its own dashboard
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Login failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-navy-950 via-navy-900 to-navy-800 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center text-center">
          <Logo size={44} />
          <h1 className="mt-3 text-xl font-semibold text-white">CareerDNA</h1>
          <p className="mt-1 text-[13px] text-navy-200">
            Institutional career readiness &amp; upskilling engine
          </p>
        </div>

        <div className="card p-6">
          <div className="mb-5 grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1">
            {(["student", "staff"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => { setTab(t); setError(null); setStep("usn"); }}
                className={`flex items-center justify-center gap-2 rounded-md px-3 py-2 text-[13px] font-medium transition ${
                  tab === t ? "bg-white text-navy-900 shadow-sm" : "text-slate-500"
                }`}
              >
                {t === "student" ? <User className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
                {t === "student" ? "Student" : "Faculty / TPO"}
              </button>
            ))}
          </div>

          {error && (
            <div className="mb-4 flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-[13px] text-rose-700">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
            </div>
          )}

          {tab === "student" ? (
            step === "usn" ? (
              <form onSubmit={usnForm.handleSubmit(sendOtp)} className="space-y-4">
                <div>
                  <label className="label" htmlFor="usn">Institutional USN</label>
                  <input
                    id="usn" className="input mt-1.5 uppercase" placeholder="e.g. 3PM24CS042"
                    {...usnForm.register("usn")}
                  />
                  {usnForm.formState.errors.usn && (
                    <p className="mt-1 text-[12px] text-rose-600">{usnForm.formState.errors.usn.message}</p>
                  )}
                </div>
                <button className="btn-primary w-full" disabled={busy}>
                  {busy ? "Sending code…" : "Send verification code"}
                </button>
                <p className="text-[12px] leading-relaxed text-slate-400">
                  The one-time code is sent to your institutional registered email.
                </p>
              </form>
            ) : (
              <form onSubmit={otpForm.handleSubmit(verify)} className="space-y-4">
                <div>
                  <label className="label" htmlFor="otp">Verification code</label>
                  <input
                    id="otp" className="input mt-1.5 tracking-[0.3em]" placeholder="••••••"
                    {...otpForm.register("otp")}
                  />
                  {otpForm.formState.errors.otp && (
                    <p className="mt-1 text-[12px] text-rose-600">{otpForm.formState.errors.otp.message}</p>
                  )}
                </div>
                {hint && (
                  <p className="text-[12px] text-slate-500">Code sent to <span className="font-medium">{hint}</span></p>
                )}
                {demoOtp && (
                  <p className="rounded-lg bg-teal-50 px-3 py-2 text-[12px] text-teal-700">
                    Demo mode — use code <span className="font-semibold tabular-nums">{demoOtp}</span>
                  </p>
                )}
                <button className="btn-primary w-full" disabled={busy}>
                  {busy ? "Signing in…" : "Verify & sign in"}
                </button>
                <button type="button" className="w-full text-center text-[12.5px] font-medium text-navy-600 hover:underline"
                  onClick={() => { setStep("usn"); setError(null); }}>
                  Use a different USN
                </button>
              </form>
            )
          ) : (
            <form onSubmit={staffForm.handleSubmit(staffLogin)} className="space-y-4">
              <div>
                <label className="label" htmlFor="email">Institutional email</label>
                <input id="email" className="input mt-1.5" placeholder="name@northfielddemo.edu"
                  {...staffForm.register("email")} />
                {staffForm.formState.errors.email && (
                  <p className="mt-1 text-[12px] text-rose-600">{staffForm.formState.errors.email.message}</p>
                )}
              </div>
              <div>
                <label className="label" htmlFor="password">Password</label>
                <input id="password" type="password" className="input mt-1.5"
                  {...staffForm.register("password")} />
                {staffForm.formState.errors.password && (
                  <p className="mt-1 text-[12px] text-rose-600">{staffForm.formState.errors.password.message}</p>
                )}
              </div>
              <button className="btn-primary w-full" disabled={busy}>
                {busy ? "Signing in…" : "Sign in"}
              </button>
              <p className="flex items-start gap-1.5 text-[12px] leading-relaxed text-slate-400">
                <GraduationCap className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                Staff accounts are provisioned by the institution. No self-registration.
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, ShieldCheck, User } from "lucide-react";
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
  const staffForm = useForm<{ email: string; password: string }>({ resolver: zodResolver(staffSchema) });

  const [step, setStep] = useState<"usn" | "otp">("usn");
  const [activeUsn, setActiveUsn] = useState<string>("");
  const [otpDigits, setOtpDigits] = useState<string[]>(["", "", "", "", "", ""]);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  const [hint, setHint] = useState<string | null>(null);
  const [demoOtp, setDemoOtp] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const go = (role: string) => navigate(homeFor(role), { replace: true });

  const sendOtp = async (d: { usn: string }) => {
    setError(null);
    setBusy(true);
    const cleanUsn = d.usn.trim().toUpperCase();
    try {
      const r = await requestOtp(cleanUsn);
      setActiveUsn(cleanUsn);
      setHint(r.email_hint);
      setDemoOtp(r.demo_otp);
      setOtpDigits(["", "", "", "", "", ""]);
      setStep("otp");
      setTimeout(() => inputRefs.current[0]?.focus(), 80);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not send code");
    } finally {
      setBusy(false);
    }
  };

  const handleOtpChange = (index: number, rawVal: string) => {
    const clean = rawVal.replace(/\D/g, "");
    if (!clean) {
      const updated = [...otpDigits];
      updated[index] = "";
      setOtpDigits(updated);
      return;
    }

    // Single digit or last typed digit
    const digit = clean.slice(-1);
    const updated = [...otpDigits];
    updated[index] = digit;
    setOtpDigits(updated);

    // Auto advance to next box
    if (index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace") {
      if (otpDigits[index] !== "") {
        const updated = [...otpDigits];
        updated[index] = "";
        setOtpDigits(updated);
      } else if (index > 0) {
        inputRefs.current[index - 1]?.focus();
        const updated = [...otpDigits];
        updated[index - 1] = "";
        setOtpDigits(updated);
      }
    } else if (e.key === "ArrowLeft" && index > 0) {
      e.preventDefault();
      inputRefs.current[index - 1]?.focus();
    } else if (e.key === "ArrowRight" && index < 5) {
      e.preventDefault();
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleOtpPaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (!pasted) return;

    const updated = ["", "", "", "", "", ""];
    for (let i = 0; i < pasted.length && i < 6; i++) {
      updated[i] = pasted[i];
    }
    setOtpDigits(updated);

    const focusIdx = Math.min(pasted.length, 5);
    inputRefs.current[focusIdx]?.focus();
  };

  const otpValue = otpDigits.join("");
  const isOtpComplete = otpValue.length === 6 && /^\d{6}$/.test(otpValue);

  const verifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isOtpComplete || busy) return;
    setError(null);
    setBusy(true);
    try {
      await loginStudent(activeUsn, otpValue);
      go("STUDENT");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Login failed");
      setOtpDigits(["", "", "", "", "", ""]);
      setTimeout(() => inputRefs.current[0]?.focus(), 80);
    } finally {
      setBusy(false);
    }
  };

  const staffLogin = async (d: { email: string; password: string }) => {
    setError(null);
    setBusy(true);
    try {
      const u = await loginStaff(d.email.trim(), d.password);
      go(u.role); // each role lands on its own dashboard
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Login failed");
    } finally {
      setBusy(false);
    }
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
                onClick={() => {
                  setTab(t);
                  setError(null);
                  setStep("usn");
                  setOtpDigits(["", "", "", "", "", ""]);
                }}
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
                    id="usn"
                    className="input mt-1.5 uppercase"
                    placeholder="e.g. 3PM24CS042"
                    autoComplete="username"
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
              <form onSubmit={verifyOtp} className="space-y-4">
                <div>
                  <div className="flex items-center justify-between">
                    <label className="label">Verification code</label>
                    <span className="text-[11px] font-medium text-slate-400">6-digit code</span>
                  </div>

                  {/* 6 Individual Digit Inputs */}
                  <div className="mt-2.5 flex items-center justify-between gap-2">
                    {otpDigits.map((digit, idx) => (
                      <input
                        key={idx}
                        ref={(el) => (inputRefs.current[idx] = el)}
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        maxLength={1}
                        value={digit}
                        autoComplete={idx === 0 ? "one-time-code" : "off"}
                        aria-label={`OTP digit ${idx + 1}`}
                        disabled={busy}
                        onChange={(e) => handleOtpChange(idx, e.target.value)}
                        onKeyDown={(e) => handleOtpKeyDown(idx, e)}
                        onPaste={handleOtpPaste}
                        onFocus={(e) => e.target.select()}
                        className="h-12 w-11 rounded-lg border border-slate-300 bg-white text-center text-lg font-bold text-navy-950 shadow-sm transition-all focus:border-navy-600 focus:outline-none focus:ring-2 focus:ring-navy-600/20 disabled:bg-slate-100 disabled:text-slate-400 sm:w-12"
                      />
                    ))}
                  </div>
                </div>

                {hint && (
                  <p className="text-[12px] text-slate-500">
                    Code sent to <span className="font-medium text-slate-700">{hint}</span>
                  </p>
                )}
                {demoOtp && (
                  <p className="rounded-lg bg-teal-50 px-3 py-2 text-[12px] text-teal-700">
                    Demo mode — use code <span className="font-semibold tabular-nums">{demoOtp}</span>
                  </p>
                )}
                <button className="btn-primary w-full" disabled={busy || !isOtpComplete}>
                  {busy ? "Signing in…" : "Verify & sign in"}
                </button>
                <button
                  type="button"
                  className="w-full text-center text-[12.5px] font-medium text-navy-600 hover:underline"
                  onClick={() => {
                    setStep("usn");
                    setError(null);
                    setOtpDigits(["", "", "", "", "", ""]);
                  }}
                >
                  Use a different USN
                </button>
              </form>
            )
          ) : (
            <form onSubmit={staffForm.handleSubmit(staffLogin)} className="space-y-4">
              <div>
                <label className="label" htmlFor="email">Institutional email</label>
                <input
                  id="email"
                  className="input mt-1.5"
                  placeholder="name@northfielddemo.edu"
                  autoComplete="email"
                  {...staffForm.register("email")}
                />
                {staffForm.formState.errors.email && (
                  <p className="mt-1 text-[12px] text-rose-600">{staffForm.formState.errors.email.message}</p>
                )}
              </div>
              <div>
                <label className="label" htmlFor="password">Password</label>
                <input
                  id="password"
                  type="password"
                  className="input mt-1.5"
                  autoComplete="current-password"
                  {...staffForm.register("password")}
                />
                {staffForm.formState.errors.password && (
                  <p className="mt-1 text-[12px] text-rose-600">{staffForm.formState.errors.password.message}</p>
                )}
              </div>
              <button className="btn-primary w-full" disabled={busy}>
                {busy ? "Signing in…" : "Sign in"}
              </button>
            </form>
          )}

          {/* 1-Click Demo Accounts */}
          <div className="mt-6 border-t border-slate-100 pt-4">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              ⚡ 1-Click Demo Logins
            </div>
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => {
                  setTab("student");
                  setStep("usn");
                  setError(null);
                  setOtpDigits(["", "", "", "", "", ""]);
                  usnForm.setValue("usn", "3PM24CS500");
                }}
                className="rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11.5px] font-medium text-slate-700 hover:border-navy-400 hover:bg-white"
              >
                🎓 Student (Aarav)
              </button>
              <button
                type="button"
                onClick={() => {
                  setTab("staff");
                  setError(null);
                  staffForm.setValue("email", "meera.iyer@northfielddemo.edu");
                  staffForm.setValue("password", "TPOAdmin123!");
                }}
                className="rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11.5px] font-medium text-slate-700 hover:border-navy-400 hover:bg-white"
              >
                👔 TPO Admin
              </button>
              <button
                type="button"
                onClick={() => {
                  setTab("staff");
                  setError(null);
                  staffForm.setValue("email", "dept.cse@northfielddemo.edu");
                  staffForm.setValue("password", "DeptDemo123!");
                }}
                className="rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11.5px] font-medium text-slate-700 hover:border-navy-400 hover:bg-white"
              >
                🏛️ HOD (CSE)
              </button>
              <button
                type="button"
                onClick={() => {
                  setTab("staff");
                  setError(null);
                  staffForm.setValue("email", "priya.nair@vervetech-demo.example");
                  staffForm.setValue("password", "RecruiterDemo123!");
                }}
                className="rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11.5px] font-medium text-slate-700 hover:border-navy-400 hover:bg-white"
              >
                🏢 Recruiter (VerveTech)
              </button>
              <button
                type="button"
                onClick={() => {
                  setTab("staff");
                  setError(null);
                  staffForm.setValue("email", "kavya.raghavan@northfielddemo.edu");
                  staffForm.setValue("password", "FacultyDemo123!");
                }}
                className="rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11.5px] font-medium text-slate-700 hover:border-navy-400 hover:bg-white"
              >
                👨‍🏫 Faculty Verifier
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


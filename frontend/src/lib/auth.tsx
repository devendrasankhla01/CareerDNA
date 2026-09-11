import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { api, clearSession, getSessionUser, setSession, type SessionUser } from "../api/client";

interface AuthCtx {
  user: SessionUser | null;
  loginStudent: (usn: string, otp: string) => Promise<SessionUser>;
  requestOtp: (usn: string) => Promise<{ email_hint: string | null; demo_otp: string | null }>;
  loginStaff: (email: string, password: string) => Promise<SessionUser>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(() => getSessionUser());

  const requestOtp = useCallback(async (usn: string) => {
    const d = await api<{ email_hint: string | null; demo_otp: string | null }>(
      "/auth/student/request-otp", { body: { usn } }
    );
    return d;
  }, []);

  const loginStudent = useCallback(async (usn: string, otp: string) => {
    const d = await api<{ token: string; user: SessionUser }>("/auth/student/verify-otp", {
      body: { usn, otp },
    });
    setSession(d.token, d.user);
    setUser(d.user);
    return d.user;
  }, []);

  const loginStaff = useCallback(async (email: string, password: string) => {
    const d = await api<{ token: string; user: SessionUser }>("/auth/staff/login", {
      body: { email, password },
    });
    setSession(d.token, d.user);
    setUser(d.user);
    return d.user;
  }, []);

  const logout = useCallback(() => {
    api("/auth/logout", { method: "POST", body: {} }).catch(() => undefined);
    clearSession();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loginStudent, requestOtp, loginStaff, logout }),
    [user, loginStudent, requestOtp, loginStaff, logout]
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth outside provider");
  return ctx;
}

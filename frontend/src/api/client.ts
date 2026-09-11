const TOKEN_KEY = "careerdna_token";
const USER_KEY = "careerdna_user";

export interface SessionUser {
  id: number;
  role: "STUDENT" | "FACULTY" | "VERIFIER" | "DEPARTMENT" | "COMPANY" | "TPO_ADMIN";
  email: string;
  display_name: string;
  is_active: boolean;
  student?: {
    id: number;
    usn: string;
    name: string;
    branch: string;
    semester: number;
    target_career_code: string | null;
    profile_version: number;
  };
  categories?: string[];
  department?: { code: string; name: string };
  company?: { id: number; name: string };
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getSessionUser(): SessionUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionUser;
  } catch {
    return null;
  }
}

export function setSession(token: string, user: SessionUser) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

interface ApiOpts {
  method?: string;
  body?: unknown;
  formData?: FormData;
}

export const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export async function api<T = any>(path: string, opts: ApiOpts = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.body !== undefined && !opts.formData) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_BASE}/api${path}`, {
    method: opts.method || (opts.body !== undefined || opts.formData ? "POST" : "GET"),
    headers,
    body: opts.formData ? opts.formData : opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  let data: any = null;
  const text = await res.text();
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text || res.statusText };
  }

  if (!res.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : data?.message || res.statusText;
    if (res.status === 401) clearSession();
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

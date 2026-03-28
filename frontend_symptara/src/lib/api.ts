const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

// ── Authenticated fetch wrapper ───────────────────────────────────────────────
// Every call passes the Supabase JWT as Bearer token.
// If the server returns 4xx/5xx, we throw the parsed JSON body so callers
// can inspect err.status and err.detail for quota / auth errors.

async function apiFetch(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<any> {
  const headers: Record<string, string> = {
    ...(options.body && !(options.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string> | undefined),
  };

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    let detail: any = {};
    try { detail = await res.json(); } catch { /* non-JSON error body */ }
    const err: any = new Error(detail?.detail?.message || detail?.message || res.statusText);
    err.status = res.status;
    err.detail = detail?.detail ?? detail;
    throw err;
  }

  return res.json();
}

// ── API surface ───────────────────────────────────────────────────────────────

export const api = {
  sendMessage: (body: Record<string, unknown>, token: string) =>
    apiFetch("/consultation/message", {
      method: "POST",
      body:   JSON.stringify(body),
    }, token),

  uploadFile: (
    sessionId: string | null,
    userId: string,
    file: File,
    token: string
  ) => {
    const form = new FormData();
    form.append("file", file);
    if (sessionId) form.append("session_id", sessionId);
    form.append("user_id", userId);
    return apiFetch("/consultation/upload-file", {
      method: "POST",
      body:   form,
    }, token);
  },

  newSession: (userId: string, currentSessionId: string | null, token: string) =>
    apiFetch("/consultation/new-session", {
      method: "POST",
      body:   JSON.stringify({ user_id: userId, session_id: currentSessionId }),
    }, token),

  downloadReport: (sessionId: string, userId: string, token: string) =>
    apiFetch(`/consultation/report/${sessionId}?user_id=${userId}`, {}, token),

  getSession: (sessionId: string, token: string) =>
    apiFetch(`/consultation/session/${sessionId}`, {}, token),

  getProfile: (userId: string, token: string) =>
    apiFetch(`/profile/${userId}`, {}, token),

  saveProfile: (userId: string, profile: Record<string, unknown>, token: string) =>
    apiFetch("/profile/", {
      method: "POST",
      body:   JSON.stringify({ user_id: userId, ...profile }),
    }, token),
};
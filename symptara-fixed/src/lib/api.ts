const API_BASE = "http://localhost:8001";

export const api = {
  sendMessage: async (body: Record<string, unknown>) => {
    const res = await fetch(`${API_BASE}/consultation/message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  },

  uploadFile: async (sessionId: string | null, userId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("user_id", userId);
    if (sessionId) formData.append("session_id", sessionId);
    const res = await fetch(`${API_BASE}/consultation/upload-file`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error(`Upload error: ${res.status}`);
    return res.json();
  },

  newSession: async (userId: string, currentSessionId: string | null) => {
    const params = new URLSearchParams({ user_id: userId });
    if (currentSessionId) params.append("current_session_id", currentSessionId);
    const res = await fetch(`${API_BASE}/consultation/new-session?${params}`, {
      method: "POST",
    });
    if (!res.ok) throw new Error(`New session error: ${res.status}`);
    return res.json();
  },

  downloadReport: async (sessionId: string, userId: string) => {
    const res = await fetch(
      `${API_BASE}/consultation/report/${sessionId}?user_id=${userId}`
    );
    if (!res.ok) throw new Error(`Report error: ${res.status}`);
    return res.json();
  },

  getProfile: async (userId: string) => {
    const res = await fetch(`${API_BASE}/profile/${userId}`);
    if (!res.ok) throw new Error(`Profile error: ${res.status}`);
    return res.json();
  },

  saveProfile: async (profile: Record<string, unknown>) => {
    const res = await fetch(`${API_BASE}/profile/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    });
    if (!res.ok) throw new Error(`Profile save error: ${res.status}`);
    return res.json();
  },
};

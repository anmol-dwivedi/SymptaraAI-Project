import { useState, useCallback } from "react";
import type {
  ConsultationState,
  Message,
  ResultsData,
  ConsultationResponse,
  DiagnosisCandidate,
  ConfirmatoryTest,
  Medication,
  DrugInteraction,
  Doctor,
  PubmedPaper,
  ClinicalGuideline,
} from "@/types/consultation";
import { api } from "@/lib/api";

const USER_ID = "00000000-0000-0000-0000-000000000001";

const initialState: ConsultationState = {
  session_id: null,
  accumulated_symptoms: [],
  turn_count: 0,
  is_post_conclusion: false,
  lat: null,
  lng: null,
  location_text: null,
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  local_time: new Date().toISOString().slice(0, 19),
  input_method: "text",
  file_analysis: null,
  urgency_level: null,
  state: "GATHERING",
  is_conclusion: false,
};

const initialResults: ResultsData = {
  diagnoses: [],
  tests: [],
  medications: [],
  interactions: [],
  doctors: [],
  pubmed: [],
  guidelines: [],
  specialistType: null,
  fileAnalysis: null,
};

// ── API response → frontend type mappers ──────────────────────────────────────

function scoreToConfidence(score: number): "High" | "Medium" | "Low" {
  if (score >= 0.7) return "High";
  if (score >= 0.4) return "Medium";
  return "Low";
}

function mapDiagnoses(raw: any[]): DiagnosisCandidate[] {
  if (!raw?.length) return [];
  return raw.map((d) => ({
    disease:     d.disease || d.name || "",
    confidence:  scoreToConfidence(d.match_ratio ?? d.score ?? 0),
    match_score: d.match_ratio ?? d.score ?? 0,
    description: d.description || "",
  }));
}

function mapTests(raw: any[]): ConfirmatoryTest[] {
  if (!raw?.length) return [];
  return raw.map((t) => ({
    test_name: t.test || t.test_name || "",
    priority:  (t.urgency || t.priority || "Routine") as ConfirmatoryTest["priority"],
    purpose:   t.purpose || "",
  }));
}

function mapMedications(raw: any[]): Medication[] {
  if (!raw?.length) return [];
  return raw.map((m) => ({
    drug_name:  m.name || m.drug_name || "",
    source:     m.available ? "FDA" : undefined,
    warnings:   m.warnings ? (Array.isArray(m.warnings) ? m.warnings : [m.warnings]) : [],
    dosage:     m.dosage || "",
    indication: m.indications || m.indication || "",
  }));
}

function mapInteractions(raw: any[]): DrugInteraction[] {
  if (!raw?.length) return [];
  return raw.map((i) => ({
    drug1:       i.drug_1 || i.drug1 || "",
    drug2:       i.drug_2 || i.drug2 || "",
    severity:    (i.severity || "low") as DrugInteraction["severity"],
    description: i.description || "",
  }));
}

function mapDoctors(raw: any[]): Doctor[] {
  if (!raw?.length) return [];
  return raw.map((d) => ({
    name:      d.name || "",
    address:   d.address || "",
    rating:    d.rating || 0,
    maps_link: d.google_maps_link || d.maps_link || "",
    specialty: d.specialty || "",
  }));
}

function mapPubmed(raw: any[]): PubmedPaper[] {
  if (!raw?.length) return [];
  return raw.map((p) => ({
    title:   p.title || "",
    authors: typeof p.authors === "string"
      ? p.authors.split(",").map((a: string) => a.trim())
      : (p.authors || []),
    journal: p.journal || "",
    year:    p.year || "",
    link:    p.url || p.link || "",
  }));
}

function mapGuidelines(raw: any): ClinicalGuideline[] {
  if (!raw) return [];
  if (typeof raw === "object" && !Array.isArray(raw)) {
    if (!raw.guideline && !raw.content) return [];
    return [{
      title:   raw.disease || "Clinical Guidelines",
      source:  raw.source || "NLM",
      content: raw.guideline || raw.content || "",
    }];
  }
  if (Array.isArray(raw)) {
    return raw.map((g: any) => ({
      title:   g.disease || g.title || "Clinical Guidelines",
      source:  g.source || "NLM",
      content: g.guideline || g.content || "",
    }));
  }
  return [];
}

// ── Main hook ─────────────────────────────────────────────────────────────────

export function useConsultation() {
  const [state, setState] = useState<ConsultationState>(initialState);
  const [messages, setMessages] = useState<Message[]>([]);
  const [results, setResults] = useState<ResultsData>(initialResults);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [isEmergency, setIsEmergency] = useState(false);
  const [apiConnected, setApiConnected] = useState(true);

  const setLocation = useCallback((lat: number, lng: number, text: string) => {
    setState((s) => ({ ...s, lat, lng, location_text: text }));
  }, []);

  const sendMessage = useCallback(
    async (message: string, inputMethod: "text" | "voice" = "text") => {
      const userMsg: Message = {
        id:        crypto.randomUUID(),
        role:      "user",
        content:   message,
        timestamp: new Date(),
      };
      setMessages((m) => [...m, userMsg]);
      setIsLoading(true);

      try {
        const body = {
          user_id:              USER_ID,
          session_id:           state.session_id,
          message,
          accumulated_symptoms: state.accumulated_symptoms,
          turn_count:           state.turn_count,
          file_analysis:        state.file_analysis,
          lat:                  state.lat,
          lng:                  state.lng,
          location_text:        state.location_text,
          input_method:         inputMethod,
          is_post_conclusion:   state.is_post_conclusion,
          timezone:             Intl.DateTimeFormat().resolvedOptions().timeZone,
          local_time:           new Date().toISOString().slice(0, 19),
        };

        const data: ConsultationResponse = await api.sendMessage(body);
        setApiConnected(true);

        const isNowPostConclusion = state.is_post_conclusion || data.is_conclusion;

        const sysMsg: Message = {
          id:               crypto.randomUUID(),
          role:             "system",
          content:          data.response,
          timestamp:        new Date(),
          isPostConclusion: isNowPostConclusion,
        };
        setMessages((m) => [...m, sysMsg]);

        setState((s) => ({
          ...s,
          session_id:           data.session_id,
          accumulated_symptoms: data.all_symptoms || s.accumulated_symptoms,
          turn_count:           data.turn_count,
          state:                data.is_conclusion ? "CONCLUSION" : data.state,
          is_post_conclusion:   isNowPostConclusion,
          is_conclusion:        data.is_conclusion,
          urgency_level:        data.urgency_level || s.urgency_level,
          file_analysis:        null,
        }));

        if (data.urgency_level === "emergency") setIsEmergency(true);

        const mcp = (data as any).mcp_enrichment || {};

        setResults((r) => ({
          ...r,
          diagnoses:      data.graph_candidates ? mapDiagnoses(data.graph_candidates as any) : r.diagnoses,
          doctors:        data.doctors           ? mapDoctors(data.doctors as any)            : r.doctors,
          specialistType: (data as any).specialist_type || r.specialistType,
          tests:          mcp.tests              ? mapTests(mcp.tests)                        : r.tests,
          medications:    mcp.drugs              ? mapMedications(mcp.drugs)                  : r.medications,
          interactions:   mcp.interactions       ? mapInteractions(mcp.interactions)          : r.interactions,
          pubmed:         mcp.pubmed_papers       ? mapPubmed(mcp.pubmed_papers)              : r.pubmed,
          guidelines:     mcp.guidelines         ? mapGuidelines(mcp.guidelines)              : r.guidelines,
        }));

        setUploadedFileName(null);
      } catch {
        setApiConnected(false);
        const errMsg: Message = {
          id:        crypto.randomUUID(),
          role:      "system",
          content:   "Connection error. Please ensure the backend is running at http://localhost:8001",
          timestamp: new Date(),
        };
        setMessages((m) => [...m, errMsg]);
      } finally {
        setIsLoading(false);
      }
    },
    [state]
  );

  const uploadFile = useCallback(
    async (file: File) => {
      setIsUploading(true);
      try {
        const data = await api.uploadFile(state.session_id, USER_ID, file);
        setState((s) => ({ ...s, file_analysis: data.analysis }));
        setUploadedFileName(file.name);
        setResults((r) => ({ ...r, fileAnalysis: data.analysis }));
      } catch {
        setApiConnected(false);
      } finally {
        setIsUploading(false);
      }
    },
    [state.session_id]
  );

  const removeFile = useCallback(() => {
    setState((s) => ({ ...s, file_analysis: null }));
    setUploadedFileName(null);
    setResults((r) => ({ ...r, fileAnalysis: null }));
  }, []);

  const newSession = useCallback(async () => {
    try {
      await api.newSession(USER_ID, state.session_id);
    } catch {
      // proceed anyway
    }
    setState(initialState);
    setMessages([]);
    setResults(initialResults);
    setIsEmergency(false);
    setUploadedFileName(null);
  }, [state.session_id]);

  // Downloads raw report as .html file
  const downloadReport = useCallback(async () => {
    if (!state.session_id) return;
    try {
      const data = await api.downloadReport(state.session_id, USER_ID);
      const html = generateReportHTML(data, []);
      const blob = new Blob([html], { type: "text/html" });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = "symptara_report.html";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // silent
    }
  }, [state.session_id]);

  // Opens the styled report in a new tab and triggers browser print dialog.
  // User selects "Save as PDF" — no external library needed.
  const downloadReportAsPDF = useCallback(async () => {
    if (!state.session_id) return;
    try {
      const data        = await api.downloadReport(state.session_id, USER_ID);
      const html        = generateReportHTML(data, messages);
      const printWindow = window.open("", "_blank");
      if (!printWindow) {
        // Popup blocked — fall back to HTML download
        const blob = new Blob([html], { type: "text/html" });
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement("a");
        a.href     = url;
        a.download = "symptara_report.html";
        a.click();
        URL.revokeObjectURL(url);
        return;
      }
      printWindow.document.write(html);
      printWindow.document.close();
      // Wait for fonts + styles to render before triggering print
      setTimeout(() => {
        printWindow.focus();
        printWindow.print();
      }, 800);
    } catch {
      // silent
    }
  }, [state.session_id, messages]);

  // Called by MedicalInfoDrawer after successful save.
  // Backend fetches profile fresh from Supabase on every triage call,
  // so next message send will automatically use the newly saved profile.
  const refreshProfile = useCallback(() => {
    // intentional no-op — profile is read server-side per turn
  }, []);

  return {
    state,
    messages,
    results,
    isLoading,
    isUploading,
    uploadedFileName,
    isEmergency,
    apiConnected,
    sendMessage,
    uploadFile,
    removeFile,
    newSession,
    downloadReport,
    downloadReportAsPDF,
    setLocation,
    refreshProfile,
  };
}

// ── Report HTML generator ─────────────────────────────────────────────────────
// Used by both downloadReport (HTML) and downloadReportAsPDF (print).
// Includes the full conversation transcript so doctors see everything.

function generateReportHTML(data: Record<string, unknown>, messages: Message[]): string {
  const meta         = (data.report_metadata as any)       || {};
  const profile      = (data.patient_profile as any)       || {};
  const summary      = (data.consultation_summary as any)  || {};
  const diagnoses    = (data.differential_diagnoses as any[]) || [];
  const tests        = (data.confirmatory_tests as any[])  || [];
  const meds         = (data.medications as any[])         || [];
  const interactions = (data.drug_interactions as any[])   || [];
  const papers       = (data.pubmed_references as any[])   || [];
  const guidelines   = (data.clinical_guidelines as any)   || {};
  const files        = (data.uploaded_file_analyses as string[]) || [];

  // Use transcript from API if available, otherwise fall back to in-memory messages
  const transcript: Array<{role: string; content: string}> =
    (data.conversation_transcript as any[]) ||
    messages.map((m) => ({ role: m.role, content: m.content })) ||
    [];

  const confColor = (c: string) =>
    c === "High" ? "#00FF88" : c === "Medium" ? "#FFB800" : "#FF3B3B";
  const prioColor = (p: string) =>
    p === "STAT" ? "#FF3B3B" : p === "Urgent" ? "#FFB800" : "#00D4FF";
  const sevColor  = (s: string) =>
    s === "high" ? "#FF3B3B" : s === "moderate" ? "#FFB800" : "#FFD700";

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Symptara Consultation Report</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:Inter,system-ui,sans-serif;background:#0A0A0F;color:#fff;padding:40px 20px;max-width:860px;margin:auto;line-height:1.6}
    h1{color:#00D4FF;font-size:26px;margin-bottom:4px;font-weight:700}
    .tagline{color:#8B8FA8;font-size:12px;margin-bottom:28px}
    h2{color:#7B2FFF;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid #2A2A3A;padding-bottom:6px;margin:24px 0 12px}
    .card{background:#1A1A24;border:1px solid #2A2A3A;border-radius:10px;padding:14px;margin-bottom:10px}
    .grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
    .mi{display:flex;flex-direction:column;gap:2px}
    .ml{font-size:10px;color:#8B8FA8;text-transform:uppercase;letter-spacing:.5px}
    .mv{font-size:13px;color:#fff}
    .badge{display:inline-block;border-radius:20px;padding:2px 8px;font-size:10px;font-weight:600;border:1px solid}
    .row{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
    table{width:100%;border-collapse:collapse}
    th{background:#111118;color:#8B8FA8;font-size:10px;text-transform:uppercase;letter-spacing:.5px;text-align:left;padding:8px 10px;border-bottom:1px solid #2A2A3A}
    td{padding:8px 10px;font-size:13px;border-bottom:1px solid #1E1E2A;vertical-align:top}
    tr:last-child td{border-bottom:none}
    .warn{background:rgba(255,184,0,.06);border:1px solid rgba(255,184,0,.25);border-radius:6px;padding:8px 10px;margin-top:8px;font-size:12px;color:#FFB800}
    a{color:#00D4FF;text-decoration:none}
    .summary{background:#111118;border-left:3px solid #00D4FF;padding:12px 14px;border-radius:0 8px 8px 0;font-size:13px;color:#ccc;font-style:italic;margin-bottom:4px}
    .pre{background:#111118;border:1px solid #2A2A3A;border-radius:8px;padding:12px;font-size:12px;color:#ccc;white-space:pre-wrap;word-break:break-word}
    .disc{margin-top:36px;padding:14px;background:#111118;border:1px solid #2A2A3A;border-radius:8px;font-size:11px;color:#8B8FA8;text-align:center}
    .msg-user{background:#2A1A4A;border-radius:10px 10px 2px 10px;padding:10px 14px;font-size:13px;margin-bottom:8px;max-width:80%;margin-left:auto;text-align:right}
    .msg-system{background:#1A1A24;border-left:2px solid #00D4FF;border-radius:0 10px 10px 0;padding:10px 14px;font-size:13px;margin-bottom:8px;max-width:90%;white-space:pre-wrap}
    .msg-post{border-left-color:#7B2FFF}
    .msg-label{font-size:10px;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;font-weight:600}
    @media print{
      body{background:#fff;color:#000;padding:20px}
      h1{color:#0088AA}
      h2{color:#5500AA}
      .card{background:#f8f8f8;border-color:#ddd}
      .ml{color:#666}
      .mv{color:#000}
      .summary{background:#f0f8ff;border-left-color:#0088AA;color:#333}
      .msg-user{background:#f0e8ff;color:#000}
      .msg-system{background:#f8f8f8;border-left-color:#0088AA;color:#000}
      .msg-post{border-left-color:#5500AA}
      .pre{background:#f8f8f8;border-color:#ddd;color:#333}
      .disc{background:#f8f8f8;border-color:#ddd;color:#666}
      a{color:#0088AA}
    }
  </style>
</head>
<body>

<h1>Symptara</h1>
<p class="tagline">Hybrid RAG &amp; Medical MCP Powered Symptom Triage — Consultation Report</p>

<div class="card">
  <div class="grid2">
    <div class="mi"><span class="ml">Consultation Time</span><span class="mv">${meta.consultation_time || "—"}</span></div>
    <div class="mi"><span class="ml">Location</span><span class="mv">${meta.patient_location || "Not provided"}</span></div>
    <div class="mi"><span class="ml">Timezone</span><span class="mv">${meta.patient_timezone || "—"}</span></div>
    <div class="mi"><span class="ml">Session ID</span><span class="mv" style="font-size:10px;color:#8B8FA8">${meta.session_id || "—"}</span></div>
  </div>
</div>

${profile.available ? `
<h2>Patient Profile</h2>
<div class="card"><div class="grid2">
  ${profile.age            ? `<div class="mi"><span class="ml">Age</span><span class="mv">${profile.age}</span></div>` : ""}
  ${profile.sex            ? `<div class="mi"><span class="ml">Sex</span><span class="mv">${profile.sex}</span></div>` : ""}
  ${profile.blood_type     ? `<div class="mi"><span class="ml">Blood Type</span><span class="mv">${profile.blood_type}</span></div>` : ""}
  ${profile.chronic_conditions?.length   ? `<div class="mi"><span class="ml">Chronic Conditions</span><span class="mv">${profile.chronic_conditions.join(", ")}</span></div>` : ""}
  ${profile.current_medications?.length  ? `<div class="mi"><span class="ml">Current Medications</span><span class="mv">${profile.current_medications.join(", ")}</span></div>` : ""}
  ${profile.allergies?.length            ? `<div class="mi"><span class="ml">Allergies</span><span class="mv">${profile.allergies.join(", ")}</span></div>` : ""}
  ${profile.past_surgeries?.length       ? `<div class="mi"><span class="ml">Past Surgeries</span><span class="mv">${profile.past_surgeries.join(", ")}</span></div>` : ""}
</div></div>` : ""}

${summary.plain_summary ? `<h2>Clinical Summary</h2><div class="summary">${summary.plain_summary}</div>` : ""}

${diagnoses.length ? `
<h2>Differential Diagnoses</h2>
${diagnoses.map((d: any) => `<div class="card"><div class="row">
  <span style="font-weight:600;font-size:14px">${d.disease}</span>
  <div style="display:flex;align-items:center;gap:8px">
    <span style="font-size:12px;color:#8B8FA8">${d.score ? (d.score * 100).toFixed(0) + "% match" : ""}</span>
    <span class="badge" style="color:${confColor(d.confidence)};border-color:${confColor(d.confidence)}40">${d.confidence}</span>
  </div>
</div></div>`).join("")}` : ""}

${tests.length ? `
<h2>Confirmatory Tests</h2>
<div class="card" style="padding:0;overflow:hidden"><table>
  <thead><tr><th>Priority</th><th>Test</th><th>Purpose</th></tr></thead>
  <tbody>${tests.map((t: any) => `<tr>
    <td><span class="badge" style="color:${prioColor(t.urgency || t.priority)};border-color:${prioColor(t.urgency || t.priority)}40">${t.urgency || t.priority || "Routine"}</span></td>
    <td>${t.test || t.test_name || ""}</td>
    <td style="color:#8B8FA8">${t.purpose || ""}</td>
  </tr>`).join("")}</tbody>
</table></div>` : ""}

${meds.length ? `
<h2>Suggested Medications</h2>
${meds.map((m: any) => `<div class="card">
  <div class="row">
    <span style="font-weight:600">${m.drug_name || m.name || ""}</span>
    <span class="badge" style="color:#00D4FF;border-color:#00D4FF40">FDA</span>
  </div>
  ${m.indication || m.indications ? `<p style="font-size:12px;color:#8B8FA8;margin-top:6px">${m.indication || m.indications}</p>` : ""}
  ${m.warnings?.length ? `<div class="warn">⚠ ${Array.isArray(m.warnings) ? m.warnings.join(" | ") : m.warnings}</div>` : ""}
</div>`).join("")}` : ""}

${interactions.length ? `
<h2>Drug Interactions</h2>
${interactions.map((i: any) => `<div class="card">
  <div class="row">
    <span style="font-weight:600">${i.drug_1 || i.drug1 || ""} ↔ ${i.drug_2 || i.drug2 || ""}</span>
    <span class="badge" style="color:${sevColor(i.severity)};border-color:${sevColor(i.severity)}40">${i.severity}</span>
  </div>
  <p style="font-size:12px;color:#8B8FA8;margin-top:6px">${i.description || ""}</p>
</div>`).join("")}` : ""}

${papers.length ? `
<h2>PubMed References</h2>
${papers.map((p: any) => `<div class="card">
  <a href="${p.url || p.link || "#"}" style="font-size:13px;font-weight:500">${p.title || ""}</a>
  <p style="font-size:11px;color:#8B8FA8;margin-top:4px">
    ${typeof p.authors === "string" ? p.authors : (p.authors || []).slice(0, 3).join(", ")}${Array.isArray(p.authors) && p.authors.length > 3 ? " et al." : ""}
    — ${p.journal || ""} (${p.year || ""})
  </p>
</div>`).join("")}` : ""}

${(guidelines.guideline || guidelines.content) ? `
<h2>Clinical Guidelines</h2>
<div class="card">
  <div class="row" style="margin-bottom:8px">
    <span style="font-weight:600">${guidelines.disease || "Guidelines"}</span>
    <span class="badge" style="color:#7B2FFF;border-color:#7B2FFF40">${guidelines.source || "NLM"}</span>
  </div>
  <p style="font-size:12px;color:#8B8FA8">${guidelines.guideline || guidelines.content || ""}</p>
</div>` : ""}

${files.length ? `
<h2>Uploaded File Analyses</h2>
${files.map((f: string) => `<div class="pre">${f}</div>`).join("")}` : ""}

${transcript.length ? `
<h2>Full Consultation Transcript</h2>
<div style="margin-bottom:16px">
${transcript.map((m: any) => m.role === "user"
  ? `<div class="msg-user"><div class="msg-label" style="color:#9B7FCA">Patient</div>${m.content}</div>`
  : `<div class="msg-system ${m.isPostConclusion ? "msg-post" : ""}"><div class="msg-label" style="color:${m.isPostConclusion ? "#9B7FCA" : "#00D4FF"}">${m.isPostConclusion ? "Post-Consultation" : "Symptara"}</div>${m.content}</div>`
).join("")}
</div>` : ""}

<div class="disc">${meta.disclaimer || "This report was generated by Symptara, an AI-assisted medical consultation tool. It is NOT a clinical diagnosis. Please present this to a qualified healthcare professional for proper evaluation and treatment."}</div>

</body></html>`;
}

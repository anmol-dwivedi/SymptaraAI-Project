export interface ConsultationState {
  session_id: string | null;
  accumulated_symptoms: string[];
  turn_count: number;
  is_post_conclusion: boolean;
  lat: number | null;
  lng: number | null;
  location_text: string | null;
  timezone: string;
  local_time: string;
  input_method: "text" | "voice";
  file_analysis: string | null;
  urgency_level: string | null;
  state: "GATHERING" | "NARROWING" | "CONCLUSION" | "POST_CONCLUSION";
  is_conclusion: boolean;
}

export interface Message {
  id: string;
  role: "user" | "system";
  content: string;
  timestamp: Date;
  isPostConclusion?: boolean;
}

// ── User Identity (Profile button) ────────────────────────────────────────────
// Personal/contact information. Stored locally and included in the report.
export interface UserIdentity {
  user_id:    string;
  full_name?: string;
  email?:     string;
  phone?:     string;
  address?:   string;
  other_info?: string;   // free-text field for anything else
}

// ── User Medical Info (Medical Info button) ───────────────────────────────────
// Medical history. Sent to backend on every triage call for anti-hallucination.
export interface UserProfile {
  user_id:               string;
  age?:                  number;
  sex?:                  string;
  blood_type?:           string;
  allergies?:            string[];
  chronic_conditions?:   string[];
  current_medications?:  string[];
  past_surgeries?:       string[];
}

export interface DiagnosisCandidate {
  disease:      string;
  confidence:   "High" | "Medium" | "Low";
  match_score:  number;
  description?: string;
}

export interface ConfirmatoryTest {
  test_name: string;
  priority:  "STAT" | "Urgent" | "Routine";
  purpose:   string;
}

export interface Medication {
  drug_name:   string;
  source?:     string;
  warnings?:   string[];
  dosage?:     string;
  indication?: string;
}

export interface DrugInteraction {
  drug1:        string;
  drug2:        string;
  severity:     "high" | "moderate" | "low";
  description:  string;
}

export interface Doctor {
  name:       string;
  address:    string;
  rating:     number;
  maps_link?: string;
  specialty?: string;
}

export interface PubmedPaper {
  title:    string;
  authors:  string[];
  journal:  string;
  year:     number | string;
  link:     string;
}

export interface ClinicalGuideline {
  title:   string;
  source:  string;
  content: string;
}

export interface MCPEnrichment {
  drugs?:         Medication[];
  interactions?:  DrugInteraction[];
  tests?:         ConfirmatoryTest[];
  pubmed_papers?: PubmedPaper[];
  guidelines?:    ClinicalGuideline[];
}

export interface ConsultationResponse {
  session_id:       string;
  state:            ConsultationState["state"];
  response:         string;
  is_conclusion:    boolean;
  all_symptoms:     string[];
  graph_candidates?: DiagnosisCandidate[];
  turn_count:       number;
  doctors?:         Doctor[];
  urgency_level?:   string;
  specialist_type?: string;
  mcp_enrichment?:  MCPEnrichment;
}

export interface ResultsData {
  diagnoses:      DiagnosisCandidate[];
  tests:          ConfirmatoryTest[];
  medications:    Medication[];
  interactions:   DrugInteraction[];
  doctors:        Doctor[];
  pubmed:         PubmedPaper[];
  guidelines:     ClinicalGuideline[];
  specialistType: string | null;
  fileAnalysis:   string | null;
}

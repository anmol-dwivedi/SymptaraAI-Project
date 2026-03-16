import { useState, useEffect, useCallback } from "react";
import { Download, RotateCcw, AlertTriangle, FileText, Stethoscope, MapPin } from "lucide-react";
import SymptaraLogo from "@/components/SymptaraLogo";
import ResultsDashboard from "@/components/ResultsDashboard";
import MessageList from "@/components/MessageList";
import ConsultationInput from "@/components/ConsultationInput";
import FileDropZone from "@/components/FileDropZone";
import { IdentityDrawer, MedicalInfoDrawer } from "@/components/ProfileDrawer";
import { UserAccountDropdown } from "@/components/UserAccountDropdown";
import { useConsultation } from "@/hooks/useConsultation";

const IDENTITY_KEY = "symptara_user_identity";
const LOCATION_DECIDED_KEY = "symptara_location_decided";

const StateBadge = ({ state }: { state: string }) => {
  const styles: Record<string, string> = {
    GATHERING:       "bg-muted text-muted-foreground border-border",
    NARROWING:       "bg-warning/15 text-warning border-warning/30",
    CONCLUSION:      "bg-success/15 text-success border-success/30",
    POST_CONCLUSION: "bg-primary/15 text-primary border-primary/30",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
        styles[state] || styles.GATHERING
      }`}
    >
      {state.replace("_", " ")}
    </span>
  );
};

// ── Location toggle switch ────────────────────────────────────────────────────
const LocationToggle = ({
  enabled,
  locationText,
  onEnable,
  onDisable,
}: {
  enabled: boolean;
  locationText: string | null;
  onEnable: () => void;
  onDisable: () => void;
}) => (
  <button
    onClick={enabled ? onDisable : onEnable}
    className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${
      enabled
        ? "border-success/40 bg-success/10 text-success hover:bg-success/20"
        : "border-border bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground"
    }`}
    title={enabled ? `Location: ${locationText || "acquiring…"}` : "Enable location access"}
  >
    <MapPin size={13} className="shrink-0" />
    {/* Toggle track */}
    <span
      className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors ${
        enabled ? "bg-success" : "bg-border"
      }`}
    >
      <span
        className={`inline-block h-3 w-3 rounded-full bg-white shadow transition-transform ${
          enabled ? "translate-x-3.5" : "translate-x-0.5"
        }`}
      />
    </span>
    <span className="hidden sm:inline">
      {enabled ? (locationText || "Acquiring…") : "Location Access"}
    </span>
  </button>
);

// ── Non-skippable location modal ──────────────────────────────────────────────
const LocationModal = ({
  onAllow,
  onDeny,
}: {
  onAllow: () => void;
  onDeny: () => void;
}) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
    <div className="w-full max-w-sm rounded-xl border border-border bg-card p-6 shadow-2xl mx-4">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/15 border border-primary/30">
          <MapPin size={20} className="text-primary" />
        </div>
        <div>
          <h2 className="font-display text-base font-semibold text-foreground">Location Access</h2>
          <p className="text-xs text-muted-foreground">Required to find nearby doctors</p>
        </div>
      </div>

      <p className="mb-5 text-sm text-muted-foreground leading-relaxed">
        Symptara uses your location to recommend the most relevant specialists and nearby clinics
        at the end of your consultation. You can revoke access at any time using the toggle in the header.
      </p>

      <div className="flex flex-col gap-2">
        <button
          onClick={onAllow}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary py-2.5 text-sm font-semibold text-primary-foreground transition-all hover:brightness-110 active:scale-95"
        >
          <MapPin size={14} />
          Allow Location Access
        </button>
        <button
          onClick={onDeny}
          className="flex w-full items-center justify-center rounded-lg border border-border bg-muted/30 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          Continue Without Location
        </button>
      </div>
    </div>
  </div>
);

// ── Main page ─────────────────────────────────────────────────────────────────
const Index = () => {
  const {
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
    clearLocation,
    refreshProfile,
  } = useConsultation();

  const [identityOpen,   setIdentityOpen]   = useState(false);
  const [medicalOpen,    setMedicalOpen]     = useState(false);
  // true = location ON, false = location OFF, null = not yet decided (shows modal)
  const [locationOn,     setLocationOn]      = useState<boolean | null>(null);

  // On mount: show modal unless user has already decided this session
  useEffect(() => {
    const decided = sessionStorage.getItem(LOCATION_DECIDED_KEY);
    if (decided === "true")  { setLocationOn(true);  }
    else if (decided === "false") { setLocationOn(false); }
    else { setLocationOn(null); } // show modal
  }, []);

  // Reverse geocode via OpenStreetMap Nominatim (free, no key needed)
  const reverseGeocode = async (lat: number, lng: number): Promise<string> => {
    try {
      const res  = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`,
        { headers: { "Accept-Language": "en" } }
      );
      const data = await res.json();
      const addr = data.address || {};
      const parts = [
        addr.city || addr.town || addr.village || addr.county || "",
        addr.state || "",
        addr.country_code?.toUpperCase() || "",
      ].filter(Boolean);
      return parts.join(", ");
    } catch {
      return `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
    }
  };

  const enableLocation = useCallback(() => {
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        const locationText = await reverseGeocode(latitude, longitude);
        setLocation(latitude, longitude, locationText);
        setLocationOn(true);
        sessionStorage.setItem(LOCATION_DECIDED_KEY, "true");
      },
      () => {
        // Browser denied — still mark as decided so modal doesn't re-appear
        setLocationOn(false);
        sessionStorage.setItem(LOCATION_DECIDED_KEY, "false");
      },
      { timeout: 10000 }
    );
    setLocationOn(true);
    sessionStorage.setItem(LOCATION_DECIDED_KEY, "true");
  }, [setLocation]);

  const disableLocation = useCallback(() => {
    clearLocation();
    setLocationOn(false);
    sessionStorage.setItem(LOCATION_DECIDED_KEY, "false");
  }, [clearLocation]);

  // Modal handlers
  const handleModalAllow = () => enableLocation();
  const handleModalDeny  = () => {
    setLocationOn(false);
    sessionStorage.setItem(LOCATION_DECIDED_KEY, "false");
  };

  const handleNewSession = () => {
    if (
      messages.length > 0 &&
      !window.confirm("Start a new consultation? Current session will be closed.")
    ) return;
    newSession();
    // Reset location decision — show modal again on new session
    sessionStorage.removeItem(LOCATION_DECIDED_KEY);
    clearLocation();
    setLocationOn(null);
  };

  const handleSignOut = () => {
    if (!window.confirm("Sign out? Your local profile data will be cleared.")) return;
    localStorage.removeItem(IDENTITY_KEY);
    sessionStorage.removeItem(LOCATION_DECIDED_KEY);
    clearLocation();
    setLocationOn(null);
    newSession();
  };

  const hasResults =
    results.diagnoses.length    ||
    results.tests.length        ||
    results.medications.length  ||
    results.interactions.length ||
    results.doctors.length      ||
    results.pubmed.length       ||
    results.guidelines.length   ||
    results.fileAnalyses.length;

  const displayState      = state.is_post_conclusion ? "POST_CONCLUSION" : state.state;
  const canDownloadReport = state.is_conclusion || state.is_post_conclusion;

  return (
    <div className="flex h-screen flex-col bg-background">

      {/* ── Location modal — non-skippable, shown until user decides ─────── */}
      {locationOn === null && (
        <LocationModal onAllow={handleModalAllow} onDeny={handleModalDeny} />
      )}

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between border-b border-border px-4 py-3 lg:px-6">

        {/* Left — Logo + tagline */}
        <div className="flex items-center gap-3">
          <SymptaraLogo />
          <span className="hidden text-xs text-muted-foreground lg:block">
            Hybrid RAG &amp; MCP Powered Symptom Triage
          </span>
        </div>

        {/* Right — action buttons */}
        <div className="flex items-center gap-2">

          {/* Emergency SOS — always visible, calls 911 */}
          <a
            href="tel:911"
            className="flex items-center gap-1.5 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-1.5 text-xs font-semibold text-destructive transition-all hover:bg-destructive/20 hover:border-destructive/60 active:scale-95"
            title="Emergency SOS — calls 911"
          >
            <AlertTriangle size={13} className="shrink-0" />
            <span className="hidden sm:inline">Emergency SOS</span>
          </a>

          {/* Report Conversion — only visible after conclusion */}
          {canDownloadReport && (
            <button
              onClick={downloadReportAsPDF}
              className="flex items-center gap-1.5 rounded-lg border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary transition-all hover:bg-primary/20 hover:border-primary/60 active:scale-95"
              title="Download consultation report as PDF"
            >
              <FileText size={13} className="shrink-0" />
              <span className="hidden sm:inline">Report Conversion</span>
            </button>
          )}

          {/* Location Access toggle — persistent, always visible */}
          {locationOn !== null && (
            <LocationToggle
              enabled={locationOn}
              locationText={state.location_text}
              onEnable={enableLocation}
              onDisable={disableLocation}
            />
          )}

          {/* Connection status dot */}
          <div
            className={`h-2 w-2 rounded-full ${apiConnected ? "bg-success" : "bg-destructive"}`}
            title={apiConnected ? "Connected" : "Disconnected"}
          />

          {/* Medical Info — opens medical history drawer (purple) */}
          <button
            onClick={() => setMedicalOpen(true)}
            className="flex items-center gap-1.5 rounded-lg border border-secondary/40 bg-secondary/10 px-3 py-1.5 text-xs text-secondary transition-colors hover:bg-secondary/20 hover:border-secondary/60"
            title="Medical Info — allergies, conditions, medications"
          >
            <Stethoscope size={14} />
            <span className="hidden sm:inline">Medical Info</span>
          </button>

          {/* User Account Dropdown — shows name, edit profile, sign out */}
          <UserAccountDropdown
            onEditProfile={() => setIdentityOpen(true)}
            onSignOut={handleSignOut}
          />
        </div>
      </header>

      {/* ── Emergency Banner ────────────────────────────────────────────────── */}
      {isEmergency && (
        <div className="glow-emergency animate-pulse border-b border-destructive/30 bg-destructive/10 px-4 py-3 text-center text-sm font-semibold text-destructive">
          ⚠ EMERGENCY: Seek immediate medical attention.{" "}
          <a href="tel:911" className="underline hover:no-underline">Call 911</a>{" "}
          or go to the nearest ER.
        </div>
      )}

      {/* ── Main Content ────────────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden flex-col lg:flex-row">

        {/* Left Panel — Results Dashboard */}
        <div className="flex flex-col border-b border-border lg:w-[55%] lg:border-b-0 lg:border-r overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-4 py-2">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Results Dashboard
            </span>
            <div className="flex items-center gap-2">
              {canDownloadReport && (
                <button
                  onClick={downloadReport}
                  className="flex items-center gap-1 rounded-md bg-muted/50 px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                  title="Download raw report as HTML"
                >
                  <Download size={12} /> HTML
                </button>
              )}
              <button
                onClick={handleNewSession}
                className="flex items-center gap-1 rounded-md bg-destructive/10 px-2.5 py-1 text-xs text-destructive hover:bg-destructive/20 transition-colors"
              >
                <RotateCcw size={12} /> New Session
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {!hasResults ? (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <SymptaraLogo size="default" />
                <p className="mt-4 text-sm text-muted-foreground max-w-xs">
                  Hybrid RAG &amp; Medical MCP Powered Symptom Triage
                </p>
                <p className="mt-2 text-xs text-muted-foreground/60">
                  Start describing your symptoms to begin the consultation
                </p>
              </div>
            ) : (
              <ResultsDashboard results={results} />
            )}
          </div>
        </div>

        {/* Right Panel — Consultation */}
        <div
          className={`flex flex-1 flex-col lg:w-[45%] overflow-hidden transition-colors ${
            displayState === "POST_CONCLUSION" ? "bg-primary/[0.02]" : ""
          }`}
        >
          <div className="flex items-center justify-between border-b border-border px-4 py-2">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Consultation
            </span>
            <StateBadge state={displayState} />
          </div>

          <FileDropZone
            onUpload={uploadFile}
            onRemoveFile={removeFile}
            isUploading={isUploading}
            uploadedFileName={uploadedFileName}
          />

          <MessageList
            messages={messages}
            isLoading={isLoading}
            isPostConclusion={state.is_post_conclusion}
          />

          <ConsultationInput
            onSend={sendMessage}
            onUpload={uploadFile}
            isLoading={isLoading}
            isPostConclusion={state.is_post_conclusion}
          />
        </div>
      </div>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <footer className="border-t border-border px-4 py-2 text-center text-[10px] text-muted-foreground/60">
        Symptara is an AI-assisted tool. Not a substitute for professional medical advice. Always consult a qualified doctor.
      </footer>

      {/* ── Drawers ─────────────────────────────────────────────────────────── */}
      <IdentityDrawer
        open={identityOpen}
        onClose={() => setIdentityOpen(false)}
      />
      <MedicalInfoDrawer
        open={medicalOpen}
        onClose={() => setMedicalOpen(false)}
        onSaved={refreshProfile}
      />
    </div>
  );
};

export default Index;
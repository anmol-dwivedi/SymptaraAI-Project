/**
 * MedicalDisclaimerModal.tsx
 * ==========================
 * Shown to non-admin users before they can access the consultation.
 * Covers medical disclaimer + session quota info.
 * Must be explicitly accepted — cannot be dismissed otherwise.
 */

import { useState } from "react";
import { AlertTriangle, Shield, Clock, CheckCircle } from "lucide-react";

interface Props {
  onAccept: () => void;
}

export function MedicalDisclaimerModal({ onAccept }: Props) {
  const [checked, setChecked] = useState(false);

  return (
    <>
      <style>{`
        @keyframes sai-disclaimer-in {
          from { opacity: 0; transform: translateY(20px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        .sai-disclaimer-backdrop {
          position: fixed; inset: 0; z-index: 60;
          background: rgba(0,0,0,0.82);
          backdrop-filter: blur(4px);
          display: flex; align-items: center; justify-content: center;
          padding: 1rem;
        }
        .sai-disclaimer-card {
          width: 100%; max-width: 520px;
          background: #0d1117;
          border: 1px solid rgba(255,255,255,0.12);
          border-radius: 16px;
          overflow: hidden;
          animation: sai-disclaimer-in 0.3s ease;
        }
        .sai-disclaimer-header {
          background: rgba(220, 60, 60, 0.08);
          border-bottom: 1px solid rgba(220, 60, 60, 0.18);
          padding: 20px 24px;
          display: flex; align-items: center; gap: 14px;
        }
        .sai-disclaimer-icon {
          width: 44px; height: 44px; flex-shrink: 0;
          border-radius: 12px;
          background: rgba(220, 60, 60, 0.12);
          border: 1px solid rgba(220, 60, 60, 0.28);
          display: flex; align-items: center; justify-content: center;
          color: #e05555;
        }
        .sai-disclaimer-title {
          font-size: 17px; font-weight: 600;
          color: #e8edf2;
          margin-bottom: 2px;
        }
        .sai-disclaimer-subtitle {
          font-size: 12px;
          color: rgba(160,180,170,0.6);
        }
        .sai-disclaimer-body {
          padding: 20px 24px;
          display: flex; flex-direction: column; gap: 14px;
        }
        .sai-disclaimer-section {
          border-radius: 10px;
          padding: 14px 16px;
          border: 1px solid rgba(255,255,255,0.08);
          background: rgba(255,255,255,0.03);
        }
        .sai-disclaimer-section-title {
          font-size: 11px; font-weight: 600;
          text-transform: uppercase; letter-spacing: 0.08em;
          color: rgba(160,180,170,0.55);
          margin-bottom: 8px;
          display: flex; align-items: center; gap: 6px;
        }
        .sai-disclaimer-section-title svg {
          width: 13px; height: 13px; flex-shrink: 0;
        }
        .sai-disclaimer-text {
          font-size: 13px;
          color: rgba(200,210,205,0.8);
          line-height: 1.65;
        }
        .sai-disclaimer-bullets {
          list-style: none; padding: 0; margin: 8px 0 0;
          display: flex; flex-direction: column; gap: 6px;
        }
        .sai-disclaimer-bullets li {
          display: flex; align-items: flex-start; gap: 8px;
          font-size: 13px; color: rgba(180,200,190,0.7);
          line-height: 1.5;
        }
        .sai-disclaimer-bullets li::before {
          content: '';
          width: 4px; height: 4px; border-radius: 50%;
          background: rgba(160,180,170,0.4);
          flex-shrink: 0; margin-top: 8px;
        }
        .sai-quota-pills {
          display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px;
        }
        .sai-quota-pill {
          display: flex; align-items: center; gap: 6px;
          font-size: 12px; font-weight: 500;
          padding: 5px 12px; border-radius: 20px;
          background: rgba(32,210,150,0.08);
          border: 1px solid rgba(32,210,150,0.2);
          color: #5DCAA5;
        }
        .sai-quota-pill svg { width: 12px; height: 12px; }
        .sai-emergency-strip {
          margin: 0 24px 16px;
          padding: 10px 14px;
          border-radius: 8px;
          background: rgba(220,60,60,0.06);
          border: 1px solid rgba(220,60,60,0.18);
          font-size: 12px;
          color: #e05555;
          text-align: center;
          line-height: 1.5;
        }
        .sai-disclaimer-footer {
          padding: 0 24px 24px;
        }
      `}</style>

      <div className="sai-disclaimer-backdrop">
        <div className="sai-disclaimer-card">

          {/* Header */}
          <div className="sai-disclaimer-header">
            <div className="sai-disclaimer-icon">
              <AlertTriangle size={22} />
            </div>
            <div>
              <div className="sai-disclaimer-title">Medical Disclaimer</div>
              <div className="sai-disclaimer-subtitle">Please read before using SymptaraAI</div>
            </div>
          </div>

          {/* Body */}
          <div className="sai-disclaimer-body">

            {/* Important notice */}
            <div className="sai-disclaimer-section">
              <div className="sai-disclaimer-section-title">
                <Shield />
                Important notice
              </div>
              <p className="sai-disclaimer-text">
                SymptaraAI is an AI-assisted triage and decision-support tool.
                It is <strong style={{ color: "#e8edf2" }}>not a licensed medical device</strong> and
                does not replace the advice, diagnosis, or treatment of a qualified healthcare professional.
              </p>
              <ul className="sai-disclaimer-bullets">
                <li>All outputs must be reviewed by a doctor before acting on them</li>
                <li>Do not use this tool for emergency medical situations</li>
                <li>AI-generated differential diagnoses may be incomplete or incorrect</li>
                <li>Your consultation data is stored securely and is confidential</li>
              </ul>
            </div>

            {/* Free account limits */}
            <div className="sai-disclaimer-section">
              <div className="sai-disclaimer-section-title">
                <Clock />
                Free account limits
              </div>
              <p className="sai-disclaimer-text">
                Your free account includes a limited number of consultations per day.
                Sessions reset automatically every 24 hours.
              </p>
              <div className="sai-quota-pills">
                <div className="sai-quota-pill">
                  <Clock />
                  5 sessions per 24 hours
                </div>
                <div className="sai-quota-pill">
                  <CheckCircle />
                  Resets automatically
                </div>
              </div>
            </div>

            {/* Checkbox */}
            <div
              onClick={() => setChecked(c => !c)}
              style={{
                display: "flex", alignItems: "flex-start", gap: 10,
                padding: "14px 16px", borderRadius: 10, cursor: "pointer",
                border: `1px solid ${checked ? "rgba(32,210,150,0.4)" : "rgba(255,255,255,0.1)"}`,
                background: checked ? "rgba(32,210,150,0.06)" : "rgba(255,255,255,0.03)",
                transition: "all 0.15s",
              }}
            >
              <div style={{
                width: 18, height: 18, flexShrink: 0, marginTop: 1,
                borderRadius: 5, display: "flex", alignItems: "center", justifyContent: "center",
                border: checked ? "none" : "1.5px solid rgba(255,255,255,0.25)",
                background: checked ? "#0F6E56" : "transparent",
                transition: "all 0.15s",
              }}>
                {checked && (
                  <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                    <path d="M1.5 5.5L4.5 8.5L9.5 2.5" stroke="white" strokeWidth="1.8"
                          strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                )}
              </div>
              <span style={{ fontSize: 13, color: "rgba(200,215,205,0.8)", lineHeight: 1.5 }}>
                I understand that SymptaraAI is not a substitute for professional
                medical advice and I agree to use it responsibly.
              </span>
            </div>

          </div>
          {/* end .sai-disclaimer-body */}

          {/* Emergency strip */}
          <div className="sai-emergency-strip">
            In an emergency, call <strong>911</strong> immediately.
            Do not wait for an AI response.
          </div>

          {/* CTA button */}
          <div className="sai-disclaimer-footer">
            <button
              onClick={() => checked && onAccept()}
              disabled={!checked}
              style={{
                width: "100%", padding: "13px",
                borderRadius: 10, fontSize: 14, fontWeight: 600,
                border: "none", cursor: checked ? "pointer" : "not-allowed",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                background: checked ? "#0F6E56" : "rgba(255,255,255,0.05)",
                color: checked ? "#fff" : "rgba(255,255,255,0.25)",
                transition: "all 0.2s",
              }}
            >
              <CheckCircle size={16} />
              {checked ? "I understand — continue to SymptaraAI" : "Please read and accept above"}
            </button>
          </div>

        </div>
        {/* end .sai-disclaimer-card */}
      </div>
      {/* end .sai-disclaimer-backdrop */}
    </>
  );
}
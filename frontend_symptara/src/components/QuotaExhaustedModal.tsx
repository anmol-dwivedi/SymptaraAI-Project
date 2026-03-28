/**
 * QuotaExhaustedModal.tsx
 * =======================
 * Full blocking modal shown when user has used all 5 daily sessions.
 * Cannot be dismissed — user must wait for reset.
 */

import { useEffect, useState } from "react";
import { Clock, RotateCcw } from "lucide-react";
import type { QuotaError } from "@/hooks/useConsultation";

interface Props {
  quota: QuotaError;
}

function useCountdown(resetAt: string) {
  const [timeLeft, setTimeLeft] = useState("");

  useEffect(() => {
    function update() {
      const diff = new Date(resetAt).getTime() - Date.now();
      if (diff <= 0) { setTimeLeft("now"); return; }
      const h = Math.floor(diff / 3_600_000);
      const m = Math.floor((diff % 3_600_000) / 60_000);
      const s = Math.floor((diff % 60_000) / 1_000);
      setTimeLeft(
        h > 0
          ? `${h}h ${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`
          : `${m}m ${String(s).padStart(2, "0")}s`
      );
    }
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [resetAt]);

  return timeLeft;
}

export function QuotaExhaustedModal({ quota }: Props) {
  const countdown = useCountdown(quota.resetAt);
  const resetTime = new Date(quota.resetAt).toLocaleTimeString([], {
    hour: "2-digit", minute: "2-digit"
  });

  return (
    <>
      <style>{`
        @keyframes sai-quota-in {
          from { opacity: 0; transform: scale(0.95); }
          to   { opacity: 1; transform: scale(1); }
        }
        .sai-quota-backdrop {
          position: fixed; inset: 0; z-index: 60;
          background: rgba(0,0,0,0.8);
          backdrop-filter: blur(6px);
          display: flex; align-items: center; justify-content: center;
          padding: 1rem;
        }
        .sai-quota-card {
          width: 100%; max-width: 440px;
          background: var(--color-background-primary);
          border: 1px solid var(--color-border-secondary);
          border-radius: 16px;
          overflow: hidden;
          animation: sai-quota-in 0.25s ease;
          text-align: center;
        }
        .sai-quota-top {
          padding: 36px 32px 24px;
        }
        .sai-quota-clock-ring {
          width: 80px; height: 80px;
          border-radius: 50%;
          background: rgba(239, 159, 39, 0.08);
          border: 1px solid rgba(239, 159, 39, 0.2);
          display: flex; align-items: center; justify-content: center;
          margin: 0 auto 20px;
          color: #EF9F27;
        }
        .sai-quota-heading {
          font-size: 20px; font-weight: 600;
          color: var(--color-text-primary);
          margin-bottom: 8px;
        }
        .sai-quota-sub {
          font-size: 13px;
          color: var(--color-text-secondary);
          line-height: 1.6;
          max-width: 320px; margin: 0 auto;
        }
        .sai-quota-divider {
          border: none;
          border-top: 1px solid var(--color-border-tertiary);
        }
        .sai-quota-timer-section {
          padding: 24px 32px;
          background: var(--color-background-secondary);
        }
        .sai-quota-timer-label {
          font-size: 11px; font-weight: 600;
          text-transform: uppercase; letter-spacing: 0.1em;
          color: var(--color-text-tertiary);
          margin-bottom: 10px;
        }
        .sai-quota-countdown {
          font-size: 36px; font-weight: 700;
          color: #EF9F27;
          font-variant-numeric: tabular-nums;
          letter-spacing: -0.02em;
          margin-bottom: 6px;
        }
        .sai-quota-reset-time {
          font-size: 12px;
          color: var(--color-text-tertiary);
        }
        .sai-quota-footer {
          padding: 20px 32px 28px;
        }
        .sai-quota-dots {
          display: flex; justify-content: center; gap: 8px;
          margin-bottom: 16px;
        }
        .sai-quota-dot {
          width: 8px; height: 8px; border-radius: 50%;
          background: rgba(239, 159, 39, 0.3);
        }
        .sai-quota-dot.used {
          background: #EF9F27;
        }
        .sai-quota-dots-label {
          font-size: 11px;
          color: var(--color-text-tertiary);
          margin-bottom: 16px;
        }
        .sai-quota-note {
          font-size: 12px;
          color: var(--color-text-tertiary);
          line-height: 1.6;
          padding: 12px 14px;
          border-radius: 8px;
          background: var(--color-background-secondary);
          border: 1px solid var(--color-border-tertiary);
        }
      `}</style>

      <div className="sai-quota-backdrop">
        <div className="sai-quota-card">

          <div className="sai-quota-top">
            <div className="sai-quota-clock-ring">
              <Clock size={36} />
            </div>
            <div className="sai-quota-heading">Daily limit reached</div>
            <p className="sai-quota-sub">
              You've used all {quota.limit} free consultations for today.
              Your sessions will reset automatically.
            </p>
          </div>

          <hr className="sai-quota-divider" />

          {/* Live countdown */}
          <div className="sai-quota-timer-section">
            <div className="sai-quota-timer-label">
              <RotateCcw size={10} style={{display:"inline", marginRight:4}} />
              Resets in
            </div>
            <div className="sai-quota-countdown">{countdown}</div>
            <div className="sai-quota-reset-time">at {resetTime}</div>
          </div>

          <hr className="sai-quota-divider" />

          <div className="sai-quota-footer">
            {/* Session dots */}
            <div className="sai-quota-dots">
              {Array.from({ length: quota.limit }).map((_, i) => (
                <div
                  key={i}
                  className={`sai-quota-dot ${i < quota.sessionsUsed ? "used" : ""}`}
                />
              ))}
            </div>
            <div className="sai-quota-dots-label">
              {quota.sessionsUsed} of {quota.limit} sessions used today
            </div>

            <div className="sai-quota-note">
              Free accounts include {quota.limit} consultations per 24-hour window.
              The timer above shows exactly when your sessions reset.
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
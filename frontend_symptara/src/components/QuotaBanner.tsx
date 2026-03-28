import type { QuotaError } from "@/hooks/useConsultation";

interface Props {
  quota: QuotaError;
  onDismiss: () => void;
}

function timeUntilReset(resetAt: string): string {
  const diff = new Date(resetAt).getTime() - Date.now();
  if (diff <= 0) return "shortly";
  const h = Math.floor(diff / 3_600_000);
  const m = Math.floor((diff % 3_600_000) / 60_000);
  if (h > 0) return `in ${h}h ${m}m`;
  return `in ${m}m`;
}

export function QuotaBanner({ quota, onDismiss }: Props) {
  const resetTime = new Date(quota.resetAt).toLocaleTimeString([], {
    hour:   "2-digit",
    minute: "2-digit",
  });

  return (
    <>
      <style>{`
        @keyframes sai-slide-in {
          from { opacity: 0; transform: translateY(-8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .sai-quota-banner {
          animation: sai-slide-in 0.25s ease;
          display: flex;
          align-items: flex-start;
          gap: 14px;
          padding: 14px 16px;
          border-radius: 6px;
          background: rgba(239, 159, 39, 0.07);
          border: 1px solid rgba(239, 159, 39, 0.25);
          margin-bottom: 12px;
        }
        .sai-quota-icon {
          flex-shrink: 0;
          width: 18px;
          height: 18px;
          margin-top: 1px;
          color: #EF9F27;
        }
        .sai-quota-body {
          flex: 1;
          min-width: 0;
        }
        .sai-quota-title {
          font-size: 13px;
          font-weight: 500;
          color: #EF9F27;
          margin-bottom: 3px;
        }
        .sai-quota-detail {
          font-size: 12px;
          color: rgba(239, 159, 39, 0.7);
          line-height: 1.5;
        }
        .sai-quota-dismiss {
          flex-shrink: 0;
          background: none;
          border: none;
          cursor: pointer;
          color: rgba(239, 159, 39, 0.5);
          padding: 0;
          line-height: 1;
          font-size: 16px;
          transition: color 0.15s;
        }
        .sai-quota-dismiss:hover {
          color: #EF9F27;
        }
        .sai-quota-pill {
          display: inline-block;
          font-size: 10px;
          font-weight: 600;
          padding: 2px 8px;
          border-radius: 20px;
          background: rgba(239, 159, 39, 0.12);
          border: 1px solid rgba(239, 159, 39, 0.25);
          color: #EF9F27;
          margin-top: 6px;
        }
      `}</style>

      <div className="sai-quota-banner" role="alert">
        {/* Warning icon */}
        <svg className="sai-quota-icon" viewBox="0 0 20 20" fill="none">
          <path
            d="M10 2L18.66 17H1.34L10 2Z"
            stroke="currentColor" strokeWidth="1.4"
            strokeLinejoin="round" fill="none"
          />
          <line x1="10" y1="8" x2="10" y2="12" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
          <circle cx="10" cy="14.5" r="0.8" fill="currentColor"/>
        </svg>

        <div className="sai-quota-body">
          <div className="sai-quota-title">Daily session limit reached</div>
          <div className="sai-quota-detail">
            You've used all {quota.limit} free consultations for today.
            Your quota resets at <strong>{resetTime}</strong> ({timeUntilReset(quota.resetAt)}).
          </div>
          <div className="sai-quota-pill">
            {quota.sessionsUsed} / {quota.limit} sessions used
          </div>
        </div>

        <button
          className="sai-quota-dismiss"
          onClick={onDismiss}
          aria-label="Dismiss"
        >
          ×
        </button>
      </div>
    </>
  );
}
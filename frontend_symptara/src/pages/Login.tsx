import { useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";

type Mode = "signin" | "signup";

export default function Login() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const resetForm = () => {
    setError("");
    setInfo("");
    setEmail("");
    setPassword("");
    setConfirmPassword("");
  };

  const switchMode = (m: Mode) => {
    resetForm();
    setMode(m);
  };

  const handleSubmit = async () => {
    setError("");
    setInfo("");

    if (!email || !password) {
      setError("Please fill in all fields.");
      return;
    }

    if (mode === "signup") {
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }
      if (password.length < 8) {
        setError("Password must be at least 8 characters.");
        return;
      }
    }

    setLoading(true);
    try {
      if (mode === "signin") {
        const { error: err } = await signIn(email, password);
        if (err) throw err;
      } else {
        const { error: err } = await signUp(email, password);
        if (err) throw err;
        setInfo(
          "Account created. Please check your email to confirm your address, then sign in."
        );
        switchMode("signin");
        setLoading(false);
        return;
      }
    } catch (err: any) {
      setError(err?.message ?? "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSubmit();
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Mono:wght@300;400;500&display=swap');

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        .sai-root {
          min-height: 100vh;
          background: #080c10;
          display: flex;
          align-items: center;
          justify-content: center;
          font-family: 'DM Mono', monospace;
          position: relative;
          overflow: hidden;
        }

        /* Subtle grid background */
        .sai-root::before {
          content: '';
          position: absolute;
          inset: 0;
          background-image:
            linear-gradient(rgba(32, 210, 150, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(32, 210, 150, 0.03) 1px, transparent 1px);
          background-size: 48px 48px;
          pointer-events: none;
        }

        /* Radial glow behind card */
        .sai-glow {
          position: absolute;
          width: 600px;
          height: 600px;
          border-radius: 50%;
          background: radial-gradient(circle, rgba(32, 210, 150, 0.06) 0%, transparent 70%);
          pointer-events: none;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
        }

        .sai-card {
          position: relative;
          width: 420px;
          background: #0d1117;
          border: 1px solid rgba(32, 210, 150, 0.15);
          border-radius: 2px;
          padding: 48px 44px 44px;
          opacity: 0;
          transform: translateY(16px);
          transition: opacity 0.5s ease, transform 0.5s ease;
        }

        .sai-card.mounted {
          opacity: 1;
          transform: translateY(0);
        }

        /* Top accent line */
        .sai-card::before {
          content: '';
          position: absolute;
          top: 0; left: 0; right: 0;
          height: 1px;
          background: linear-gradient(90deg, transparent, rgba(32, 210, 150, 0.6), transparent);
        }

        .sai-logo-row {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 36px;
        }

        .sai-logo-mark {
          width: 32px;
          height: 32px;
          border: 1px solid rgba(32, 210, 150, 0.4);
          border-radius: 2px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }

        .sai-logo-mark svg {
          width: 16px;
          height: 16px;
        }

        .sai-logo-name {
          font-family: 'Instrument Serif', serif;
          font-size: 20px;
          color: #e8edf2;
          letter-spacing: 0.01em;
        }

        .sai-logo-name em {
          color: #20d296;
          font-style: italic;
        }

        .sai-heading {
          font-family: 'Instrument Serif', serif;
          font-size: 26px;
          color: #e8edf2;
          font-weight: 400;
          margin-bottom: 6px;
          line-height: 1.2;
        }

        .sai-subheading {
          font-size: 11px;
          color: rgba(160, 180, 170, 0.6);
          letter-spacing: 0.08em;
          text-transform: uppercase;
          margin-bottom: 36px;
        }

        /* Tab switcher */
        .sai-tabs {
          display: flex;
          border-bottom: 1px solid rgba(32, 210, 150, 0.1);
          margin-bottom: 32px;
        }

        .sai-tab {
          flex: 1;
          background: none;
          border: none;
          cursor: pointer;
          font-family: 'DM Mono', monospace;
          font-size: 11px;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          padding: 10px 0;
          color: rgba(160, 180, 170, 0.45);
          position: relative;
          transition: color 0.2s;
        }

        .sai-tab::after {
          content: '';
          position: absolute;
          bottom: -1px; left: 0; right: 0;
          height: 1px;
          background: #20d296;
          transform: scaleX(0);
          transition: transform 0.2s ease;
        }

        .sai-tab.active {
          color: #20d296;
        }

        .sai-tab.active::after {
          transform: scaleX(1);
        }

        .sai-tab:hover:not(.active) {
          color: rgba(160, 180, 170, 0.7);
        }

        /* Fields */
        .sai-field {
          margin-bottom: 18px;
        }

        .sai-label {
          display: block;
          font-size: 10px;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: rgba(160, 180, 170, 0.5);
          margin-bottom: 8px;
        }

        .sai-input {
          width: 100%;
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(32, 210, 150, 0.12);
          border-radius: 2px;
          padding: 11px 14px;
          font-family: 'DM Mono', monospace;
          font-size: 13px;
          color: #c8d8d0;
          outline: none;
          transition: border-color 0.2s, background 0.2s;
          letter-spacing: 0.02em;
        }

        .sai-input::placeholder {
          color: rgba(160, 180, 170, 0.2);
        }

        .sai-input:focus {
          border-color: rgba(32, 210, 150, 0.4);
          background: rgba(32, 210, 150, 0.03);
        }

        /* Error / info banners */
        .sai-banner {
          border-radius: 2px;
          padding: 10px 14px;
          font-size: 12px;
          line-height: 1.5;
          margin-bottom: 20px;
          letter-spacing: 0.01em;
        }

        .sai-banner.error {
          background: rgba(220, 60, 60, 0.08);
          border: 1px solid rgba(220, 60, 60, 0.2);
          color: #e88080;
        }

        .sai-banner.info {
          background: rgba(32, 210, 150, 0.06);
          border: 1px solid rgba(32, 210, 150, 0.2);
          color: #20d296;
        }

        /* Submit button */
        .sai-btn {
          width: 100%;
          padding: 13px;
          background: transparent;
          border: 1px solid rgba(32, 210, 150, 0.35);
          border-radius: 2px;
          font-family: 'DM Mono', monospace;
          font-size: 11px;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: #20d296;
          cursor: pointer;
          position: relative;
          overflow: hidden;
          transition: border-color 0.2s, color 0.2s, background 0.2s;
          margin-top: 8px;
        }

        .sai-btn::before {
          content: '';
          position: absolute;
          inset: 0;
          background: rgba(32, 210, 150, 0.07);
          transform: translateX(-100%);
          transition: transform 0.3s ease;
        }

        .sai-btn:hover:not(:disabled)::before {
          transform: translateX(0);
        }

        .sai-btn:hover:not(:disabled) {
          border-color: rgba(32, 210, 150, 0.65);
          color: #4de8b0;
        }

        .sai-btn:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }

        /* Spinner inside button */
        .sai-spinner {
          display: inline-block;
          width: 12px;
          height: 12px;
          border: 1px solid rgba(32, 210, 150, 0.3);
          border-top-color: #20d296;
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
          vertical-align: middle;
          margin-right: 8px;
        }

        @keyframes spin { to { transform: rotate(360deg); } }

        /* Session quota notice */
        .sai-quota-note {
          margin-top: 28px;
          padding-top: 20px;
          border-top: 1px solid rgba(32, 210, 150, 0.07);
          display: flex;
          gap: 10px;
          align-items: flex-start;
        }

        .sai-quota-dot {
          width: 4px;
          height: 4px;
          border-radius: 50%;
          background: rgba(32, 210, 150, 0.4);
          flex-shrink: 0;
          margin-top: 5px;
        }

        .sai-quota-text {
          font-size: 11px;
          color: rgba(160, 180, 170, 0.35);
          line-height: 1.6;
          letter-spacing: 0.02em;
        }

        /* Disclaimer */
        .sai-disclaimer {
          margin-top: 32px;
          font-size: 10px;
          color: rgba(160, 180, 170, 0.25);
          line-height: 1.7;
          letter-spacing: 0.02em;
          text-align: center;
        }

        @media (max-width: 480px) {
          .sai-card { width: 100%; min-height: 100vh; border-radius: 0; border-left: none; border-right: none; padding: 48px 28px 40px; }
          .sai-root { align-items: flex-start; }
        }
      `}</style>

      <div className="sai-root">
        <div className="sai-glow" />

        <div className={`sai-card ${mounted ? "mounted" : ""}`}>
          {/* Logo */}
          <div className="sai-logo-row">
            <div className="sai-logo-mark">
              <svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M8 1L8 15M1 8L15 8" stroke="#20d296" strokeWidth="1.2" strokeLinecap="round"/>
                <circle cx="8" cy="8" r="3.5" stroke="#20d296" strokeWidth="0.8" opacity="0.5"/>
              </svg>
            </div>
            <span className="sai-logo-name">
              Symptara<em>AI</em>
            </span>
          </div>

          {/* Heading */}
          <h1 className="sai-heading">
            {mode === "signin" ? "Welcome back." : "Create an account."}
          </h1>
          <p className="sai-subheading">
            {mode === "signin" ? "Sign in to your account" : "Free · 5 consultations per day"}
          </p>

          {/* Tabs */}
          <div className="sai-tabs">
            <button
              className={`sai-tab ${mode === "signin" ? "active" : ""}`}
              onClick={() => switchMode("signin")}
            >
              Sign in
            </button>
            <button
              className={`sai-tab ${mode === "signup" ? "active" : ""}`}
              onClick={() => switchMode("signup")}
            >
              Sign up
            </button>
          </div>

          {/* Banners */}
          {error && <div className="sai-banner error">{error}</div>}
          {info  && <div className="sai-banner info">{info}</div>}

          {/* Fields */}
          <div className="sai-field">
            <label className="sai-label">Email address</label>
            <input
              className="sai-input"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              onKeyDown={handleKeyDown}
              autoComplete="email"
            />
          </div>

          <div className="sai-field">
            <label className="sai-label">Password</label>
            <input
              className="sai-input"
              type="password"
              placeholder={mode === "signup" ? "Min. 8 characters" : "••••••••"}
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={handleKeyDown}
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
            />
          </div>

          {mode === "signup" && (
            <div className="sai-field">
              <label className="sai-label">Confirm password</label>
              <input
                className="sai-input"
                type="password"
                placeholder="Repeat password"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                onKeyDown={handleKeyDown}
                autoComplete="new-password"
              />
            </div>
          )}

          {/* Submit */}
          <button
            className="sai-btn"
            onClick={handleSubmit}
            disabled={loading}
          >
            {loading && <span className="sai-spinner" />}
            {loading
              ? mode === "signin" ? "Signing in..." : "Creating account..."
              : mode === "signin" ? "Sign in" : "Create account"}
          </button>

          {/* Quota note */}
          <div className="sai-quota-note">
            <div className="sai-quota-dot" />
            <p className="sai-quota-text">
              Free accounts include 5 consultation sessions per 24-hour window.
              Sessions reset automatically.
            </p>
          </div>

          {/* Medical disclaimer */}
          <p className="sai-disclaimer">
            SymptaraAI is an AI-assisted triage tool and does not replace
            the advice of a licensed healthcare professional. In an emergency,
            call 911 immediately.
          </p>
        </div>
      </div>
    </>
  );
}
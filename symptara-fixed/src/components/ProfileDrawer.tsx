/**
 * ProfileDrawer.tsx
 * =================
 * Exports TWO drawers:
 *
 *   <IdentityDrawer />    — User login/contact info (Profile button)
 *                           Name, Email, Phone, Address, Other Info
 *                           Stored in localStorage — not sent to backend
 *
 *   <MedicalInfoDrawer /> — Medical history (Medical Info button)
 *                           Age, Sex, Blood Type, Allergies, Conditions,
 *                           Medications, Past Surgeries
 *                           Sent to backend via POST /profile/
 */

import { useState, useEffect, useCallback } from "react";
import { X, Plus, User, Stethoscope } from "lucide-react";
import type { UserProfile, UserIdentity } from "@/types/consultation";
import { api } from "@/lib/api";

const USER_ID = "00000000-0000-0000-0000-000000000001";
const BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];
const IDENTITY_KEY = "symptara_user_identity";

// ── Shared sub-components ─────────────────────────────────────────────────────

const Field = ({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) => (
  <div>
    <label className="mb-1 block text-xs font-medium text-muted-foreground">
      {label}
    </label>
    {children}
  </div>
);

const TextInput = ({
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) => (
  <input
    type={type}
    value={value}
    onChange={(e) => onChange(e.target.value)}
    placeholder={placeholder}
    className="w-full rounded-md border border-border bg-muted/50 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none transition-colors"
  />
);

const TagInput = ({
  label,
  values,
  onChange,
}: {
  label: string;
  values: string[];
  onChange: (v: string[]) => void;
}) => {
  const [input, setInput] = useState("");

  const add = () => {
    const trimmed = input.trim();
    if (trimmed && !values.includes(trimmed)) {
      onChange([...values, trimmed]);
      setInput("");
    }
  };

  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-muted-foreground">
        {label}
      </label>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {values.map((v, i) => (
          <span
            key={i}
            className="inline-flex items-center gap-1 rounded-md bg-primary/10 border border-primary/20 px-2 py-0.5 text-xs text-primary"
          >
            {v}
            <button
              onClick={() => onChange(values.filter((_, j) => j !== i))}
              className="hover:text-destructive transition-colors"
            >
              <X size={10} />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-1">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())}
          placeholder={`Add ${label.toLowerCase()}...`}
          className="flex-1 rounded-md border border-border bg-muted/50 px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none"
        />
        <button
          onClick={add}
          className="rounded-md border border-border bg-muted/50 px-2 text-muted-foreground hover:text-foreground transition-colors"
        >
          <Plus size={14} />
        </button>
      </div>
    </div>
  );
};

const DrawerShell = ({
  open,
  onClose,
  title,
  icon,
  accentClass,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  icon: React.ReactNode;
  accentClass: string;
  children: React.ReactNode;
}) => {
  if (!open) return null;
  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="fixed right-0 top-0 z-50 h-full w-full max-w-md overflow-y-auto border-l border-border bg-panel shadow-2xl">
        <div className={`flex items-center justify-between border-b border-border p-4 ${accentClass}`}>
          <div className="flex items-center gap-2">
            {icon}
            <h2 className="font-display text-lg font-semibold text-foreground">
              {title}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:text-foreground transition-colors"
          >
            <X size={20} />
          </button>
        </div>
        <div className="space-y-5 p-4">{children}</div>
      </div>
    </>
  );
};

// ── Identity Drawer (Profile button) ─────────────────────────────────────────
// Stores to localStorage only — this is contact/identity info, not medical.

interface IdentityDrawerProps {
  open:    boolean;
  onClose: () => void;
}

export const IdentityDrawer = ({ open, onClose }: IdentityDrawerProps) => {
  const [identity, setIdentity] = useState<UserIdentity>({
    user_id:    USER_ID,
    full_name:  "",
    email:      "",
    phone:      "",
    address:    "",
    other_info: "",
  });
  const [saved, setSaved] = useState(false);

  // Load from localStorage on open
  useEffect(() => {
    if (!open) return;
    try {
      const stored = localStorage.getItem(IDENTITY_KEY);
      if (stored) {
        setIdentity({ ...JSON.parse(stored), user_id: USER_ID });
      }
    } catch {}
  }, [open]);

  const save = useCallback(() => {
    try {
      localStorage.setItem(IDENTITY_KEY, JSON.stringify(identity));
      setSaved(true);
      setTimeout(() => {
        setSaved(false);
        onClose();
      }, 800);
    } catch {}
  }, [identity, onClose]);

  return (
    <DrawerShell
      open={open}
      onClose={onClose}
      title="Profile"
      icon={<User size={18} className="text-primary" />}
      accentClass="bg-primary/[0.03]"
    >
      <p className="text-xs text-muted-foreground -mt-2 pb-1 border-b border-border">
        Personal contact information. Stored locally on this device.
      </p>

      <Field label="Full Name">
        <TextInput
          value={identity.full_name || ""}
          onChange={(v) => setIdentity({ ...identity, full_name: v })}
          placeholder="John Doe"
        />
      </Field>

      <Field label="Email">
        <TextInput
          type="email"
          value={identity.email || ""}
          onChange={(v) => setIdentity({ ...identity, email: v })}
          placeholder="john@example.com"
        />
      </Field>

      <Field label="Phone">
        <TextInput
          type="tel"
          value={identity.phone || ""}
          onChange={(v) => setIdentity({ ...identity, phone: v })}
          placeholder="+1 (555) 000-0000"
        />
      </Field>

      <Field label="Address">
        <textarea
          value={identity.address || ""}
          onChange={(e) => setIdentity({ ...identity, address: e.target.value })}
          placeholder="123 Main St, Dallas, TX 75001"
          rows={2}
          className="w-full resize-none rounded-md border border-border bg-muted/50 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none transition-colors"
        />
      </Field>

      <Field label="Any Other Info">
        <textarea
          value={identity.other_info || ""}
          onChange={(e) => setIdentity({ ...identity, other_info: e.target.value })}
          placeholder="Emergency contact, insurance info, preferred language..."
          rows={3}
          className="w-full resize-none rounded-md border border-border bg-muted/50 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none transition-colors"
        />
      </Field>

      <button
        onClick={save}
        className="w-full rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground transition-all hover:brightness-110"
      >
        {saved ? "✓ Saved" : "Save Profile"}
      </button>
    </DrawerShell>
  );
};

// ── Medical Info Drawer (Medical Info button) ─────────────────────────────────
// Sends to backend via POST /profile/ — used for anti-hallucination in triage.

interface MedicalInfoDrawerProps {
  open:    boolean;
  onClose: () => void;
}

export const MedicalInfoDrawer = ({ open, onClose }: MedicalInfoDrawerProps) => {
  const [profile, setProfile] = useState<UserProfile>({
    user_id:              USER_ID,
    allergies:            [],
    chronic_conditions:   [],
    current_medications:  [],
    past_surgeries:       [],
  });
  const [saving, setSaving] = useState(false);

  // Load from backend on open
  useEffect(() => {
    if (!open) return;
    api.getProfile(USER_ID).then((data) => {
      if (data) setProfile({ ...data, user_id: USER_ID });
    }).catch(() => {});
  }, [open]);

  const save = useCallback(async () => {
    setSaving(true);
    try {
      await api.saveProfile(profile as unknown as Record<string, unknown>);
      onClose();
    } catch {}
    setSaving(false);
  }, [profile, onClose]);

  return (
    <DrawerShell
      open={open}
      onClose={onClose}
      title="Medical Info"
      icon={<Stethoscope size={18} className="text-secondary" />}
      accentClass="bg-secondary/[0.03]"
    >
      <p className="text-xs text-muted-foreground -mt-2 pb-1 border-b border-border">
        Medical history used to improve triage accuracy. Sent to the backend.
      </p>

      <Field label="Age">
        <input
          type="number"
          value={profile.age || ""}
          onChange={(e) =>
            setProfile({ ...profile, age: parseInt(e.target.value) || undefined })
          }
          className="w-full rounded-md border border-border bg-muted/50 px-3 py-2 text-sm text-foreground focus:border-primary/50 focus:outline-none"
        />
      </Field>

      <Field label="Sex">
        <select
          value={profile.sex || ""}
          onChange={(e) => setProfile({ ...profile, sex: e.target.value })}
          className="w-full rounded-md border border-border bg-muted/50 px-3 py-2 text-sm text-foreground focus:border-primary/50 focus:outline-none"
        >
          <option value="">Select...</option>
          <option value="Male">Male</option>
          <option value="Female">Female</option>
          <option value="Other">Other</option>
        </select>
      </Field>

      <Field label="Blood Type">
        <select
          value={profile.blood_type || ""}
          onChange={(e) => setProfile({ ...profile, blood_type: e.target.value })}
          className="w-full rounded-md border border-border bg-muted/50 px-3 py-2 text-sm text-foreground focus:border-primary/50 focus:outline-none"
        >
          <option value="">Select...</option>
          {BLOOD_TYPES.map((bt) => (
            <option key={bt} value={bt}>{bt}</option>
          ))}
        </select>
      </Field>

      <TagInput
        label="Allergies"
        values={profile.allergies || []}
        onChange={(v) => setProfile({ ...profile, allergies: v })}
      />
      <TagInput
        label="Chronic Conditions"
        values={profile.chronic_conditions || []}
        onChange={(v) => setProfile({ ...profile, chronic_conditions: v })}
      />
      <TagInput
        label="Current Medications"
        values={profile.current_medications || []}
        onChange={(v) => setProfile({ ...profile, current_medications: v })}
      />
      <TagInput
        label="Past Surgeries"
        values={profile.past_surgeries || []}
        onChange={(v) => setProfile({ ...profile, past_surgeries: v })}
      />

      <button
        onClick={save}
        disabled={saving}
        className="w-full rounded-lg bg-secondary py-2.5 text-sm font-medium text-secondary-foreground transition-all hover:brightness-110 disabled:opacity-50"
      >
        {saving ? "Saving..." : "Save Medical Info"}
      </button>
    </DrawerShell>
  );
};

// ── Default export for backwards compatibility ────────────────────────────────
export default MedicalInfoDrawer;

/**
 * UserAccountDropdown.tsx
 * =======================
 * Proper user account dropdown in the header.
 * Shows user's name from localStorage identity, with dropdown menu.
 *
 * For MVP (no auth backend):
 * - Displays stored name or "Guest User"
 * - Shows email if set
 * - "Edit Profile" opens the IdentityDrawer
 * - "Sign Out" clears localStorage identity + resets session
 */

import { useState, useEffect, useRef } from "react";
import { User, ChevronDown, LogOut, UserCog, Shield } from "lucide-react";

const IDENTITY_KEY = "symptara_user_identity";

interface UserAccountDropdownProps {
  onEditProfile: () => void;
  onSignOut:     () => void;
}

export const UserAccountDropdown = ({
  onEditProfile,
  onSignOut,
}: UserAccountDropdownProps) => {
  const [open,      setOpen]      = useState(false);
  const [identity,  setIdentity]  = useState<any>(null);
  const dropdownRef               = useRef<HTMLDivElement>(null);

  // Load identity from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(IDENTITY_KEY);
      if (stored) setIdentity(JSON.parse(stored));
    } catch {}
  }, [open]); // re-read on each open in case it was updated

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const displayName  = identity?.full_name?.trim() || "Guest User";
  const displayEmail = identity?.email?.trim()     || null;
  const initials     = displayName
    .split(" ")
    .slice(0, 2)
    .map((w: string) => w[0]?.toUpperCase() || "")
    .join("");

  const handleEditProfile = () => {
    setOpen(false);
    onEditProfile();
  };

  const handleSignOut = () => {
    setOpen(false);
    onSignOut();
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        {/* Avatar circle */}
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/20 text-[10px] font-bold text-primary">
          {initials || <User size={12} />}
        </div>
        <span className="hidden sm:inline max-w-[100px] truncate">
          {displayName}
        </span>
        <ChevronDown
          size={12}
          className={`transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {/* Dropdown menu */}
      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-56 overflow-hidden rounded-xl border border-border bg-card shadow-2xl">
          {/* User info header */}
          <div className="border-b border-border bg-muted/20 px-4 py-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/20 text-sm font-bold text-primary">
                {initials || <User size={16} />}
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-foreground">
                  {displayName}
                </p>
                {displayEmail && (
                  <p className="truncate text-[11px] text-muted-foreground">
                    {displayEmail}
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Menu items */}
          <div className="py-1">
            <button
              onClick={handleEditProfile}
              className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-foreground transition-colors hover:bg-muted/50"
            >
              <UserCog size={14} className="text-muted-foreground" />
              Edit Profile
            </button>

            <div className="my-1 border-t border-border/50" />

            {/* Privacy note */}
            <div className="flex items-center gap-2 px-4 py-2">
              <Shield size={11} className="text-muted-foreground shrink-0" />
              <span className="text-[10px] text-muted-foreground leading-tight">
                Profile data stored locally on this device
              </span>
            </div>

            <div className="my-1 border-t border-border/50" />

            <button
              onClick={handleSignOut}
              className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-destructive transition-colors hover:bg-destructive/10"
            >
              <LogOut size={14} />
              Sign Out
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserAccountDropdown;

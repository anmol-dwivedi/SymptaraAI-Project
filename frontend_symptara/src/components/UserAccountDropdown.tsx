/**
 * UserAccountDropdown.tsx
 * =======================
 * Reads display name and email from Supabase auth session.
 * Shows "Admin" badge for users in the admin_users table.
 * Falls back to email prefix if no full name is set.
 */

import { useState, useEffect, useRef } from "react";
import { User, ChevronDown, LogOut, UserCog, Shield, Crown } from "lucide-react";
import { supabase } from "@/lib/supabase";

interface UserAccountDropdownProps {
  onEditProfile: () => void;
  onSignOut:     () => void;
}

export const UserAccountDropdown = ({
  onEditProfile,
  onSignOut,
}: UserAccountDropdownProps) => {
  const [open,      setOpen]      = useState(false);
  const [email,     setEmail]     = useState<string | null>(null);
  const [userId,    setUserId]    = useState<string | null>(null);
  const [isAdmin,   setIsAdmin]   = useState(false);
  const dropdownRef               = useRef<HTMLDivElement>(null);

  // Load user from Supabase session
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const user = data.session?.user;
      if (!user) return;
      setEmail(user.email ?? null);
      setUserId(user.id);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setEmail(session?.user?.email ?? null);
      setUserId(session?.user?.id ?? null);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  // Check admin status whenever userId changes
  useEffect(() => {
    if (!userId) { setIsAdmin(false); return; }
    supabase
      .from("admin_users")
      .select("user_id")
      .eq("user_id", userId)
      .then(({ data }) => setIsAdmin((data?.length ?? 0) > 0));
  }, [userId]);

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

  // Display name: "Admin" for admin users, email prefix for everyone else
  const emailPrefix  = email?.split("@")[0] ?? "Guest User";
  const displayName  = isAdmin ? "Admin" : emailPrefix;
  const initials     = displayName
    .split(/[\s._-]/)
    .slice(0, 2)
    .map((w: string) => w[0]?.toUpperCase() || "")
    .join("") || "GU";

  const handleEditProfile = () => { setOpen(false); onEditProfile(); };
  const handleSignOut     = () => { setOpen(false); onSignOut(); };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        {/* Avatar circle */}
        <div className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold ${
          isAdmin ? "bg-amber-500/20 text-amber-500" : "bg-primary/20 text-primary"
        }`}>
          {isAdmin ? <Crown size={11} /> : (initials || <User size={12} />)}
        </div>

        <span className="hidden sm:inline max-w-[100px] truncate">
          {displayName}
        </span>

        {/* Admin badge */}
        {isAdmin && (
          <span className="hidden sm:inline text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-500 border border-amber-500/25">
            ADMIN
          </span>
        )}

        <ChevronDown
          size={12}
          className={`transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {/* Dropdown menu */}
      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-60 overflow-hidden rounded-xl border border-border bg-card shadow-2xl">

          {/* User info header */}
          <div className={`border-b border-border px-4 py-3 ${
            isAdmin ? "bg-amber-500/5" : "bg-muted/20"
          }`}>
            <div className="flex items-center gap-3">
              <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold ${
                isAdmin ? "bg-amber-500/20 text-amber-500" : "bg-primary/20 text-primary"
              }`}>
                {isAdmin ? <Crown size={16} /> : (initials || <User size={16} />)}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p className="truncate text-sm font-semibold text-foreground">
                    {displayName}
                  </p>
                  {isAdmin && (
                    <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-500 border border-amber-500/25 shrink-0">
                      ADMIN
                    </span>
                  )}
                </div>
                {email && (
                  <p className="truncate text-[11px] text-muted-foreground">
                    {email}
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

            <div className="flex items-center gap-2 px-4 py-2">
              <Shield size={11} className="text-muted-foreground shrink-0" />
              <span className="text-[10px] text-muted-foreground leading-tight">
                {isAdmin
                  ? "Unlimited sessions · Admin access"
                  : "5 consultations per 24-hour window"}
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
/**
 * Settings overview.
 *
 * One row per area, each showing the value you would see if you opened it, and
 * a screen behind the ones that have real behaviour today. Areas with nothing
 * behind them yet say so instead of showing a control that does nothing.
 *
 * The user, allergy and preference fetches all run here rather than inside the
 * screens, because an overview row has to show a real value before you open
 * anything.
 */
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

import {
  ApiError,
  createAllergy,
  deleteAllergy,
  getCurrentUser,
  listAllergies,
  readPreferences,
  updatePreferences,
} from "../api/client";
import type {
  AllergyCreateRequest,
  AllergyResponse,
  PreferenceResponse,
  PreferenceUpdateRequest,
  UserResponse,
} from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { clearToken } from "../auth/token";
import { formatRisk } from "../utils/format";
import { DevLlmSettingsCard } from "./DevLlmSettingsCard";
import {
  ComingSoonGroup,
  ComingSoonRow,
  SettingsCard,
  SettingsGroup,
  SettingsRow,
  type SettingsScreenId,
} from "./settings/SettingsRows";
import {
  HealthScreen,
  LocationScreen,
  NotificationsScreen,
  ProfileScreen,
  SettingsSubScreen,
} from "./settings/Screens";

const SCREEN_TITLE: Record<SettingsScreenId, string> = {
  profile: "Profile",
  health: "Health",
  location: "Location",
  notifications: "Notifications",
};

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function initialsFor(email: string): string {
  const local = email.split("@")[0] ?? "";
  return (local.slice(0, 2) || "AC").toUpperCase();
}

function locationValue(user: UserResponse): string {
  if (user.latitude === null || user.longitude === null) return "Not set";
  return `${user.latitude.toFixed(4)}, ${user.longitude.toFixed(4)}`;
}

function allergyValue(allergies: AllergyResponse[] | null, failed: boolean): string {
  if (allergies === null) return failed ? "Could not load" : "Loading…";
  if (allergies.length === 0) return "Nothing saved yet";
  return allergies.length === 1 ? "1 saved" : `${allergies.length} saved`;
}

function categoriesOn(prefs: PreferenceResponse): string {
  const on = [prefs.alert_pollen, prefs.alert_air_quality, prefs.alert_weather].filter(Boolean)
    .length;
  return on === 0 ? "All categories off" : `${on} of 3 on`;
}

function prefValue(
  prefs: PreferenceResponse | null,
  failed: boolean,
  live: (prefs: PreferenceResponse) => string,
): string {
  if (prefs !== null) return live(prefs);
  return failed ? "Could not load" : "Loading…";
}

export function SettingsPage() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [allergies, setAllergies] = useState<AllergyResponse[] | null>(null);
  const [allergyLoadError, setAllergyLoadError] = useState<string | null>(null);
  const [prefs, setPrefs] = useState<PreferenceResponse | null>(null);
  const [prefsLoadError, setPrefsLoadError] = useState<string | null>(null);
  const [screen, setScreen] = useState<SettingsScreenId | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const loadAllergies = useCallback(async () => {
    setAllergyLoadError(null);
    try {
      setAllergies(await listAllergies());
    } catch (e) {
      setAllergyLoadError(errorText(e, "Could not load your allergies."));
    }
  }, []);

  const loadPrefs = useCallback(async () => {
    setPrefsLoadError(null);
    try {
      setPrefs(await readPreferences());
    } catch (e) {
      setPrefsLoadError(errorText(e, "Could not load your notification preferences."));
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    getCurrentUser()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch((e) => {
        if (cancelled) return;
        // An expired or rejected token must not strand the user on a wall with
        // only "Back to today". The token is dead, so drop it and send them to
        // sign in again.
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
          clearToken();
          navigate("/login", { replace: true });
          return;
        }
        setLoadError(errorText(e, "Could not load your settings."));
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  useEffect(() => {
    void loadAllergies();
    void loadPrefs();
  }, [loadAllergies, loadPrefs]);

  async function addAllergy(body: AllergyCreateRequest) {
    const created = await createAllergy(body);
    setAllergies((prev) => (prev ? [...prev, created] : prev));
  }

  async function removeAllergy(id: number) {
    await deleteAllergy(id);
    setAllergies((prev) => (prev ? prev.filter((a) => a.id !== id) : prev));
  }

  async function changePrefs(body: PreferenceUpdateRequest) {
    setPrefs(await updatePreferences(body));
  }

  function renderScreen(id: SettingsScreenId, user: UserResponse) {
    switch (id) {
      case "profile":
        return <ProfileScreen user={user} />;
      case "health":
        return (
          <HealthScreen
            allergies={allergies}
            loadError={allergyLoadError}
            onRetry={() => void loadAllergies()}
            onAdd={addAllergy}
            onRemove={removeAllergy}
          />
        );
      case "location":
        return <LocationScreen user={user} onSaved={setUser} />;
      case "notifications":
        return (
          <NotificationsScreen
            prefs={prefs}
            loadError={prefsLoadError}
            onRetry={() => void loadPrefs()}
            onChange={changePrefs}
          />
        );
    }
  }

  if (loadError) {
    return (
      <div className="stage flex flex-col gap-4">
        <Alert variant="destructive">
          <AlertTitle>Could not load your settings</AlertTitle>
          <AlertDescription>{loadError}</AlertDescription>
        </Alert>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate("/today")}>
            Back to today
          </Button>
          <Button variant="outline" onClick={() => navigate("/login", { replace: true })}>
            Sign in again
          </Button>
        </div>
      </div>
    );
  }

  if (user === null) {
    return (
      <div className="stage flex flex-col gap-4" aria-hidden="true">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-36 w-full" />
        <Skeleton className="h-36 w-full" />
      </div>
    );
  }

  if (screen !== null) {
    return (
      <div className="stage flex flex-col gap-4">
        <SettingsSubScreen title={SCREEN_TITLE[screen]} onBack={() => setScreen(null)}>
          {renderScreen(screen, user)}
        </SettingsSubScreen>
      </div>
    );
  }

  return (
    <div className="stage flex flex-col gap-4">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <Avatar>
              <AvatarFallback>{initialsFor(user.email)}</AvatarFallback>
            </Avatar>
            <CardTitle>Settings</CardTitle>
          </div>
          <CardAction>
            <Button variant="ghost" onClick={() => navigate("/today")}>
              Done
            </Button>
          </CardAction>
        </CardHeader>
      </Card>

      <SettingsCard>
        <SettingsRow label="Profile" value={user.email} onSelect={() => setScreen("profile")} />
      </SettingsCard>

      <SettingsGroup title="Health">
        <SettingsRow
          label="Allergies"
          value={allergyValue(allergies, allergyLoadError !== null)}
          onSelect={() => setScreen("health")}
        />
        <ComingSoonRow label="Medications" />
      </SettingsGroup>

      <ComingSoonGroup title="Emergency" rows={["Emergency contact", "Medical card"]} />

      <SettingsCard>
        <SettingsRow
          label="Location"
          value={locationValue(user)}
          onSelect={() => setScreen("location")}
        />
      </SettingsCard>

      <SettingsGroup title="Notifications">
        <SettingsRow
          label="Categories"
          value={prefValue(prefs, prefsLoadError !== null, categoriesOn)}
          onSelect={() => setScreen("notifications")}
        />
        <SettingsRow
          label="Minimum risk"
          value={prefValue(prefs, prefsLoadError !== null, (p) => formatRisk(p.min_risk_level))}
          onSelect={() => setScreen("notifications")}
        />
        <ComingSoonRow label="Quiet hours" />
        <ComingSoonRow label="Notification permission" />
      </SettingsGroup>

      <ComingSoonGroup
        title="Chat and language"
        rows={["Agent language", "Voice input", "Keep chat history"]}
      />

      <ComingSoonGroup
        title="Accessibility"
        rows={["Text size", "Reduce motion", "High contrast"]}
      />

      <ComingSoonGroup
        title="Privacy and data"
        rows={["What is stored", "Export my data", "Delete my data"]}
      />

      <section aria-label="Advanced" className="flex flex-col gap-2">
        <h2 className="text-xs font-bold tracking-[0.12em] text-muted-foreground uppercase">
          Advanced
        </h2>
        <div className="overflow-hidden rounded-xl bg-card ring-1 ring-foreground/10">
          <button
            type="button"
            aria-expanded={advancedOpen}
            aria-controls="settings-advanced"
            onClick={() => setAdvancedOpen((open) => !open)}
            className="flex min-h-11 w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
          >
            <span className="flex min-w-0 flex-col">
              <span className="text-sm font-medium">Developer tools</span>
              <span className="text-xs text-muted-foreground">
                Local development only
              </span>
            </span>
            <ChevronRight
              aria-hidden
              className={`ml-auto size-4 shrink-0 text-muted-foreground ${advancedOpen ? "rotate-90" : ""}`}
            />
          </button>
          {advancedOpen ? (
            <div id="settings-advanced" className="flex flex-col gap-3 border-t border-border p-3">
              <div className="flex flex-col gap-0.5">
                <p className="text-sm font-medium">Diagnostics</p>
                <p className="text-xs text-muted-foreground">Not built yet.</p>
              </div>
              {/* Renders nothing unless the backend has DEV_SETTINGS_ENABLED=true. */}
              <DevLlmSettingsCard />
            </div>
          ) : null}
        </div>
      </section>

      <Separator />

      <div className="flex flex-col gap-2">
        <Button variant="destructive" className="min-h-11" onClick={logout}>
          Sign out
        </Button>
        <p className="text-xs text-muted-foreground">
          You need your email and password to sign back in.
        </p>
      </div>

      <Separator />

      <section aria-label="Danger zone" className="flex flex-col gap-2">
        <h2 className="text-xs font-bold tracking-[0.12em] text-muted-foreground uppercase">
          Danger zone
        </h2>
        <div className="flex flex-col gap-2 rounded-xl bg-card px-4 py-3 ring-1 ring-foreground/10">
          <p className="text-sm font-medium">Delete account</p>
          <p className="text-xs text-muted-foreground">
            Not built yet. The server has no delete endpoint, so this button is
            turned off rather than pretending to work.
          </p>
          <Button variant="destructive" className="min-h-11" disabled>
            Delete account
          </Button>
        </div>
      </section>
    </div>
  );
}
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
import { useNavigate, useSearchParams } from "react-router-dom";
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
import {
  readEmergencyContact,
  saveEmergencyContact,
  type EmergencyContact,
} from "../api/emergencyContact";
import { deleteMyAccount, exportMyData } from "../api/privacy";
import { useAuth } from "../auth/AuthContext";
import { useConsent } from "../auth/ConsentContext";
import { clearToken } from "../auth/token";
import { toast } from "sonner";
import { useTextSize } from "../prefs/textSize";
import { formatRisk } from "../utils/format";
import { DevLlmSettingsCard } from "./DevLlmSettingsCard";
import {
  ComingSoonGroup,
  ComingSoonRow,
  SettingsCard,
  SettingsGroup,
  SettingsRow,
} from "./settings/SettingsRows";
import { isSettingsScreenId, type SettingsScreenId } from "./settings/settingsScreenIds";
import {
  EmergencyContactScreen,
  DeleteDataScreen,
  ExportDataScreen,
  HealthScreen,
  LocationScreen,
  NotificationsScreen,
  PrivacyScreen,
  ProfileScreen,
  SettingsSubScreen,
  StoredDataScreen,
  TextSizeScreen,
} from "./settings/Screens";

const SCREEN_TITLE: Record<SettingsScreenId, string> = {
  profile: "Profile",
  health: "Health",
  location: "Location",
  notifications: "Notifications",
  textsize: "Text size",
  privacy: "Privacy and data",
  stored: "What is stored",
  export: "Export my data",
  delete: "Delete my data",
  emergency: "Emergency contact",
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

function consentValue(granted: boolean, withdrawnAt: string | null): string {
  if (granted) return "Agreed";
  if (withdrawnAt) return "Withdrawn";
  return "Not agreed yet";
}

function contactValue(contact: EmergencyContact | null, failed: boolean): string {
  if (contact === null) return failed ? "Could not load" : "Loading…";
  return contact.name ?? "Not set";
}

export function SettingsPage() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { consent, policy, granted, setGranted, refresh, status } = useConsent();
  // The consent context reads the policy next to the consent and keeps going
  // when the policy fails, so a missing policy with a ready consent state
  // means the policy call failed rather than that it was never asked for.
  const policyError =
    policy === null && status === "ready" ? "The policy could not be loaded." : null;
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [allergies, setAllergies] = useState<AllergyResponse[] | null>(null);
  const [allergyLoadError, setAllergyLoadError] = useState<string | null>(null);
  const [prefs, setPrefs] = useState<PreferenceResponse | null>(null);
  const [prefsLoadError, setPrefsLoadError] = useState<string | null>(null);
  const [contact, setContact] = useState<EmergencyContact | null>(null);
  const [contactLoadError, setContactLoadError] = useState<string | null>(null);
  // The open subscreen lives in the URL, so another screen can send the user
  // straight to it ("/settings?screen=location") and the back button works.
  const [params, setParams] = useSearchParams();
  const requested = params.get("screen");
  const screen: SettingsScreenId | null =
    requested !== null && isSettingsScreenId(requested) ? requested : null;
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const { step: textSize, setStep: setTextSize } = useTextSize();

  const openScreen = (id: SettingsScreenId) => setParams({ screen: id }, { replace: true });
  const closeScreen = () => setParams({}, { replace: true });

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

  const loadContact = useCallback(async () => {
    setContactLoadError(null);
    try {
      setContact(await readEmergencyContact());
    } catch (e) {
      setContactLoadError(errorText(e, "Could not load your emergency contact."));
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
    void loadContact();
  }, [loadAllergies, loadPrefs, loadContact]);

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

  async function changeContact(next: {
    name: string | null;
    phone: string | null;
    note: string | null;
  }) {
    setContact(await saveEmergencyContact(next));
  }

  async function runExport() {
    const name = await exportMyData();
    toast.success(`Your data was downloaded as ${name}.`);
  }

  async function runDelete() {
    await deleteMyAccount();
    // The account is gone, so the token is worthless and the local copy of it
    // should not stay on the device.
    clearToken();
    toast.success("Your account and your data were deleted.");
    navigate("/login", { replace: true });
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
      case "textsize":
        return <TextSizeScreen step={textSize} onChange={setTextSize} />;
      case "privacy":
        return (
          <PrivacyScreen
            granted={granted}
            grantedAt={consent?.granted_at ?? null}
            operator={policy?.operator ?? null}
            noticeItems={policy?.required_notice_items ?? []}
            onSetGranted={setGranted}
          />
        );
      case "emergency":
        return (
          <EmergencyContactScreen
            // The contact arrives after the screen opens, so the key gives the
            // form a fresh start once there is something to fill it with.
            key={contact === null ? "loading" : "loaded"}
            contact={contact}
            loadError={contactLoadError}
            onRetry={() => void loadContact()}
            onSave={changeContact}
          />
        );
      case "stored":
        return (
          <StoredDataScreen
            policy={policy}
            policyError={policyError}
            onRetry={() => void refresh()}
          />
        );
      case "export":
        return <ExportDataScreen onExport={runExport} />;
      case "delete":
        return <DeleteDataScreen onDelete={runDelete} />;
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
        <SettingsSubScreen title={SCREEN_TITLE[screen]} onBack={closeScreen}>
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
        <SettingsRow label="Profile" value={user.email} onSelect={() => openScreen("profile")} />
      </SettingsCard>

      <SettingsGroup title="Health">
        <SettingsRow
          label="Allergies"
          value={allergyValue(allergies, allergyLoadError !== null)}
          onSelect={() => openScreen("health")}
        />
        <ComingSoonRow label="Medications" />
      </SettingsGroup>

      <SettingsGroup title="Emergency">
        <SettingsRow
          label="Emergency contact"
          value={contactValue(contact, contactLoadError !== null)}
          onSelect={() => openScreen("emergency")}
        />
        <ComingSoonRow label="Medical card" />
      </SettingsGroup>

      <SettingsCard>
        <SettingsRow
          label="Location"
          value={locationValue(user)}
          onSelect={() => openScreen("location")}
        />
      </SettingsCard>

      <SettingsGroup title="Notifications">
        <SettingsRow
          label="Categories"
          value={prefValue(prefs, prefsLoadError !== null, categoriesOn)}
          onSelect={() => openScreen("notifications")}
        />
        <SettingsRow
          label="Minimum risk"
          value={prefValue(prefs, prefsLoadError !== null, (p) => formatRisk(p.min_risk_level))}
          onSelect={() => openScreen("notifications")}
        />
        <ComingSoonRow label="Quiet hours" />
        <ComingSoonRow label="Notification permission" />
      </SettingsGroup>

      <ComingSoonGroup
        title="Chat and language"
        rows={["Agent language", "Voice input", "Keep chat history"]}
      />

      <SettingsGroup title="Accessibility">
        <SettingsRow
          label="Text size"
          value={textSize.label}
          onSelect={() => openScreen("textsize")}
        />
        <ComingSoonRow label="Reduce motion" />
        <ComingSoonRow label="High contrast" />
      </SettingsGroup>

      <SettingsGroup title="Privacy and data">
        <SettingsRow
          label="Health information consent"
          value={consentValue(granted, consent?.withdrawn_at ?? null)}
          onSelect={() => openScreen("privacy")}
        />
        <SettingsRow
          label="What is stored"
          value={policy?.version ? `Policy v${policy.version}` : "Not loaded"}
          onSelect={() => openScreen("stored")}
        />
        <SettingsRow
          label="Export my data"
          value="JSON file"
          onSelect={() => openScreen("export")}
        />
        <SettingsRow
          label="Delete my data"
          value="Permanent"
          onSelect={() => openScreen("delete")}
        />
      </SettingsGroup>

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
            Removes your account and everything in it, with no recovery period.
          </p>
          <Button
            variant="destructive"
            className="min-h-11"
            onClick={() => openScreen("delete")}
          >
            Delete account
          </Button>
        </div>
      </section>
    </div>
  );
}
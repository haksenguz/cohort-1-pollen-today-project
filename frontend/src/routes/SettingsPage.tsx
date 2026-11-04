/**
 * Settings overview.
 *
 * One row per area, each showing the value you would see if you opened it, and
 * a screen behind every one of them. A row that has nothing behind it is left
 * out rather than shown as a dead end.
 *
 * The overview follows the pattern ChatGPT uses: a search field on top, then
 * flat rows under small grey labels. No cards, one hairline between rows.
 *
 * The user, allergy and preference fetches all run here rather than inside the
 * screens, because an overview row has to show a real value before you open
 * anything.
 */
import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Bell,
  ChevronRight,
  Code,
  Database,
  Download,
  HeartPulse,
  MapPin,
  Phone,
  Search,
  ShieldCheck,
  Trash2,
  TriangleAlert,
  Type,
  User,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { SettingsGroup, SettingsRow } from "./settings/SettingsRows";
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

/** One row on the overview. */
type OverviewRow = {
  label: string;
  value: string;
  icon: ReactNode;
  screen: SettingsScreenId;
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

/**
 * The rows a search keeps. A query matches a row when it appears in the row
 * title, in the value under it, or in the group the row sits in, so a search
 * for "privacy" brings up the whole privacy group.
 */
function matchesQuery(
  groupTitle: string,
  row: OverviewRow,
  query: string,
): boolean {
  const needle = query.toLowerCase();
  return (
    row.label.toLowerCase().includes(needle) ||
    row.value.toLowerCase().includes(needle) ||
    groupTitle.toLowerCase().includes(needle)
  );
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
  const [query, setQuery] = useState("");
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

  // Every row below opens a screen. A row without one was left out, because a
  // row that admits it does nothing is worse than no row at all.
  const groups: { title: string; rows: OverviewRow[] }[] = [
    {
      title: "Account",
      rows: [
        {
          label: "Profile",
          value: user.email,
          icon: <User className="size-4" />,
          screen: "profile",
        },
        {
          label: "Location",
          value: locationValue(user),
          icon: <MapPin className="size-4" />,
          screen: "location",
        },
      ],
    },
    {
      title: "Health",
      rows: [
        {
          label: "Allergies",
          value: allergyValue(allergies, allergyLoadError !== null),
          icon: <HeartPulse className="size-4" />,
          screen: "health",
        },
      ],
    },
    {
      title: "Emergency",
      rows: [
        {
          label: "Emergency contact",
          value: contactValue(contact, contactLoadError !== null),
          icon: <Phone className="size-4" />,
          screen: "emergency",
        },
      ],
    },
    {
      title: "Notifications",
      rows: [
        {
          label: "Categories",
          value: prefValue(prefs, prefsLoadError !== null, categoriesOn),
          icon: <Bell className="size-4" />,
          screen: "notifications",
        },
        {
          label: "Minimum risk",
          value: prefValue(prefs, prefsLoadError !== null, (p) => formatRisk(p.min_risk_level)),
          icon: <TriangleAlert className="size-4" />,
          screen: "notifications",
        },
      ],
    },
    {
      title: "Accessibility",
      rows: [
        {
          label: "Text size",
          value: textSize.label,
          icon: <Type className="size-4" />,
          screen: "textsize",
        },
      ],
    },
    {
      title: "Privacy and data",
      rows: [
        {
          label: "Health information consent",
          value: consentValue(granted, consent?.withdrawn_at ?? null),
          icon: <ShieldCheck className="size-4" />,
          screen: "privacy",
        },
        {
          label: "What is stored",
          value: policy?.version ? `Policy v${policy.version}` : "Not loaded",
          icon: <Database className="size-4" />,
          screen: "stored",
        },
        {
          label: "Export my data",
          value: "JSON file",
          icon: <Download className="size-4" />,
          screen: "export",
        },
        {
          label: "Delete my data",
          value: "Permanent",
          icon: <Trash2 className="size-4" />,
          screen: "delete",
        },
      ],
    },
  ];

  const needle = query.trim();
  const visibleGroups = needle
    ? groups
        .map((group) => ({
          ...group,
          rows: group.rows.filter((row) => matchesQuery(group.title, row, needle)),
        }))
        .filter((group) => group.rows.length > 0)
    : groups;

  return (
    <div className="stage flex flex-col gap-4">
      <div className="sticky top-0 z-10 -mx-4 flex flex-col gap-2 border-b border-border bg-background px-4 py-2">
        <div className="flex items-center gap-3">
          <Avatar>
            <AvatarFallback>{initialsFor(user.email)}</AvatarFallback>
          </Avatar>
          <h1 className="font-display text-lg font-semibold">Settings</h1>
          <Button
            variant="ghost"
            className="ml-auto min-h-11"
            onClick={() => navigate("/today")}
          >
            Done
          </Button>
        </div>

        <div className="relative">
          <Search
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search settings"
            placeholder="Search settings"
            className="h-11 pl-9"
          />
        </div>
      </div>

      {visibleGroups.length === 0 ? (
        <p className="text-sm text-muted-foreground">No settings match "{needle}".</p>
      ) : (
        visibleGroups.map((group) => (
          <SettingsGroup key={group.title} title={group.title}>
            {group.rows.map((row) => (
              <SettingsRow
                key={row.label}
                label={row.label}
                value={row.value}
                icon={row.icon}
                onSelect={() => openScreen(row.screen)}
              />
            ))}
          </SettingsGroup>
        ))
      )}

      <section aria-label="Advanced" className="flex flex-col gap-1.5">
        <h2 className="text-xs font-bold tracking-[0.12em] text-muted-foreground uppercase">
          Advanced
        </h2>
        <div className="flex flex-col divide-y divide-border">
          <SettingsRow
            label="Developer tools"
            value="Local development only"
            icon={<Code className="size-4" />}
            ariaExpanded={advancedOpen}
            ariaControls="settings-advanced"
            end={
              <ChevronRight
                aria-hidden
                className={`ml-auto size-4 shrink-0 text-muted-foreground ${advancedOpen ? "rotate-90" : ""}`}
              />
            }
            onSelect={() => setAdvancedOpen((open) => !open)}
          />
        </div>
        {advancedOpen ? (
          <div id="settings-advanced" className="flex flex-col gap-3 pt-3">
            {/* Renders nothing unless the backend has DEV_SETTINGS_ENABLED=true. */}
            <DevLlmSettingsCard />
          </div>
        ) : null}
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
        <div className="flex flex-col gap-2">
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

/**
 * Settings screen: location, allergies, notification preferences, and (on a local
 * dev box) the chat agent's API key.
 *
 * Composed from the shadcn components in src/components/ui rather than
 * hand-rolled form markup, per ADR 0004. Every endpoint it needs already
 * exists and is typed in the API client, so there is no backend work here
 * and no new dependency.
 *
 * Each section loads and saves independently. That is deliberate: a user
 * who only wants to silence weather alerts should not have to wait on, or
 * risk losing, their allergy edits.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import {
  ApiError,
  createAllergy,
  deleteAllergy,
  getCurrentUser,
  listAllergies,
  readPreferences,
  updateCurrentUser,
  updatePreferences,
} from "../api/client";
import type {
  Allergen,
  AllergyResponse,
  AllergySeverity,
  PreferenceResponse,
  RiskLevel,
  UserResponse,
} from "../api/types";
import { clearToken } from "../auth/token";
import {
  ALLERGEN_OPTIONS,
  ALLERGY_SEVERITIES,
  formatAllergyLabel,
  formatRisk,
  formatSeverityLabel,
} from "../utils/format";
import { DevLlmSettingsCard } from "./DevLlmSettingsCard";

const RISK_OPTIONS: readonly RiskLevel[] = ["LOW", "MODERATE", "HIGH", "EMERGENCY"];

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function initialsFor(email: string): string {
  const local = email.split("@")[0] ?? "";
  return (local.slice(0, 2) || "AC").toUpperCase();
}

// ---- Location ---------------------------------------------------------

// The spec's numeric GeolocationPositionError codes. They are spelled out
// here instead of read off `GeolocationPositionError.PERMISSION_DENIED`
// because that constant is missing in some older browsers, and so a failure
// has to be explained in words rather than left to a silent catch.
const GEO_PERMISSION_DENIED = 1;
const GEO_POSITION_UNAVAILABLE = 2;
const GEO_TIMEOUT = 3;

function geolocationErrorText(error: GeolocationPositionError): string {
  switch (error.code) {
    case GEO_PERMISSION_DENIED:
      return "Location permission denied. Allow location for this site in your browser settings, or enter coordinates manually below.";
    case GEO_POSITION_UNAVAILABLE:
      return "Your device could not work out a position. Move somewhere with a better signal, or enter coordinates manually below.";
    case GEO_TIMEOUT:
      return "Finding your location took too long. Try again, or enter coordinates manually below.";
    default:
      return "Could not read your location. Enter coordinates manually below.";
  }
}

function LocationSection({ user }: { user: UserResponse }) {
  const [latitude, setLatitude] = useState(
    user.latitude === null ? "" : String(user.latitude),
  );
  const [longitude, setLongitude] = useState(
    user.longitude === null ? "" : String(user.longitude),
  );
  const [saving, setSaving] = useState(false);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const manualRef = useRef<HTMLDetailsElement>(null);

  // The single save path for this section. The manual form and the
  // "Use my current location" button both land here, so the validation and
  // the updateCurrentUser call exist exactly once and a fix from GPS is
  // persisted the same way a typed one is.
  async function persist(latText: string, lonText: string) {
    setError(null);
    setSaved(false);

    const lat = latText.trim();
    const lon = lonText.trim();

    // Validation runs before the saving flag is raised, so a rejected value
    // leaves the form responsive instead of showing a spinner that cannot end.
    let payload: { latitude: number | null; longitude: number | null };
    if (lat === "" && lon === "") {
      payload = { latitude: null, longitude: null };
    } else {
      const latNum = Number(lat);
      const lonNum = Number(lon);
      if (
        !Number.isFinite(latNum) ||
        !Number.isFinite(lonNum) ||
        latNum < -90 ||
        latNum > 90 ||
        lonNum < -180 ||
        lonNum > 180
      ) {
        setError(
          "Latitude must be -90 to 90 and longitude -180 to 180. Leave both blank to clear.",
        );
        return;
      }
      payload = { latitude: latNum, longitude: lonNum };
    }

    // One guarded write for every path, including clearing the location. The
    // clear branch used to call `updateCurrentUser` unguarded: a rejected
    // request became an unhandled rejection with nothing shown on screen, and
    // the Save button stayed enabled because `saving` was never raised.
    setSaving(true);
    try {
      await updateCurrentUser(payload);
      setSaved(true);
    } catch (e) {
      setError(errorText(e, "Could not save your location."));
    } finally {
      setSaving(false);
    }
  }

  function revealManualEntry() {
    // Every failure below tells the reader to type coordinates instead. Open
    // the disclosure so that instruction points at something on screen.
    if (manualRef.current) manualRef.current.open = true;
  }

  function locate() {
    // A non-secure context (plain http on a LAN address) and older browsers
    // expose no geolocation at all, so there is no error event to read.
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setError(
        "This browser cannot find your location. Open the app over HTTPS, or enter coordinates manually below.",
      );
      revealManualEntry();
      return;
    }

    setError(null);
    setSaved(false);
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);
        const latText = String(position.coords.latitude);
        const lonText = String(position.coords.longitude);
        setLatitude(latText);
        setLongitude(lonText);
        void persist(latText, lonText);
      },
      (geoError) => {
        setLocating(false);
        setError(geolocationErrorText(geoError));
        revealManualEntry();
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
    );
  }

  function save() {
    void persist(latitude, longitude);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Location</CardTitle>
        <CardDescription>
          Used to look up pollen, air quality and nearby hospitals. Nothing
          is sent anywhere else.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <FieldGroup>
          <div className="flex flex-col gap-2">
            <Button onClick={locate} disabled={locating} aria-busy={locating}>
              {locating ? "Locating…" : "Use my current location"}
            </Button>
            <p className="text-xs text-muted-foreground">
              Asks your device for a GPS fix. Your browser will ask permission
              first.
            </p>
          </div>

          {error ? (
            <Alert variant="destructive">
              <AlertTitle>Location not updated</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          {saved ? (
            <p role="status" className="text-xs text-muted-foreground">
              Saved.
            </p>
          ) : null}

          <details ref={manualRef} className="flex flex-col gap-4 rounded-lg border p-3">
            <summary className="cursor-pointer text-sm font-medium">
              Enter coordinates manually
            </summary>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="profile-lat">Latitude</FieldLabel>
                <Input
                  id="profile-lat"
                  inputMode="decimal"
                  placeholder="37.5665"
                  value={latitude}
                  onChange={(e) => setLatitude(e.target.value)}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="profile-lon">Longitude</FieldLabel>
                <Input
                  id="profile-lon"
                  inputMode="decimal"
                  placeholder="126.9780"
                  value={longitude}
                  onChange={(e) => setLongitude(e.target.value)}
                />
              </Field>
              <div>
                <Button onClick={save} disabled={saving}>
                  {saving ? "Saving" : "Save location"}
                </Button>
              </div>
            </FieldGroup>
          </details>
        </FieldGroup>
      </CardContent>
    </Card>
  );
}

// ---- Allergies --------------------------------------------------------

function AllergiesSection() {
  const [allergies, setAllergies] = useState<AllergyResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Default to a real named allergen. "TREE_POLLEN" is a legacy coarse value
// kept for existing rows and still a valid enum member, but it is no longer
// in ALLERGEN_OPTIONS — so it left the picker trigger rendering blank.
const [allergen, setAllergen] = useState<Allergen>("BIRCH");
  const [severity, setSeverity] = useState<AllergySeverity>("MILD");
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setAllergies(await listAllergies());
    } catch (e) {
      setError(errorText(e, "Could not load your allergies."));
      setAllergies([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function add() {
    setAdding(true);
    setError(null);
    try {
      await createAllergy({ allergen, severity });
      await load();
    } catch (e) {
      setError(errorText(e, "Could not add that allergy."));
    } finally {
      setAdding(false);
    }
  }

  async function remove(id: number) {
    setError(null);
    try {
      await deleteAllergy(id);
      await load();
    } catch (e) {
      setError(errorText(e, "Could not remove that allergy."));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Allergies</CardTitle>
        <CardDescription>
          These adjust your risk score. They are not a diagnosis.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {allergies === null ? (
          <div className="flex flex-col gap-2" aria-hidden="true">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-6 w-40" />
          </div>
        ) : allergies.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nothing saved yet. Add what you react to below.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {allergies.map((a) => (
              <li key={a.id} className="flex items-center gap-2">
                <Badge variant="secondary">{formatAllergyLabel(a.allergen)}</Badge>
                <span className="text-sm text-muted-foreground">
                  {formatSeverityLabel(a.severity)}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-auto"
                  onClick={() => void remove(a.id)}
                  aria-label={`Remove ${formatAllergyLabel(a.allergen)}`}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        )}

        <Separator />

        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="profile-allergen">Add an allergy</FieldLabel>
            <Select
              value={allergen}
              onValueChange={(v) => setAllergen(v as Allergen)}
            >
              <SelectTrigger id="profile-allergen">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {ALLERGEN_OPTIONS.map((option) => (
                    <SelectItem key={option} value={option}>
                      {formatAllergyLabel(option)}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel htmlFor="profile-severity">How strong is it</FieldLabel>
            <ToggleGroup
              id="profile-severity"
              type="single"
              variant="outline"
              value={severity}
              onValueChange={(v) => {
                if (v) setSeverity(v as AllergySeverity);
              }}
            >
              {ALLERGY_SEVERITIES.map((option) => (
                <ToggleGroupItem key={option} value={option}>
                  {formatSeverityLabel(option)}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </Field>
          <div>
            <Button onClick={add} disabled={adding}>
              {adding ? "Adding" : "Add"}
            </Button>
          </div>
        </FieldGroup>

        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Something went wrong</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}

// ---- Notification preferences -----------------------------------------

const PREF_SWITCHES: readonly {
  key: "alert_pollen" | "alert_air_quality" | "alert_weather";
  label: string;
  hint: string;
}[] = [
  { key: "alert_pollen", label: "Pollen alerts", hint: "When pollen is high in your area." },
  { key: "alert_air_quality", label: "Air quality alerts", hint: "When PM2.5 or PM10 cross your threshold." },
  { key: "alert_weather", label: "Weather alerts", hint: "When conditions likely make symptoms worse." },
];

function PreferencesSection() {
  const [prefs, setPrefs] = useState<PreferenceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    readPreferences()
      .then((p) => {
        if (!cancelled) setPrefs(p);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(errorText(e, "Could not load your preferences."));
          setPrefs(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function patch(body: Parameters<typeof updatePreferences>[0]) {
    setError(null);
    setSaving(true);
    try {
      setPrefs(await updatePreferences(body));
    } catch (e) {
      setError(errorText(e, "Could not save that preference."));
    } finally {
      setSaving(false);
    }
  }

  if (prefs === null && error === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3" aria-hidden="true">
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-5/6" />
          <Skeleton className="h-6 w-4/6" />
        </CardContent>
      </Card>
    );
  }

  if (prefs === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertTitle>Could not load preferences</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Notifications</CardTitle>
        <CardDescription>
          Alerts are generated and stored on the server. Nothing is sent by
          this build.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {PREF_SWITCHES.map(({ key, label, hint }) => (
          <div key={key} className="flex items-start gap-3">
            <Switch
              id={key}
              checked={prefs[key]}
              disabled={saving}
              onCheckedChange={(checked) => void patch({ [key]: checked })}
            />
            <div className="flex flex-col gap-0.5">
              <Label htmlFor={key}>{label}</Label>
              <p className="text-xs text-muted-foreground">{hint}</p>
            </div>
          </div>
        ))}

        <Separator />

        <Field>
          <FieldLabel htmlFor="pref-min-risk">
            Minimum risk before I get alerted
          </FieldLabel>
          <Select
            value={prefs.min_risk_level}
            onValueChange={(v) => void patch({ min_risk_level: v as RiskLevel })}
          >
            <SelectTrigger id="pref-min-risk">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {RISK_OPTIONS.map((option) => (
                  <SelectItem key={option} value={option}>
                    {formatRisk(option)}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>

        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Not saved</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}

// ---- Page -------------------------------------------------------------

export function SettingsPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState<UserResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

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
        // sign in again — otherwise logging out is a manual, undiscoverable
        // action and the only other page (the dev key card) sits behind this
        // very gate.
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
          clearToken();
          navigate("/login", { replace: true });
          return;
        }
        setError(errorText(e, "Could not load your settings."));
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  if (error) {
    return (
      <div className="stage flex flex-col gap-4">
        <Alert variant="destructive">
          <AlertTitle>Could not load your settings</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
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

  return (
    <div className="stage flex flex-col gap-4">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <Avatar>
              <AvatarFallback>{initialsFor(user.email)}</AvatarFallback>
            </Avatar>
            <div className="flex flex-col">
              <CardTitle>Settings</CardTitle>
              <CardDescription>{user.email}</CardDescription>
            </div>
          </div>
          <CardAction>
            <Button variant="ghost" size="sm" onClick={() => navigate("/today")}>
              Done
            </Button>
          </CardAction>
        </CardHeader>
      </Card>

      <LocationSection user={user} />
      <AllergiesSection />
      <PreferencesSection />
      {/* Renders nothing unless the backend has DEV_SETTINGS_ENABLED=true. */}
      <DevLlmSettingsCard />
    </div>
  );
}

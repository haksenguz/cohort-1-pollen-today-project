/**
 * The settings screens behind the overview rows.
 *
 * Each one owns its own saving, error and skeleton state, and writes through
 * callbacks the page hands down so an overview row can show the new value as
 * soon as the server confirms it.
 */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { ChevronLeft } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldTitle } from "@/components/ui/field";
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

import { updateCurrentUser } from "../../api/client";
import type {
  AllergyCreateRequest,
  AllergyResponse,
  Allergen,
  AllergySeverity,
  PreferenceResponse,
  PreferenceUpdateRequest,
  RiskLevel,
  UserResponse,
} from "../../api/types";
import {
  ALLERGEN_OPTIONS,
  ALLERGY_SEVERITIES,
  formatAllergyLabel,
  formatRisk,
  formatSeverityLabel,
} from "../../utils/format";

const RISK_OPTIONS: readonly RiskLevel[] = ["LOW", "MODERATE", "HIGH", "EMERGENCY"];

/**
 * The values a fresh account gets. Mirrors the NotificationPreference model
 * defaults in backend/app/models/__init__.py, so "restore defaults" writes the
 * same thing the server would have created on its own.
 */
const DEFAULT_PREFERENCES: PreferenceUpdateRequest = {
  alert_pollen: true,
  alert_air_quality: true,
  alert_weather: true,
  min_risk_level: "MODERATE",
  quiet_hours_start: null,
  quiet_hours_end: null,
};

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

export function SettingsSubScreen({
  title,
  onBack,
  children,
}: {
  title: string;
  onBack: () => void;
  children: ReactNode;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1">
        <Button variant="ghost" onClick={onBack} className="min-h-11 gap-1 px-2">
          <ChevronLeft aria-hidden className="size-4" />
          Back
        </Button>
        <h2
          ref={headingRef}
          tabIndex={-1}
          className="font-display text-lg font-semibold focus:outline-none"
        >
          {title}
        </h2>
      </div>
      {children}
    </div>
  );
}

function LoadError({ title, message, onRetry }: { title: string; message: string; onRetry: () => void }) {
  return (
    <Alert variant="destructive">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
      <Button variant="outline" onClick={onRetry} className="mt-1 min-h-11">
        Try again
      </Button>
    </Alert>
  );
}

function SavedNotice({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="text-xs text-muted-foreground">
      {children}
    </p>
  );
}

// ---- Profile ------------------------------------------------------------

export function ProfileScreen({ user }: { user: UserResponse }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Your account</CardTitle>
        <CardDescription>How you sign in to this app.</CardDescription>
      </CardHeader>
      <CardContent>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="profile-email">Email</FieldLabel>
            <Input id="profile-email" value={user.email} readOnly />
            <FieldDescription>Changing your email is not built yet.</FieldDescription>
          </Field>
          <Field>
            <FieldTitle>Name</FieldTitle>
            <FieldDescription>
              Not built yet. Your account does not have a name yet.
            </FieldDescription>
          </Field>
          <Field>
            <FieldTitle>Member since</FieldTitle>
            <FieldDescription>
              {new Date(user.created_at).toLocaleDateString()}
            </FieldDescription>
          </Field>
        </FieldGroup>
      </CardContent>
    </Card>
  );
}

// ---- Location -----------------------------------------------------------

// The spec's numeric GeolocationPositionError codes, spelled out instead of
// read off GeolocationPositionError.PERMISSION_DENIED because that constant is
// missing in some older browsers, leaving a failure with nothing to explain it.
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

export function LocationScreen({
  user,
  onSaved,
}: {
  user: UserResponse;
  onSaved: (user: UserResponse) => void;
}) {
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

  // The one save path. The manual form and "Use my current location" both land
  // here, so a GPS fix is persisted exactly like a typed one.
  async function persist(latText: string, lonText: string) {
    setError(null);
    setSaved(false);

    const lat = latText.trim();
    const lon = lonText.trim();

    // Validation runs before `saving` is raised, so a rejected value leaves the
    // form responsive instead of showing a spinner that cannot end.
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

    // One guarded write for every path, clearing included.
    setSaving(true);
    try {
      onSaved(await updateCurrentUser(payload));
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

  return (
    <Card>
      <CardHeader>
        <CardTitle>Where you are</CardTitle>
        <CardDescription>
          Used to look up pollen, air quality and nearby hospitals. Nothing is
          sent anywhere else.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <FieldGroup>
          <div className="flex flex-col gap-2">
            <Button onClick={locate} disabled={locating} aria-busy={locating} className="min-h-11">
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
          {saved ? <SavedNotice>Saved.</SavedNotice> : null}

          <details ref={manualRef} className="flex flex-col gap-4 rounded-lg border p-3">
            <summary className="min-h-11 cursor-pointer text-sm font-medium">
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
                <Button onClick={() => void persist(latitude, longitude)} disabled={saving} className="min-h-11">
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

// ---- Health / allergies -------------------------------------------------

export function HealthScreen({
  allergies,
  loadError,
  onRetry,
  onAdd,
  onRemove,
}: {
  allergies: AllergyResponse[] | null;
  loadError: string | null;
  onRetry: () => void;
  onAdd: (body: AllergyCreateRequest) => Promise<void>;
  onRemove: (id: number) => Promise<void>;
}) {
  const [error, setError] = useState<string | null>(null);
  // Default to a real named allergen. "TREE_POLLEN" is a legacy coarse value
  // kept for existing rows and still a valid enum member, but it is no longer
  // in ALLERGEN_OPTIONS, so it left the picker trigger rendering blank.
  const [allergen, setAllergen] = useState<Allergen>("BIRCH");
  const [severity, setSeverity] = useState<AllergySeverity>("MILD");
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<void>) {
    setError(null);
    setBusy(true);
    try {
      await action();
    } catch (e) {
      setError(errorText(e, "Could not save your allergies."));
    } finally {
      setBusy(false);
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
        {loadError ? (
          <LoadError title="Could not load allergies" message={loadError} onRetry={onRetry} />
        ) : allergies === null ? (
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
                  className="ml-auto min-h-11"
                  onClick={() => void run(() => onRemove(a.id))}
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
            <Button
              onClick={() => void run(() => onAdd({ allergen, severity }))}
              disabled={busy}
              className="min-h-11"
            >
              {busy ? "Saving" : "Add"}
            </Button>
          </div>
        </FieldGroup>

        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Not saved</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        <Separator />

        <div className="flex flex-col gap-0.5">
          <FieldTitle>Medications</FieldTitle>
          <FieldDescription>Not built yet.</FieldDescription>
        </div>
      </CardContent>
    </Card>
  );
}

// ---- Notifications ------------------------------------------------------

const PREF_SWITCHES: readonly {
  key: "alert_pollen" | "alert_air_quality" | "alert_weather";
  label: string;
  hint: string;
}[] = [
  { key: "alert_pollen", label: "Pollen alerts", hint: "When pollen is high in your area." },
  { key: "alert_air_quality", label: "Air quality alerts", hint: "When PM2.5 or PM10 cross your threshold." },
  { key: "alert_weather", label: "Weather alerts", hint: "When conditions likely make symptoms worse." },
];

export function NotificationsScreen({
  prefs,
  loadError,
  onRetry,
  onChange,
}: {
  prefs: PreferenceResponse | null;
  loadError: string | null;
  onRetry: () => void;
  onChange: (body: PreferenceUpdateRequest) => Promise<void>;
}) {
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function submit(body: PreferenceUpdateRequest) {
    setError(null);
    setSaved(false);
    setSaving(true);
    try {
      await onChange(body);
      setSaved(true);
    } catch (e) {
      setError(errorText(e, "Could not save that preference."));
    } finally {
      setSaving(false);
    }
  }

  if (loadError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
        </CardHeader>
        <CardContent>
          <LoadError
            title="Could not load preferences"
            message={loadError}
            onRetry={onRetry}
          />
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
        <CardContent className="flex flex-col gap-3" aria-hidden="true">
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-5/6" />
          <Skeleton className="h-6 w-4/6" />
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
              onCheckedChange={(checked) => void submit({ [key]: checked })}
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
            onValueChange={(v) => void submit({ min_risk_level: v as RiskLevel })}
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

        <Separator />

        <div className="flex flex-col gap-2">
          <div className="flex flex-col gap-0.5">
            <FieldTitle>Quiet hours</FieldTitle>
            <FieldDescription>Not built yet.</FieldDescription>
          </div>
          <div className="flex flex-col gap-0.5">
            <FieldTitle>Notification permission</FieldTitle>
            <FieldDescription>
              Not built yet. Alerts are stored on the server, so your browser
              has not been asked for permission.
            </FieldDescription>
          </div>
        </div>

        <Separator />

        <Button
          variant="outline"
          className="min-h-11"
          disabled={saving}
          onClick={() => void submit(DEFAULT_PREFERENCES)}
        >
          {saving ? "Saving" : "Restore defaults"}
        </Button>

        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Not saved</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        {saved ? <SavedNotice>Saved.</SavedNotice> : null}
      </CardContent>
    </Card>
  );
}
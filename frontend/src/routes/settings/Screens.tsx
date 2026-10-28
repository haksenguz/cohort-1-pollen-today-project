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
import type { EmergencyContact } from "../../api/emergencyContact";
import type { PolicyDocument } from "../../api/consent";
import {
  ALLERGEN_OPTIONS,
  ALLERGY_SEVERITIES,
  formatAllergyLabel,
  formatRisk,
  formatSeverityLabel,
} from "../../utils/format";
import {
  DEFAULT_TEXT_SIZE,
  TEXT_SIZE_STEPS,
  type TextSizeStep,
} from "../../prefs/textSize";

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
          Alerts are created and stored on the server. The app shows them while
          it is open. Nothing is sent when the app is closed.
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

// ---- Privacy and data ---------------------------------------------------

/**
 * The 민감정보 consent, and the way out of it.
 *
 * The withdrawal is the reason this screen exists. A consent that cannot be
 * taken back is not consent, and the user should not have to write to anyone
 * to take it back: 제38조④ asks for the same effort as signing up was.
 */
export function PrivacyScreen({
  granted,
  grantedAt,
  operator,
  noticeItems,
  onSetGranted,
}: {
  granted: boolean;
  grantedAt: string | null;
  operator: string | null;
  noticeItems: string[];
  onSetGranted: (granted: boolean) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function run(next: boolean) {
    setError(null);
    setSaved(false);
    setBusy(true);
    try {
      await onSetGranted(next);
      setSaved(true);
    } catch (e) {
      setError(errorText(e, "Could not record your choice."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Health information consent</CardTitle>
        <CardDescription>
          Your symptoms, your allergies and the risk level the app assigned are
          health information. Korean privacy law (제23조) lets the app process
          them only on your separate agreement.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-0.5">
          <FieldTitle>Your agreement</FieldTitle>
          <FieldDescription>
            {granted
              ? `Agreed${grantedAt ? ` on ${new Date(grantedAt).toLocaleDateString()}` : ""}. The chat and your allergy list are open.`
              : "Not agreed yet. The chat stays closed until you agree."}
          </FieldDescription>
        </div>

        <Separator />

        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-medium">What the agreement covers</h3>
          <ul className="flex list-disc flex-col gap-1 pl-5 text-sm text-muted-foreground">
            {noticeItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>

        <Separator />

        <div className="flex flex-col gap-0.5">
          <h3 className="text-sm font-medium">Who runs this app</h3>
          <p className="text-sm text-muted-foreground">
            {operator ?? "No operator is named yet, so this policy cannot be published."}
          </p>
        </div>

        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Not recorded</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        {saved ? <SavedNotice>Saved.</SavedNotice> : null}

        <div className="flex flex-col gap-2">
          {granted ? (
            <Button
              variant="outline"
              className="min-h-11"
              disabled={busy}
              onClick={() => void run(false)}
            >
              {busy ? "Saving" : "Withdraw my agreement"}
            </Button>
          ) : (
            <Button className="min-h-11" disabled={busy} onClick={() => void run(true)}>
              {busy ? "Saving" : "Agree"}
            </Button>
          )}
          <p className="text-xs text-muted-foreground">
            {granted
              ? "Withdrawing stops the app from processing your health information. What is already stored stays until you delete it."
              : "Nothing is recorded until you agree."}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

// ---- Emergency contact ---------------------------------------------------

/**
 * The emergency contact.
 *
 * The app cannot call this number. It has no way to place a call, and a
 * screen that pretended otherwise would be the most dangerous lie in the app.
 * The number is here so the person holding the phone can dial it.
 */
export function EmergencyContactScreen({
  contact,
  loadError,
  onRetry,
  onSave,
}: {
  contact: EmergencyContact | null;
  loadError: string | null;
  onRetry: () => void;
  onSave: (contact: {
    name: string | null;
    phone: string | null;
    note: string | null;
  }) => Promise<void>;
}) {
  const [name, setName] = useState(contact?.name ?? "");
  const [phone, setPhone] = useState(contact?.phone ?? "");
  const [note, setNote] = useState(contact?.note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // The server is the source of truth for what is saved, so the form starts
  // from the loaded contact. The page gives this screen a new key when the
  // contact arrives, so the fields fill themselves once instead of being
  // pushed into state by an effect.

  async function run(action: () => Promise<void>) {
    setError(null);
    setSaved(false);
    setBusy(true);
    try {
      await action();
      setSaved(true);
    } catch (e) {
      setError(errorText(e, "Could not save your emergency contact."));
    } finally {
      setBusy(false);
    }
  }

  function save() {
    return run(() =>
      onSave({
        name: name.trim() || null,
        phone: phone.trim() || null,
        note: note.trim() || null,
      }),
    );
  }

  function clear() {
    setName("");
    setPhone("");
    setNote("");
    return run(() => onSave({ name: null, phone: null, note: null }));
  }

  if (loadError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Emergency contact</CardTitle>
        </CardHeader>
        <CardContent>
          <LoadError
            title="Could not load your emergency contact"
            message={loadError}
            onRetry={onRetry}
          />
        </CardContent>
      </Card>
    );
  }

  if (contact === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Emergency contact</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3" aria-hidden="true">
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-2/3" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Emergency contact</CardTitle>
        <CardDescription>
          The person to call if you cannot reach yourself. This app cannot call
          them for you. It is a number you choose to dial.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="emergency-name">Name</FieldLabel>
            <Input
              id="emergency-name"
              value={name}
              autoComplete="name"
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="emergency-phone">Phone number</FieldLabel>
            <Input
              id="emergency-phone"
              value={phone}
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              onChange={(e) => setPhone(e.target.value)}
            />
            <FieldDescription>
              Digits, spaces, dashes and a leading + are fine. Between 7 and 15
              digits.
            </FieldDescription>
          </Field>
          <Field>
            <FieldLabel htmlFor="emergency-note">Note</FieldLabel>
            <Input
              id="emergency-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
            <FieldDescription>
              Anything they should know, such as where the medicine is.
            </FieldDescription>
          </Field>
        </FieldGroup>

        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Not saved</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        {saved ? <SavedNotice>Saved.</SavedNotice> : null}

        <div className="flex flex-col gap-2">
          <Button className="min-h-11" disabled={busy} onClick={() => void save()}>
            {busy ? "Saving" : "Save"}
          </Button>
          <Button
            variant="outline"
            className="min-h-11"
            disabled={busy}
            onClick={() => void clear()}
          >
            Clear
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ---- Text size ----------------------------------------------------------

/**
 * The text size control behind the Accessibility group (bugs.md F4, WCAG 2.2
 * SC 1.4.4). No fetching and no saving state, unlike the screens above: this
 * one is a preference about how the reader sees the app on this device, so it
 * is held in the browser and applies to every screen, not just this one.
 */
export function TextSizeScreen({
  step,
  onChange,
}: {
  step: TextSizeStep;
  onChange: (next: TextSizeStep) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Text size</CardTitle>
        <CardDescription>
          Makes every text size in the app bigger or smaller. Pinching or
          ctrl-plus on the browser still zooms on top of this.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Field>
          <FieldTitle id="pref-text-size-label">Text size</FieldTitle>
          <ToggleGroup
            type="single"
            variant="outline"
            value={step.id}
            onValueChange={(next) => {
              // Clicking the step that is already selected reports an empty
              // string, and that is not a choice. Restore defaults is how you
              // go back to Normal.
              const picked = TEXT_SIZE_STEPS.find((option) => option.id === next);
              if (picked) onChange(picked);
            }}
            /* w-full flex-wrap rather than the default w-fit row of shrink-0
               items: at the largest step four options no longer fit across a
               phone, and without wrapping the last one is pushed out of the
               card. That is the loss of content SC 1.4.4 is about. */
            className="w-full flex-wrap justify-start"
            aria-labelledby="pref-text-size-label"
          >
            {TEXT_SIZE_STEPS.map((option) => (
              <ToggleGroupItem
                key={option.id}
                value={option.id}
                /* Keeps the visible label at the front of the accessible name,
                   so speech input still matches what is on screen. */
                aria-label={`${option.label}, ${option.percent}%`}
              >
                {option.label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <FieldDescription>
            The largest setting is double the default text size, and every
            screen stays readable at it.
          </FieldDescription>
        </Field>

        <div>
          <Button
            variant="outline"
            className="min-h-11"
            onClick={() => onChange(DEFAULT_TEXT_SIZE)}
          >
            Restore defaults
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
// ---- Privacy rights -------------------------------------------------------

/**
 * What the server holds, read from the published policy.
 *
 * The policy is public, because a policy only a signed-in user can read was
 * never disclosed before consent was asked for.
 */
export function StoredDataScreen({
  policy,
  policyError,
  onRetry,
}: {
  policy: PolicyDocument | null;
  policyError: string | null;
  onRetry: () => void;
}) {
  if (policyError !== null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>What is stored</CardTitle>
          <CardDescription>The policy could not be loaded.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Alert variant="destructive">
            <AlertTitle>Could not load the policy</AlertTitle>
            <AlertDescription>{policyError}</AlertDescription>
          </Alert>
          <Button variant="outline" className="min-h-11" onClick={onRetry}>
            Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (policy === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>What is stored</CardTitle>
          <CardDescription>Loading the policy…</CardDescription>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-32 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>What is stored</CardTitle>
        <CardDescription>
          {policy.title}, version {policy.version}
          {policy.requires_legal_review ? ", still a draft" : ""}.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {policy.operator_named === false ? (
          <Alert>
            <AlertTitle>No operator is named yet</AlertTitle>
            <AlertDescription>
              This deployment has not published who runs the app, so the policy
              below is not a published notice.
            </AlertDescription>
          </Alert>
        ) : null}
        {policy.sections.map((section) => (
          <section key={section.heading} className="flex flex-col gap-1.5">
            <h3 className="text-sm font-medium">{section.heading}</h3>
            {section.body.map((paragraph) => (
              <p key={paragraph} className="text-sm text-muted-foreground">
                {paragraph}
              </p>
            ))}
          </section>
        ))}
      </CardContent>
    </Card>
  );
}

/**
 * The export right.
 *
 * The button downloads a file rather than opening a screen of the data. The
 * export can hold every symptom the user ever described, and a phone screen
 * is the wrong place to read that.
 */
export function ExportDataScreen({ onExport }: { onExport: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function run() {
    setError(null);
    setDone(false);
    setBusy(true);
    try {
      await onExport();
      setDone(true);
    } catch (e) {
      setError(errorText(e, "Could not prepare your export."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Export my data</CardTitle>
        <CardDescription>
          A JSON file with everything this server holds about your account:
          your profile, your allergies, your conversations, the symptom events
          and the risk levels the engine assigned, and your emergency contact.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Export failed</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        {done ? <SavedNotice>Your file has been downloaded.</SavedNotice> : null}
        <Button className="min-h-11" disabled={busy} onClick={() => void run()}>
          {busy ? "Preparing" : "Download my data"}
        </Button>
      </CardContent>
    </Card>
  );
}

/**
 * The deletion right.
 *
 * Deletion is a hard delete with no recovery period, so it asks twice. The
 * first tap says what will go, the second one does it.
 */
export function DeleteDataScreen({ onDelete }: { onDelete: () => Promise<void> }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setError(null);
    setBusy(true);
    try {
      await onDelete();
    } catch (e) {
      setError(errorText(e, "Could not delete your account."));
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Delete my data</CardTitle>
        <CardDescription>
          This removes your account and everything attached to it: your profile,
          your allergies, every conversation and message, the symptom events and
          their risk levels, your notification preferences and your emergency
          contact.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Alert variant="destructive">
          <AlertTitle>Permanent</AlertTitle>
          <AlertDescription>
            There is no recovery period and no undo. Export your data first if
            you want a copy of it.
          </AlertDescription>
        </Alert>

        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Nothing was deleted</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        {confirming ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-muted-foreground">
              This cannot be undone. Delete everything now?
            </p>
            <div className="flex gap-2">
              <Button
                variant="destructive"
                className="min-h-11"
                disabled={busy}
                onClick={() => void run()}
              >
                {busy ? "Deleting" : "Yes, delete everything"}
              </Button>
              <Button
                variant="outline"
                className="min-h-11"
                disabled={busy}
                onClick={() => setConfirming(false)}
              >
                Keep my data
              </Button>
            </div>
          </div>
        ) : (
          <Button
            variant="destructive"
            className="min-h-11"
            onClick={() => setConfirming(true)}
          >
            Delete my account
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
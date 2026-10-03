/**
 * Profile screen: location, allergies, and notification preferences.
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
import { useCallback, useEffect, useState } from "react";
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
import {
  ALLERGEN_OPTIONS,
  ALLERGY_SEVERITIES,
  formatAllergyLabel,
  formatRisk,
  formatSeverityLabel,
} from "../utils/format";

const RISK_OPTIONS: readonly RiskLevel[] = ["LOW", "MODERATE", "HIGH", "EMERGENCY"];

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function initialsFor(email: string): string {
  const local = email.split("@")[0] ?? "";
  return (local.slice(0, 2) || "AC").toUpperCase();
}

// ---- Location ---------------------------------------------------------

function LocationSection({ user }: { user: UserResponse }) {
  const [latitude, setLatitude] = useState(
    user.latitude === null ? "" : String(user.latitude),
  );
  const [longitude, setLongitude] = useState(
    user.longitude === null ? "" : String(user.longitude),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function save() {
    setError(null);
    setSaved(false);

    const lat = latitude.trim();
    const lon = longitude.trim();
    if (lat === "" && lon === "") {
      await updateCurrentUser({ latitude: null, longitude: null });
      setSaved(true);
      return;
    }
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
      setError("Latitude must be -90 to 90 and longitude -180 to 180. Leave both blank to clear.");
      return;
    }

    setSaving(true);
    try {
      await updateCurrentUser({ latitude: latNum, longitude: lonNum });
      setSaved(true);
    } catch (e) {
      setError(errorText(e, "Could not save your location."));
    } finally {
      setSaving(false);
    }
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
          {error ? (
            <Alert variant="destructive">
              <AlertTitle>Not saved</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          {saved ? <p className="text-xs text-muted-foreground">Saved.</p> : null}
          <div>
            <Button onClick={save} disabled={saving}>
              {saving ? "Saving" : "Save location"}
            </Button>
          </div>
        </FieldGroup>
      </CardContent>
    </Card>
  );
}

// ---- Allergies --------------------------------------------------------

function AllergiesSection() {
  const [allergies, setAllergies] = useState<AllergyResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [allergen, setAllergen] = useState<Allergen>("TREE_POLLEN");
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

export function ProfilePage() {
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
        if (!cancelled) setError(errorText(e, "Could not load your profile."));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="stage flex flex-col gap-4">
        <Alert variant="destructive">
          <AlertTitle>Could not load your profile</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button variant="outline" onClick={() => navigate("/today")}>
          Back to today
        </Button>
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
              <CardTitle>Profile</CardTitle>
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
    </div>
  );
}

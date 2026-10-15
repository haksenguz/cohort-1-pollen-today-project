/**
 * Local-dev panel: paste the chat agent's API key without leaving the app.
 *
 * Why it exists
 * -------------
 * The chat agent reads OPENAI_API_KEY from `backend/.env` at import time. The
 * old loop was: leave the browser, edit the file, restart the API, come back.
 * When you are testing the chat, that loop happens on every key you try.
 *
 * What this is NOT
 * ----------------
 * Not a user-facing setting, and not a per-user credential — the key is
 * server-wide and every user of this instance shares it. It only renders when
 * `GET /api/dev/llm` succeeds, which only happens when the backend has
 * `DEV_SETTINGS_ENABLED=true`. In every other build this component renders
 * nothing and the panel never appears.
 */
import { useCallback, useEffect, useState } from "react";

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
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

import { readDevLlmSettings, saveDevLlmSettings } from "../api/client";
import type { DevLlmSettingsResponse } from "../api/types";

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

export function DevLlmSettingsCard() {
  const [available, setAvailable] = useState(false);
  const [settings, setSettings] = useState<DevLlmSettingsResponse | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    try {
      const next = await readDevLlmSettings();
      setSettings(next);
      setBaseUrl(next.base_url);
      setModel(next.model);
      setAvailable(true);
    } catch {
      // Endpoint absent means DEV_SETTINGS_ENABLED is off — the normal case
      // for anything but a local dev box, so this is not worth surfacing.
      setAvailable(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    setError(null);
    setSaved(false);
    setSaving(true);
    try {
      const next = await saveDevLlmSettings({
        api_key: apiKey.trim(),
        base_url: baseUrl.trim(),
        model: model.trim(),
      });
      setSettings(next);
      // The key is never returned, so the field cannot be repopulated from it.
      setApiKey("");
      setSaved(true);
    } catch (e) {
      setError(errorText(e, "Could not save the key."));
    } finally {
      setSaving(false);
    }
  }

  if (!available) return null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle>Chat agent key</CardTitle>
          <Badge variant="secondary">local dev</Badge>
        </div>
        <CardDescription>
          Server-wide, not per-account. Stored in backend/.env and used by the
          next message immediately — no restart.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3 text-sm">
          <p className="text-muted-foreground">
            {settings?.configured ? (
              <>
                Key loaded: <code>{settings.key_hint}</code>
              </>
            ) : (
              "No key loaded — chat replies with a configuration error."
            )}
          </p>

          <Separator />

          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="dev-api-key">
                API key {settings?.configured ? "(paste a new one to replace)" : ""}
              </FieldLabel>
              <Input
                id="dev-api-key"
                type="password"
                autoComplete="off"
                spellCheck={false}
                placeholder="sk-..."
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="dev-base-url">
                Base URL (optional)
              </FieldLabel>
              <Input
                id="dev-base-url"
                placeholder="https://openrouter.ai/api/v1"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="dev-model">Model</FieldLabel>
              <Input
                id="dev-model"
                placeholder="gpt-4o-mini"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              />
            </Field>

            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Not saved</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
            {saved ? (
              <p className="text-xs text-muted-foreground">
                Saved. Head to Chat to try it.
              </p>
            ) : null}

            <div>
              <Button onClick={() => void save()} disabled={saving}>
                {saving ? "Saving" : "Save key"}
              </Button>
            </div>
          </FieldGroup>
        </div>
      </CardContent>
    </Card>
  );
}
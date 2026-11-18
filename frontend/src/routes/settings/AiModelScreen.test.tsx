/**
 * The AI model screen. It has to tell apart: no key saved, a key saved, a
 * save that worked (and cleared the field), a save that failed, and a removed
 * key. The key must never stay on the page after it has been sent.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { LlmSettingsResponse } from "../../api/types";
import { llmKeyTail, llmStatusText } from "../../utils/llm";
import { AiModelScreen } from "./Screens";

const saved = (overrides: Partial<LlmSettingsResponse> = {}): LlmSettingsResponse => ({
  configured: true,
  key_hint: "gsk_...1234",
  provider: "groq",
  base_url: null,
  model: null,
  ...overrides,
});

const unsaved: LlmSettingsResponse = {
  configured: false,
  key_hint: "",
  provider: null,
  base_url: null,
  model: null,
};

const renderScreen = (props: {
  settings?: LlmSettingsResponse | null;
  loadError?: string | null;
  onSave?: (body: { api_key: string; provider: string; model: string | null }) => Promise<void>;
  onRemove?: () => Promise<void>;
}) =>
  render(
    <AiModelScreen
      settings={props.settings === undefined ? unsaved : props.settings}
      loadError={props.loadError ?? null}
      onRetry={vi.fn()}
      onSave={props.onSave ?? vi.fn().mockResolvedValue(undefined)}
      onRemove={props.onRemove ?? vi.fn().mockResolvedValue(undefined)}
    />,
  );

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("AiModelScreen", () => {
  it("says the shared model is used when no key is saved", () => {
    renderScreen({});

    expect(screen.getByText(/leave it empty to use the app's shared model/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Remove my key" })).toBeDisabled();
  });

  it("keeps the key input a password field with autocomplete off", () => {
    renderScreen({});

    const input = screen.getByLabelText("API key");
    expect(input).toHaveAttribute("type", "password");
    expect(input).toHaveAttribute("autocomplete", "off");
  });

  it("disables Save until a key is typed", () => {
    renderScreen({});

    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "gsk_new" } });
    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
  });

  it("shows a saved key as configured and offers to remove it", () => {
    renderScreen({ settings: saved() });

    expect(screen.getByText(/your groq key is saved/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Remove my key" })).toBeEnabled();
  });

  it("sends the key, provider and model, then clears the key field", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderScreen({ onSave });

    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "  gsk_new  " } });
    fireEvent.change(screen.getByLabelText("Model (optional)"), {
      target: { value: " llama-3.3 " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith({
        api_key: "gsk_new",
        provider: "groq",
        model: "llama-3.3",
      }),
    );
    expect(await screen.findByText("Saved.")).toBeTruthy();
    expect(screen.getByLabelText("API key")).toHaveValue("");
  });

  it("shows the error and keeps the typed key when the save fails", async () => {
    const onSave = vi.fn().mockRejectedValue(new Error("That key was rejected by the provider."));
    renderScreen({ onSave });

    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "gsk_bad" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("That key was rejected by the provider.")).toBeTruthy();
    expect(screen.getByLabelText("API key")).toHaveValue("gsk_bad");
  });

  it("removes the saved key and reports it", async () => {
    const onRemove = vi.fn().mockResolvedValue(undefined);
    renderScreen({ settings: saved(), onRemove });

    fireEvent.click(screen.getByRole("button", { name: "Remove my key" }));

    await waitFor(() => expect(onRemove).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Saved.")).toBeTruthy();
  });

  it("shows an error when remove fails", async () => {
    const onRemove = vi.fn().mockRejectedValue(new Error("Server unavailable."));
    renderScreen({ settings: saved(), onRemove });

    fireEvent.click(screen.getByRole("button", { name: "Remove my key" }));

    expect(await screen.findByText("Server unavailable.")).toBeTruthy();
  });

  it("shows a load error with a retry", () => {
    renderScreen({ settings: null, loadError: "Could not load your AI model." });

    expect(screen.getByText("Could not load your AI model.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});

describe("llm helpers", () => {
  it("names the provider and the last four characters on the overview row", () => {
    expect(llmStatusText(saved(), false)).toBe("Using your Groq key ending 1234");
    expect(llmStatusText(unsaved, false)).toBe("Using the app's shared model");
    expect(llmStatusText(null, true)).toBe("Could not load");
    expect(llmStatusText(null, false)).toBe("Loading…");
  });

  it("takes the last four alphanumerics of the hint", () => {
    expect(llmKeyTail("gsk_...abcd")).toBe("abcd");
  });
});

/**
 * Starter-prompt chip tests.
 *
 * The chips are only worth having if tapping one actually puts the sentence in
 * the composer, so the assertions run against a real assistant-ui runtime and
 * read the composer state back out of it rather than asserting that a
 * callback fired.
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { AssistantRuntimeProvider, useAuiState, useLocalRuntime } from "@assistant-ui/react";
import type { ChatModelAdapter } from "@assistant-ui/react";

import { SUGGESTED_PROMPTS } from "./starterPrompts";
import { SuggestedPrompts } from "./SuggestedPrompts";

const stubAdapter: ChatModelAdapter = {
  run: async () => ({ content: [{ type: "text", text: "" }] }),
};

function ComposerText() {
  const text = useAuiState((state) => state.composer.text);
  return <span data-testid="composer">{text}</span>;
}

function Harness({ onSelect }: { onSelect?: (prompt: string) => void }) {
  const runtime = useLocalRuntime(stubAdapter);
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ComposerText />
      <SuggestedPrompts onSelect={onSelect} />
    </AssistantRuntimeProvider>
  );
}

describe("SuggestedPrompts", () => {
  it("renders one chip per starter prompt", () => {
    render(<Harness />);

    for (const prompt of SUGGESTED_PROMPTS) {
      expect(screen.getByRole("button", { name: prompt })).toBeInTheDocument();
    }
  });

  it("seeds the composer with the tapped prompt instead of sending it", () => {
    render(<Harness />);
    expect(screen.getByTestId("composer")).toHaveTextContent("");

    fireEvent.click(screen.getByRole("button", { name: SUGGESTED_PROMPTS[0] }));

    expect(screen.getByTestId("composer")).toHaveTextContent(SUGGESTED_PROMPTS[0]);
  });

  it("uses an explicit onSelect when one is given", () => {
    const seen: string[] = [];
    render(<Harness onSelect={(prompt) => seen.push(prompt)} />);

    fireEvent.click(screen.getByRole("button", { name: SUGGESTED_PROMPTS[2] }));

    expect(seen).toEqual([SUGGESTED_PROMPTS[2]]);
    expect(screen.getByTestId("composer")).toHaveTextContent("");
  });

  it("keeps every chip a tappable button, so the row is keyboard reachable", () => {
    render(<Harness />);

    const chips = screen.getAllByRole("button");
    expect(chips).toHaveLength(SUGGESTED_PROMPTS.length);
    for (const chip of chips) {
      expect(chip).toHaveAttribute("type", "button");
    }
  });
});
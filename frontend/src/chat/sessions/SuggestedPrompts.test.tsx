/**
 * Starter-prompt chip tests.
 *
 * The chips are only worth having if tapping one actually puts the sentence in
 * the composer, so the assertions run against a real assistant-ui runtime and
 * read the composer state back out of it rather than asserting that a
 * callback fired.
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AssistantRuntimeProvider, useLocalRuntime } from "@assistant-ui/react";
import type { ChatModelAdapter } from "@assistant-ui/react";

import { SUGGESTED_PROMPTS } from "./starterPrompts";
import { SuggestedPrompts } from "./SuggestedPrompts";

function Harness({ seen }: { seen: string[] }) {
  const adapter: ChatModelAdapter = {
    run: async ({ messages }) => {
      const last = messages.at(-1);
      const text = last?.content.find((part) => part.type === "text");
      if (text && text.type === "text") seen.push(text.text);
      return { content: [{ type: "text", text: "" }] };
    },
  };
  const runtime = useLocalRuntime(adapter);
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <SuggestedPrompts />
    </AssistantRuntimeProvider>
  );
}

describe("SuggestedPrompts", () => {
  it("renders one chip per starter prompt", () => {
    render(<Harness seen={[]} />);

    for (const prompt of SUGGESTED_PROMPTS) {
      expect(screen.getByRole("button", { name: prompt })).toBeInTheDocument();
    }
  });

  it("sends the tapped prompt as the user's message", async () => {
    const seen: string[] = [];
    render(<Harness seen={seen} />);

    fireEvent.click(screen.getByRole("button", { name: SUGGESTED_PROMPTS[2] }));

    await waitFor(() => expect(seen).toEqual([SUGGESTED_PROMPTS[2]]));
  });

  it("keeps every chip a tappable button, so the row is keyboard reachable", () => {
    render(<Harness seen={[]} />);

    const chips = screen.getAllByRole("button");
    expect(chips).toHaveLength(SUGGESTED_PROMPTS.length);
    for (const chip of chips) {
      expect(chip).toHaveAttribute("type", "button");
    }
  });
});
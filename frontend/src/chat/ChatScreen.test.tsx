/**
 * ChatScreen smoke test.
 *
 * This exists because the screen once rendered a completely blank page and
 * every other check missed it: the module served 200, tsc passed, the
 * backend SSE contract was verified end to end, and 58 unit tests were
 * green. Nothing actually mounted the component. A misplaced
 * ErrorPrimitive.Message threw during render, React unmounted the tree,
 * and /chat, the default route, was white.
 *
 * So: render it and assert something is on screen. Cheap insurance against
 * exactly this class of failure.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, streamChat: vi.fn() };
});

import { ChatScreen } from "./ChatScreen";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ChatScreen", () => {
  it("mounts and shows the empty state, the composer and the disclaimer", async () => {
    render(
      <MemoryRouter>
        <ChatScreen />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Tell me how you feel")).toBeTruthy();
    expect(
      screen.getByPlaceholderText("Describe how you feel, in any language"),
    ).toBeTruthy();
    expect(screen.getByText(/Not a diagnosis/)).toBeTruthy();
  });
});

/**
 * Tests for the auth gate.
 *
 * The case that matters here is the difference between a token the server
 * refused and a server that could not be reached. The first means signed out.
 * The second means "still signed in, try again", and treating it as the first
 * signs the user out every time the connection drops.
 *
 * `getCurrentUser` is mocked at the client boundary, so the real ApiError
 * shape is what the provider branches on.
 */
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ApiError, getCurrentUser } from "../api/client";
import { clearToken } from "./token";
import { AuthProvider } from "./AuthContext";
import { RequireAuth } from "./RequireAuth";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, getCurrentUser: vi.fn() };
});

vi.mock("./token", () => ({
  getToken: vi.fn(() => "tkn-abc"),
  setToken: vi.fn(),
  clearToken: vi.fn(),
}));

// The consent gate does its own fetching and would block the child screen
// while it resolves. It is not what this file is about.
vi.mock("./ConsentContext", () => ({
  ConsentProvider: ({ children }: { children: ReactNode }) => children,
}));

const ME = {
  id: 7,
  email: "someone@example.com",
  latitude: 37.5665,
  longitude: 126.978,
  created_at: "2026-11-03T00:00:00Z",
  updated_at: "2026-11-03T00:00:00Z",
};

function renderGate() {
  return render(
    <MemoryRouter initialEntries={["/chat"]}>
      <AuthProvider>
        <Routes>
          <Route
            path="/chat"
            element={
              <RequireAuth>
                <p>chat screen</p>
              </RequireAuth>
            }
          />
          <Route path="/login" element={<p>login screen</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("the auth gate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("signs the user out when the server refuses the token", async () => {
    vi.mocked(getCurrentUser).mockRejectedValue(
      new ApiError(401, "Could not validate credentials"),
    );

    renderGate();

    expect(await screen.findByText("login screen")).toBeTruthy();
    // The token is dead, so it goes. Left in place it fails every request.
    expect(clearToken).toHaveBeenCalled();
  });

  it("keeps the session when the server cannot be reached", async () => {
    // What `fetch` throws when nothing is listening: a TypeError, not an
    // ApiError, and not a verdict on the token.
    vi.mocked(getCurrentUser).mockRejectedValue(new TypeError("Failed to fetch"));

    renderGate();

    expect(await screen.findByText("The server is not answering")).toBeTruthy();
    expect(clearToken).not.toHaveBeenCalled();
    // And it does not pretend the user is signed out either.
    expect(screen.queryByText("login screen")).toBeNull();
  });

  it("signs the user back in when the retry succeeds", async () => {
    vi.mocked(getCurrentUser).mockRejectedValueOnce(new TypeError("Failed to fetch"));
    vi.mocked(getCurrentUser).mockResolvedValueOnce(ME);

    renderGate();

    const retry = await screen.findByRole("button", { name: "Try again" });
    fireEvent.click(retry);

    await waitFor(() => {
      expect(screen.getByText("chat screen")).toBeTruthy();
    });
    expect(clearToken).not.toHaveBeenCalled();
  });

  it("signs the user in when the token is still good", async () => {
    vi.mocked(getCurrentUser).mockResolvedValue(ME);

    renderGate();

    expect(await screen.findByText("chat screen")).toBeTruthy();
    expect(clearToken).not.toHaveBeenCalled();
  });
});

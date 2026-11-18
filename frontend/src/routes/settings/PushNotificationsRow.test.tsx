import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const push = vi.hoisted(() => ({
  getPushState: vi.fn(),
  enablePush: vi.fn(),
  disablePush: vi.fn(),
}));
vi.mock("../../utils/push", async () => {
  const actual = await vi.importActual<typeof import("../../utils/push")>("../../utils/push");
  return { ...actual, ...push };
});

import { PushNotConfiguredError } from "../../utils/push";
import { PushNotificationsRow } from "./PushNotificationsRow";

const toggle = () => screen.getByRole("switch", { name: "Push notifications" });

beforeEach(() => {
  vi.clearAllMocks();
});

describe("PushNotificationsRow", () => {
  it("shows the unsupported explanation and disables the switch", async () => {
    push.getPushState.mockResolvedValue("unsupported");
    render(<PushNotificationsRow />);
    expect(await screen.findByText(/cannot receive push/i)).toBeInTheDocument();
    expect(toggle()).toBeDisabled();
  });

  it("explains a blocked permission and disables the switch", async () => {
    push.getPushState.mockResolvedValue("denied");
    render(<PushNotificationsRow />);
    expect(await screen.findByText(/blocked in your browser settings/i)).toBeInTheDocument();
    expect(toggle()).toBeDisabled();
  });

  it("turns on through enablePush and reflects the new state", async () => {
    push.getPushState.mockResolvedValueOnce("off").mockResolvedValueOnce("on");
    push.enablePush.mockResolvedValue(undefined);
    render(<PushNotificationsRow />);

    fireEvent.click(await screen.findByRole("switch", { name: "Push notifications" }));

    await waitFor(() => expect(push.enablePush).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/even when the app is closed/i)).toBeInTheDocument();
    expect(toggle()).toBeChecked();
  });

  it("turns off through disablePush", async () => {
    push.getPushState.mockResolvedValueOnce("on").mockResolvedValueOnce("off");
    push.disablePush.mockResolvedValue(undefined);
    render(<PushNotificationsRow />);

    fireEvent.click(await screen.findByRole("switch", { name: "Push notifications" }));

    await waitFor(() => expect(push.disablePush).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/only while the app is open/i)).toBeInTheDocument();
  });

  it("says plainly when the server is not configured", async () => {
    push.getPushState.mockResolvedValue("off");
    push.enablePush.mockRejectedValue(new PushNotConfiguredError());
    render(<PushNotificationsRow />);

    fireEvent.click(await screen.findByRole("switch", { name: "Push notifications" }));

    expect(await screen.findByText(/not set up on the server yet/i)).toBeInTheDocument();
    expect(toggle()).toBeDisabled();
  });

  it("shows the error message when enabling fails for another reason", async () => {
    push.getPushState.mockResolvedValue("off");
    push.enablePush.mockRejectedValue(new Error("Network went away"));
    render(<PushNotificationsRow />);

    fireEvent.click(await screen.findByRole("switch", { name: "Push notifications" }));

    expect(await screen.findByText("Network went away")).toBeInTheDocument();
  });
});

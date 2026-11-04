/**
 * The export and delete screens.
 *
 * Both are privacy rights, so both have to be honest about what they do: the
 * export says the file has been downloaded, the delete says it cannot be
 * undone and asks twice before it does anything.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { DeleteDataScreen, ExportDataScreen, StoredDataScreen } from "./Screens";
import type { PolicyDocument } from "../../api/consent";

const policy = (overrides: Partial<PolicyDocument> = {}): PolicyDocument => ({
  title: "개인정보 처리방침",
  version: "2026-10-19-draft1",
  status: "draft",
  requires_legal_review: true,
  operator: "Pollen Health Co.",
  operator_name: "Pollen Health Co.",
  operator_registration_number: "123-45-67890",
  operator_named: true,
  sections: [{ heading: "수집·이용 목적", body: ["symptom triage"] }],
  required_notice_items: ["수집·이용 목적"],
  ...overrides,
});

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("ExportDataScreen", () => {
  it("downloads the file and says so", async () => {
    const onExport = vi.fn().mockResolvedValue(undefined);
    render(<ExportDataScreen onExport={onExport} />);

    fireEvent.click(screen.getByRole("button", { name: "Download my data" }));

    await waitFor(() => expect(onExport).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/downloaded/i)).toBeInTheDocument();
  });

  it("says the export failed instead of pretending it worked", async () => {
    const onExport = vi.fn().mockRejectedValue(new Error("server said no"));
    render(<ExportDataScreen onExport={onExport} />);

    fireEvent.click(screen.getByRole("button", { name: "Download my data" }));

    expect(await screen.findByText(/export failed/i)).toBeInTheDocument();
    expect(screen.getByText("server said no")).toBeInTheDocument();
  });
});

describe("DeleteDataScreen", () => {
  it("asks before it deletes anything", async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(<DeleteDataScreen onDelete={onDelete} />);

    fireEvent.click(screen.getByRole("button", { name: "Delete my account" }));

    // The first tap only asks.
    expect(onDelete).not.toHaveBeenCalled();
    expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /yes, delete everything/i }));

    await waitFor(() => expect(onDelete).toHaveBeenCalledTimes(1));
  });

  it("lets the user keep their data", async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(<DeleteDataScreen onDelete={onDelete} />);

    fireEvent.click(screen.getByRole("button", { name: "Delete my account" }));
    fireEvent.click(screen.getByRole("button", { name: /keep my data/i }));

    expect(onDelete).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Delete my account" })).toBeInTheDocument();
  });

  it("says nothing was deleted when the server refuses", async () => {
    const onDelete = vi.fn().mockRejectedValue(new Error("nope"));
    render(<DeleteDataScreen onDelete={onDelete} />);

    fireEvent.click(screen.getByRole("button", { name: "Delete my account" }));
    fireEvent.click(screen.getByRole("button", { name: /yes, delete everything/i }));

    expect(await screen.findByText(/nothing was deleted/i)).toBeInTheDocument();
  });
});

describe("StoredDataScreen", () => {
  it("lists what the policy says is stored", () => {
    render(<StoredDataScreen policy={policy()} policyError={null} onRetry={vi.fn()} />);

    expect(screen.getByText("수집·이용 목적")).toBeInTheDocument();
    expect(screen.getByText("symptom triage")).toBeInTheDocument();
  });

  it("says the policy could not be loaded rather than showing an empty page", () => {
    const onRetry = vi.fn();
    render(<StoredDataScreen policy={null} policyError="boom" onRetry={onRetry} />);

    expect(screen.getByText(/could not load the policy/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("warns when no operator is named", () => {
    render(
      <StoredDataScreen
        policy={policy({ operator_named: false, operator_name: null })}
        policyError={null}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText(/no operator is named yet/i)).toBeInTheDocument();
  });
});

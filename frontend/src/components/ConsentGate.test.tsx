/**
 * The consent step in front of the chat.
 *
 * The gate is the part of the app a user reads once and has to understand, so
 * the assertions are about what is on screen rather than about the calls: the
 * four items 제15조② requires, the fact that symptom text leaves the server,
 * and the fact that nobody is reading it.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import type { PolicyDocument } from "../api/consent";

const NOTICE_ITEMS = [
  "수집·이용 목적",
  "수집하는 민감정보의 항목",
  "보유 및 이용 기간",
  "동의를 거부할 권리와 거부 시 불이익",
];

const policy = (): PolicyDocument => ({
  title: "개인정보 처리방침 (초안)",
  version: "2026-10-19-draft1",
  status: "draft",
  requires_legal_review: true,
  operator: "Pollen Health Co. (사업자등록번호: 123-45-67890)",
  operator_name: "Pollen Health Co.",
  operator_registration_number: "123-45-67890",
  operator_named: true,
  sections: [],
  required_notice_items: NOTICE_ITEMS,
});

const consent = vi.hoisted(() => ({
  granted: false,
  policy: null as PolicyDocument | null,
  setGranted: vi.fn(),
}));

vi.mock("../auth/ConsentContext", () => ({
  useConsent: () => ({
    status: "ready",
    consent: consent.granted
      ? {
          purpose: "health_data_processing",
          granted: true,
          version: "2026-10-19-draft1",
          granted_at: "2026-10-20T00:00:00Z",
          withdrawn_at: null,
          policy_version: "2026-10-19-draft1",
          basis: "개인정보 보호법 제23조제1항제1호, 제15조제2항",
        }
      : null,
    policy: consent.policy,
    granted: consent.granted,
    error: null,
    refresh: vi.fn(),
    setGranted: consent.setGranted,
  }),
}));

import { ConsentGate } from "./ConsentGate";

const renderGate = () =>
  render(
    <MemoryRouter>
      <ConsentGate>
        <p>the chat</p>
      </ConsentGate>
    </MemoryRouter>,
  );

beforeEach(() => {
  consent.granted = false;
  consent.policy = policy();
  consent.setGranted.mockReset();
  consent.setGranted.mockResolvedValue(undefined);
});

describe("ConsentGate", () => {
  it("keeps the chat closed until the agreement is given", () => {
    renderGate();

    expect(screen.queryByText("the chat")).toBeNull();
    expect(screen.getByText("Before you describe your symptoms")).toBeTruthy();
  });

  it("carries the four items the law asks to be disclosed first", () => {
    renderGate();

    for (const item of consent.policy?.required_notice_items ?? []) {
      expect(screen.getByText(item)).toBeTruthy();
    }
  });

  it("says that the symptom text leaves the server", () => {
    renderGate();

    expect(screen.getByText(/sent from our server to the language model provider/)).toBeTruthy();
    expect(screen.getByText(/Your email, your/)).toBeTruthy();
  });

  it("says that nobody is reading and where the crisis path goes", () => {
    renderGate();

    expect(screen.getByText(/Nobody reads your messages/)).toBeTruthy();
    expect(screen.getByText(/1333/)).toBeTruthy();
    expect(screen.getByText(/1393/)).toBeTruthy();
  });

  it("records the agreement when the user agrees", () => {
    renderGate();

    fireEvent.click(screen.getByRole("button", { name: "Agree and continue" }));

    expect(consent.setGranted).toHaveBeenCalledWith(true);
  });

  it("lets the chat through once the agreement is in place", () => {
    consent.granted = true;
    renderGate();

    expect(screen.getByText("the chat")).toBeTruthy();
    expect(screen.queryByText("Before you describe your symptoms")).toBeNull();
  });

  it("will not ask for an agreement it cannot show the terms of", () => {
    consent.policy = null;
    renderGate();

    expect(screen.getByText("Could not load the privacy notice")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Agree and continue" })).toBeNull();
  });
});

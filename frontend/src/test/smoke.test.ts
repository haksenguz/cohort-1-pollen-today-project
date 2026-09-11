import { describe, it, expect } from "vitest";

describe("vitest setup", () => {
  it("runs and matches toBeInTheDocument via jest-dom", () => {
    const el = document.createElement("div");
    el.textContent = "hello";
    document.body.appendChild(el);
    expect(el).toBeInTheDocument();
    expect(el).toHaveTextContent("hello");
  });
});

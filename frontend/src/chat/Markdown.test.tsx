import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Markdown } from "./Markdown";

describe("Markdown", () => {
  it("renders bold as a strong element", () => {
    const { container } = render(<Markdown text="Take **antihistamine** now." />);

    const strong = container.querySelector("strong");
    expect(strong?.textContent).toBe("antihistamine");
  });

  it("renders a bullet list as list items", () => {
    const { container } = render(
      <Markdown text={"- peanut\n- shellfish\n- sesame"} />,
    );

    const items = container.querySelectorAll("li");
    expect(items).toHaveLength(3);
    expect(items[0].textContent).toBe("peanut");
    expect(items[2].textContent).toBe("sesame");
  });

  it("keeps a single newline as a line break", () => {
    const { container } = render(
      <Markdown text={"First line\nSecond line"} />,
    );

    expect(container.querySelector("br")).not.toBeNull();
    expect(container.textContent).toContain("First line");
    expect(container.textContent).toContain("Second line");
  });

  it("leaves a plain text message unchanged", () => {
    const { container } = render(<Markdown text="Your symptoms sound mild." />);

    expect(container.textContent).toBe("Your symptoms sound mild.");
    expect(container.querySelector("p")).not.toBeNull();
  });

  it("opens a safe link in a new tab with a safe rel", () => {
    const { container } = render(
      <Markdown text="See [the pollen count](https://example.com/pollen)." />,
    );

    const link = container.querySelector("a");
    expect(link?.getAttribute("href")).toBe("https://example.com/pollen");
    expect(link?.getAttribute("target")).toBe("_blank");
    expect(link?.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("makes a javascript link inert", () => {
    const { container } = render(
      <Markdown text="[click me](javascript:alert(1))" />,
    );

    const link = container.querySelector("a");
    expect(link).toBeNull();
    expect(container.innerHTML).not.toContain("javascript:");
    // The words survive even though the link does not.
    expect(container.textContent).toContain("click me");
  });

  it("makes a javascript link with a stray tab inert", () => {
    const { container } = render(
      <Markdown text={"[click me](java\tscript:alert(1))"} />,
    );

    // A tab breaks the link syntax, so the text stays text and nothing
    // becomes clickable.
    expect(container.querySelector("a")).toBeNull();
    expect(container.querySelector("[href]")).toBeNull();
  });

  it("makes a javascript link with a stray backslash inert", () => {
    const { container } = render(
      <Markdown text={"[click me](java\\tscript:alert(1))"} />,
    );

    expect(container.innerHTML).not.toContain("script:");
    expect(container.querySelector("a")).toBeNull();
  });

  it("renders a script payload as inert text", () => {
    const marker = "__pwned__";
    (window as unknown as Record<string, unknown>)[marker] = false;
    const payload = `<script>window.${marker} = true;</script>`;

    const { container } = render(<Markdown text={payload} />);

    expect(container.querySelector("script")).toBeNull();
    expect((window as unknown as Record<string, unknown>)[marker]).toBe(false);
  });

  it("does not load an image from the model", () => {
    const { container } = render(
      <Markdown text="![a pollen chart](https://example.com/chart.png)" />,
    );

    expect(container.querySelector("img")).toBeNull();
    expect(container.innerHTML).not.toContain("example.com/chart.png");
  });
});

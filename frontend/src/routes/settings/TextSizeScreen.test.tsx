/**
 * The Settings text size control (bugs.md F4, WCAG 2.2 SC 1.4.4).
 *
 * The screen is deliberately dumb — it renders the steps it is handed and
 * reports a pick — so what is worth pinning here is the path a pick takes:
 * through the preference hook to the document and to storage. Also the two
 * accessibility traps a segmented control falls into: a group with no
 * accessible name, and reading a second activation of the chosen step as
 * "no choice".
 *
 * Keyboard behaviour below is the ToggleGroup primitive's own contract, not
 * what the ARIA radio pattern would ideally do: one tab stop for the whole
 * group, arrow keys move focus without selecting, Enter or Space selects the
 * focused option. Asserting arrows also select would be asserting a behaviour
 * this shared primitive does not have.
 */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TEXT_SIZE_STORAGE_KEY, readTextSize, useTextSize } from "../../prefs/textSize";
import { TextSizeScreen } from "./Screens";

/** The page owns the state and hands the screen a step and a setter. */
function Harness() {
  const { step, setStep } = useTextSize();
  return <TextSizeScreen step={step} onChange={setStep} />;
}

const renderScreen = () => render(<Harness />);

const group = () => screen.getByRole("radiogroup");
const option = (label: string) =>
  within(group()).getByRole("radio", { name: new RegExp(`^${label}, \\d+%$`) });

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
  document.documentElement.style.fontSize = "";
});

describe("naming the control", () => {
  it("names the group from the label on screen", () => {
    renderScreen();

    const labelledBy = group().getAttribute("aria-labelledby");

    expect(labelledBy).toBeTruthy();
    expect(document.getElementById(labelledBy ?? "")).toHaveTextContent("Text size");
    expect(group()).toHaveAccessibleName("Text size");
    expect(within(group()).getAllByRole("radio").map((o) => o.textContent)).toEqual([
      "Normal",
      "Large",
      "Larger",
      "Largest",
    ]);
  });

  it("starts each accessible name with the label on screen", () => {
    renderScreen();

    for (const radio of within(group()).getAllByRole("radio")) {
      // WCAG 2.5.3 Label in Name: speech input has to match what is drawn.
      expect(radio).toHaveAccessibleName(new RegExp(`^${radio.textContent}, \\d+%$`));
    }
  });

  it("takes one tab stop for the whole group", () => {
    renderScreen();

    const tabbable = [group(), ...within(group()).getAllByRole("radio")].filter(
      (el) => el.getAttribute("tabindex") === "0",
    );

    expect(tabbable).toEqual([group()]);
  });
});

describe("changing the size", () => {
  it("applies the picked step to the document and stores it", () => {
    renderScreen();

    fireEvent.click(option("Largest"));

    expect(document.documentElement.style.fontSize).toBe("200%");
    expect(readTextSize().id).toBe("largest");
    expect(option("Largest")).toHaveAttribute("aria-checked", "true");
  });

  it("opens on the step that was stored, not on the first one", () => {
    localStorage.setItem(TEXT_SIZE_STORAGE_KEY, "larger");
    renderScreen();

    expect(option("Larger")).toHaveAttribute("aria-checked", "true");
    expect(option("Normal")).toHaveAttribute("aria-checked", "false");
  });

  it("keeps the chosen step when it is picked again", () => {
    // The primitive reports an empty string for a second activation of the
    // pressed item. Reading that as a choice would silently drop the reader
    // back to Normal.
    renderScreen();

    fireEvent.click(option("Largest"));
    fireEvent.click(option("Largest"));

    expect(option("Largest")).toHaveAttribute("aria-checked", "true");
    expect(readTextSize().id).toBe("largest");
    expect(document.documentElement.style.fontSize).toBe("200%");
  });

  it("puts the size back to normal through Restore defaults", () => {
    localStorage.setItem(TEXT_SIZE_STORAGE_KEY, "largest");
    renderScreen();

    fireEvent.click(screen.getByRole("button", { name: "Restore defaults" }));

    expect(document.documentElement.style.fontSize).toBe("100%");
    expect(readTextSize().id).toBe("normal");
    expect(option("Normal")).toHaveAttribute("aria-checked", "true");
  });
});

describe("changing the size from the keyboard", () => {
  it("reaches the group, walks it and takes the option it lands on", async () => {
    const user = userEvent.setup();
    renderScreen();

    await user.tab();
    expect(document.activeElement).toBe(option("Normal"));

    await user.keyboard("{ArrowRight}");
    expect(document.activeElement).toBe(option("Large"));

    await user.keyboard("{Enter}");

    expect(option("Large")).toHaveAttribute("aria-checked", "true");
    expect(readTextSize().id).toBe("large");
    expect(document.documentElement.style.fontSize).toBe("125%");
  });
});
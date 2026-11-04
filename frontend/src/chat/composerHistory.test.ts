import { describe, expect, it } from "vitest";

import {
  DRAFT,
  historyValue,
  partText,
  sentMessageTexts,
  stepHistory,
} from "./composerHistory";

/** The shape assistant-ui hands back, trimmed to what we actually read. */
const userMessage = (text: string) => ({
  role: "user",
  parts: [{ type: "text", text }],
});

describe("partText", () => {
  it("joins the text parts in order", () => {
    expect(
      partText([
        { type: "text", text: "my eyes are " },
        { type: "reasoning", text: "should be ignored" },
        { type: "text", text: "itchy" },
      ]),
    ).toBe("my eyes are itchy");
  });

  it("returns null rather than empty when the parts are unreadable", () => {
    /* This is the shape of the project's signature bug: an unreadable value
       turning into a fine-looking one. null means "drop it", "" would mean
       "here is a blank message to arrow onto". */
    expect(partText(undefined)).toBeNull();
    expect(partText("not an array")).toBeNull();
    expect(partText({ length: 2 })).toBeNull();
  });

  it("skips parts it cannot read instead of failing the whole message", () => {
    expect(partText([null, "junk", { type: "text", text: 42 }, { type: "text", text: "ok" }])).toBe(
      "ok",
    );
  });
});

describe("sentMessageTexts", () => {
  it("returns only what the user sent, oldest first", () => {
    const messages = [
      userMessage("first"),
      { role: "assistant", parts: [{ type: "text", text: "a reply" }] },
      userMessage("second"),
    ];
    expect(sentMessageTexts(messages)).toEqual(["first", "second"]);
  });

  it("drops an unreadable message instead of recalling a blank", () => {
    const messages = [
      userMessage("real"),
      { role: "user", parts: "broken" },
      { role: "user" },
      null,
      "junk",
      userMessage("  "),
    ];
    expect(sentMessageTexts(messages)).toEqual(["real"]);
  });

  it("returns an empty list for a non-array rather than throwing", () => {
    expect(sentMessageTexts(undefined)).toEqual([]);
    expect(sentMessageTexts(null)).toEqual([]);
  });

  it("never yields an entry that would recall as empty", () => {
    const messages = [userMessage(""), userMessage("   "), userMessage("\n\t")];
    expect(sentMessageTexts(messages)).toEqual([]);
  });
});

describe("stepHistory", () => {
  const history = ["oldest", "middle", "newest"];

  it("walks up from the draft to the newest send first", () => {
    expect(stepHistory(history, DRAFT, -1)).toBe(2);
  });

  it("keeps walking up to older sends", () => {
    expect(stepHistory(history, 2, -1)).toBe(1);
    expect(stepHistory(history, 1, -1)).toBe(0);
  });

  it("clamps at the oldest instead of wrapping", () => {
    expect(stepHistory(history, 0, -1)).toBe(0);
  });

  it("walks down and returns to the draft past the newest", () => {
    expect(stepHistory(history, 0, 1)).toBe(1);
    expect(stepHistory(history, 1, 1)).toBe(2);
    expect(stepHistory(history, 2, 1)).toBe(DRAFT);
  });

  it("stays on the draft when pressing down at the draft", () => {
    expect(stepHistory(history, DRAFT, 1)).toBe(DRAFT);
  });

  it("cannot move at all with no history", () => {
    expect(stepHistory([], DRAFT, -1)).toBe(DRAFT);
    expect(stepHistory([], 3, 1)).toBe(DRAFT);
  });
});

describe("historyValue", () => {
  const history = ["oldest", "newest"];

  it("resolves the draft sentinel to the draft text", () => {
    expect(historyValue(history, DRAFT, "half typed")).toBe("half typed");
  });

  it("resolves an index to its message", () => {
    expect(historyValue(history, 0, "draft")).toBe("oldest");
    expect(historyValue(history, 1, "draft")).toBe("newest");
  });

  it("falls back to the draft for an index we cannot read", () => {
    /* Never undefined and never "". A stale index has to land somewhere the
       user can see and fix, not blank the composer. */
    expect(historyValue(history, 9, "draft")).toBe("draft");
    expect(historyValue(history, -7, "draft")).toBe("draft");
    expect(historyValue([], 0, "draft")).toBe("draft");
  });
});
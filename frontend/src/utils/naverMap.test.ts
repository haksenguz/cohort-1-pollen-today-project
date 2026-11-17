import { describe, expect, it } from "vitest";

import { naverMapSearchUrl } from "./naverMap";

describe("naverMapSearchUrl", () => {
  it("encodes name and address into a Naver Map search URL", () => {
    expect(naverMapSearchUrl("Seoul Clinic", "12 Sejong-daero")).toBe(
      `https://map.naver.com/p/search/${encodeURIComponent("Seoul Clinic 12 Sejong-daero")}`,
    );
  });

  it("uses the name alone when the address is missing or blank", () => {
    const expected = `https://map.naver.com/p/search/${encodeURIComponent("Han River Hospital")}`;
    expect(naverMapSearchUrl("Han River Hospital")).toBe(expected);
    expect(naverMapSearchUrl("Han River Hospital", null)).toBe(expected);
    expect(naverMapSearchUrl("Han River Hospital", "   ")).toBe(expected);
  });

  it("returns null when there is no name to search for", () => {
    expect(naverMapSearchUrl("")).toBeNull();
    expect(naverMapSearchUrl("   ", "Somewhere")).toBeNull();
  });

  it("keeps hostile text inside the query and never changes the origin", () => {
    const url = naverMapSearchUrl('x" onmouseover="alert(1)', "a/b?c=d&e#f");
    expect(url).not.toBeNull();
    const parsed = new URL(url as string);
    expect(parsed.origin).toBe("https://map.naver.com");
    expect(parsed.pathname).toBe("/p/search/" + encodeURIComponent('x" onmouseover="alert(1)') + "%20" + encodeURIComponent("a/b?c=d&e#f"));
    expect(parsed.search).toBe("");
    expect(parsed.hash).toBe("");
  });
});

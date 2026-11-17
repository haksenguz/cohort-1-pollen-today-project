/**
 * Builds the "Open in Naver Map" search link for a clinic or hospital.
 *
 * The URL is assembled here from a fixed origin. The only model- or
 * provider-written text that reaches it is the name and address, and both are
 * passed through encodeURIComponent. Nothing else is taken from the caller.
 */
const NAVER_MAP_SEARCH = "https://map.naver.com/p/search/";

/**
 * Returns the Naver Map search URL for a place, or null when there is no name
 * to search for. A missing address is left out rather than sent as "null".
 */
export function naverMapSearchUrl(name: string, address?: string | null): string | null {
  const place = name.trim();
  if (place === "") return null;
  const extra = typeof address === "string" ? address.trim() : "";
  const query = extra === "" ? place : `${place} ${extra}`;
  return `${NAVER_MAP_SEARCH}${encodeURIComponent(query)}`;
}

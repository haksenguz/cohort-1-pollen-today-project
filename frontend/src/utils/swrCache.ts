import { useEffect, useRef, useState } from "react";

/**
 * A small stale-while-revalidate cache backed by localStorage.
 *
 * The Today screen waits on slow providers (pollen is published three times a
 * day, and weather can take 8 seconds to time out). Showing the last reading
 * at once and swapping in the new one when it lands beats a skeleton. Entries
 * older than `maxAgeMs` are dropped so a very old reading never passes for
 * today's. A failed refresh keeps what is on screen.
 */

const PREFIX = "swr:v1:";
const inflight = new Map<string, Promise<unknown>>();

type Entry<T> = { data: T; at: number };

export function readCache<T>(key: string, maxAgeMs: number): Entry<T> | null {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    if (!raw) return null;
    const entry = JSON.parse(raw) as Entry<T>;
    if (typeof entry.at !== "number" || Date.now() - entry.at > maxAgeMs) {
      localStorage.removeItem(PREFIX + key);
      return null;
    }
    return entry;
  } catch {
    return null;
  }
}

function writeCache<T>(key: string, data: T): number {
  const at = Date.now();
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify({ data, at } satisfies Entry<T>));
  } catch {
    // Storage full or blocked: the screen still works, it just will not cache.
  }
  return at;
}

/** Fetch and cache. Callers asking for the same key share one request. */
export function fetchAndCache<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const running = inflight.get(key) as Promise<T> | undefined;
  if (running) return running;
  const promise = fetcher()
    .then((data) => {
      writeCache(key, data);
      return data;
    })
    .finally(() => inflight.delete(key));
  inflight.set(key, promise);
  return promise;
}

export type SwrState<T> = {
  data: T | null;
  error: unknown;
  /** True only while there is nothing at all to show. */
  loading: boolean;
  /** True while a fetch runs behind data that is already on screen. */
  refreshing: boolean;
  updatedAt: number | null;
};

export function useSwr<T>(
  key: string | null,
  fetcher: () => Promise<T>,
  { freshMs, maxAgeMs }: { freshMs: number; maxAgeMs: number },
): SwrState<T> {
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const [state, setState] = useState<SwrState<T>>(() => initial<T>(key, maxAgeMs));

  useEffect(() => {
    if (key === null) return;
    let cancelled = false;
    const cached = readCache<T>(key, maxAgeMs);
    // oxlint-disable-next-line react/set-state-in-effect -- load the cached reading when the key changes
    setState({
      data: cached?.data ?? null,
      error: null,
      loading: cached === null,
      refreshing: false,
      updatedAt: cached?.at ?? null,
    });
    if (cached && Date.now() - cached.at < freshMs) return;

    setState((s) => ({ ...s, refreshing: s.data !== null }));
    fetchAndCache(key, () => fetcherRef.current())
      .then((data) => {
        if (cancelled) return;
        setState({ data, error: null, loading: false, refreshing: false, updatedAt: Date.now() });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setState((s) => ({ ...s, error, loading: false, refreshing: false }));
      });
    return () => {
      cancelled = true;
    };
  }, [key, freshMs, maxAgeMs]);

  return state;
}

function initial<T>(key: string | null, maxAgeMs: number): SwrState<T> {
  const cached = key === null ? null : readCache<T>(key, maxAgeMs);
  return {
    data: cached?.data ?? null,
    error: null,
    loading: key !== null && cached === null,
    refreshing: false,
    updatedAt: cached?.at ?? null,
  };
}

/** "just now", "12 min ago", "3 h ago". */
export function ageLabel(updatedAt: number | null): string {
  if (updatedAt === null) return "";
  const mins = Math.floor((Date.now() - updatedAt) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  return `${Math.floor(mins / 60)} h ago`;
}

/** Test helper: forget requests still in flight and every cached reading. */
export function resetSwrCache(): void {
  inflight.clear();
  try {
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith(PREFIX)) localStorage.removeItem(key);
    }
  } catch {
    // Nothing to clear.
  }
}

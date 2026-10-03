/**
 * Vitest setup: import jest-dom matchers so component tests can use
 * `toBeInTheDocument`, `toHaveTextContent`, etc.
 */
import "@testing-library/jest-dom/vitest";

/**
 * jsdom does not implement ResizeObserver, which assistant-ui's thread
 * viewport observes to drive auto-scroll. Without this stub any test that
 * mounts ChatScreen dies with "ResizeObserver is not defined" before it can
 * assert anything. The stub is inert on purpose: tests here assert that a
 * screen mounts and shows the right copy, not how it scrolls.
 */
if (!("ResizeObserver" in globalThis)) {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
}

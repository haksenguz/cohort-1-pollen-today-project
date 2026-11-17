import { useEffect, useRef, useState, type RefObject } from "react";

/**
 * Whether the floating header and tab bar should show.
 *
 * They slide away while the user scrolls down and come back on any scroll up,
 * the way the Pasar app behaves. Scroll events do not bubble, so one capture
 * listener on the app frame hears every scroller inside it (the page stage
 * and the chat thread alike) without each screen having to opt in.
 *
 * `locked` keeps the chrome visible, for screens where hiding the tab bar
 * would strand the composer. Changing route also brings it back.
 */
export function useChromeVisibility(
  frame: RefObject<HTMLElement | null>,
  routeKey: string,
  locked: boolean,
): boolean {
  const [visible, setVisible] = useState(true);
  const last = useRef(new WeakMap<EventTarget, number>());

  useEffect(() => {
    setVisible(true);
  }, [routeKey, locked]);

  useEffect(() => {
    const el = frame.current;
    if (!el || locked) return;

    const onScroll = (event: Event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const top = target.scrollTop;
      const prev = last.current.get(target) ?? 0;
      const delta = top - prev;
      if (Math.abs(delta) < 8) return;
      last.current.set(target, top);
      // Near the top there is nothing to get out of the way of.
      setVisible(top < 48 || delta < 0);
    };

    el.addEventListener("scroll", onScroll, { capture: true, passive: true });
    return () => el.removeEventListener("scroll", onScroll, { capture: true });
  }, [frame, locked]);

  return visible;
}

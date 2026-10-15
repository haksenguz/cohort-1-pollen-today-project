import * as React from "react"
import { Toaster as Sonner, type ToasterProps } from "sonner"

import { cn } from "@/lib/utils"

/**
 * The app toggles dark mode with `data-theme="dark"` on <html> (see
 * TopHeader.tsx), not the `.dark` class that shadcn's stock next-themes
 * wiring expects — and this app has no next-themes provider at all. So the
 * stock useTheme() call has nothing to read. This resolves the same
 * attribute the theme switcher writes, falling back to the OS preference
 * while the attribute is absent (the "system" preference).
 *
 * This is needed because sonner's `theme` prop drives real CSS classes on
 * the toast chrome; it is not something a token swap can cover. The toast
 * *colours* below still come from CSS variables, so they follow the theme
 * on their own.
 */
function useResolvedTheme(): "light" | "dark" {
  const [theme, setTheme] = React.useState<"light" | "dark">(() => {
    if (typeof document === "undefined") return "light"
    const pref = document.documentElement.getAttribute("data-theme")
    if (pref === "dark" || pref === "light") return pref
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light"
  })

  React.useEffect(() => {
    const media = window.matchMedia?.("(prefers-color-scheme: dark)")
    const sync = () => {
      const pref = document.documentElement.getAttribute("data-theme")
      setTheme(
        pref === "dark" || pref === "light"
          ? pref
          : media?.matches
            ? "dark"
            : "light"
      )
    }

    // TopHeader flips data-theme on <html> without a re-render here.
    const observer = new MutationObserver(sync)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    })
    media?.addEventListener("change", sync)

    return () => {
      observer.disconnect()
      media?.removeEventListener("change", sync)
    }
  }, [])

  return theme
}

/**
 * The app's single notification surface. Mount it exactly once, near the
 * root (AppShell), and let every caller fire toasts through `toast()`.
 *
 * Top-centre by default: the bottom of the screen belongs to the tab nav
 * and to primary actions, which is exactly where the hand-rolled
 * .pwa-toast used to sit on top of.
 */
function Toaster({ className, ...props }: ToasterProps) {
  const theme = useResolvedTheme()

  return (
    <Sonner
      theme={theme}
      className={cn("toaster group", className)}
      position="top-center"
      offset={{ top: "6.5rem" }}
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-popover group-[.toaster]:text-popover-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
          description: "group-[.toast]:text-muted-foreground",
          actionButton:
            "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton:
            "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
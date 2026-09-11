/**
 * Top-level wrapper that mounts the PWA UX: update prompt, install prompt,
 * offline banner. Render once inside App; the components self-hide when
 * not relevant.
 */
import { UpdatePrompt } from "./UpdatePrompt";
import { InstallPrompt } from "./InstallPrompt";
import { OfflineBanner } from "./OfflineBanner";

export function PwaSetup() {
  return (
    <>
      <OfflineBanner />
      <InstallPrompt />
      <UpdatePrompt />
    </>
  );
}
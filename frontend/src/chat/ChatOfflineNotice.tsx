/**
 * The offline notice inside the chat (bugs.md C10).
 *
 * The app has a global toast for going offline, but a toast fades and a toast
 * can be missed. Someone about to type a symptom needs to know before they
 * type it, so the chat screen says it in place.
 */
import { WifiOff } from "lucide-react";
import { useOnlineStatus } from "./useOnlineStatus";

export function ChatOfflineNotice() {
  const online = useOnlineStatus();
  if (online) return null;

  return (
    <div className="aui-offline" role="status">
      <WifiOff aria-hidden="true" className="aui-offline-icon" />
      <p className="aui-offline-text">
        You are offline. Messages cannot be sent until the connection is back.
      </p>
    </div>
  );
}

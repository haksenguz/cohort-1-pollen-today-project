/**
 * The consent step in front of the chat.
 *
 * The chat is where symptom text goes, and symptom text is 민감정보 under
 * 제23조, so it may only be processed on a separate agreement (제15조). This
 * is that step: it states what the agreement covers, what leaves the device,
 * and who is actually reading, and it asks before the first symptom is typed.
 *
 * The copy is deliberately blunt about the limits. An app that reads like it
 * is staffed would be a lie, and a user who believes someone is watching them
 * is worse off than one who knows nobody is.
 */
import { useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

import { useConsent } from "../auth/ConsentContext";

export function ConsentGate({ children }: { children: ReactNode }) {
  const { status, granted, policy, setGranted, refresh } = useConsent();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  if (status === "loading") {
    return <div className="screen-loading">Loading…</div>;
  }

  if (granted) {
    return <>{children}</>;
  }

  // The four items have to be shown before consent is asked for, so a notice
  // without them is not a notice. If the policy cannot be read, the honest
  // answer is a retry, not a shortened agreement.
  if (policy === null) {
    return (
      <div className="stage flex flex-col gap-4">
        <Alert variant="destructive">
          <AlertTitle>Could not load the privacy notice</AlertTitle>
          <AlertDescription>
            The notice has to be on screen before you can agree to it. Nothing was
            recorded.
          </AlertDescription>
        </Alert>
        <Button variant="outline" className="min-h-11" onClick={() => void refresh()}>
          Try again
        </Button>
      </div>
    );
  }

  async function agree() {
    setFailure(null);
    setBusy(true);
    try {
      await setGranted(true);
    } catch (e) {
      setFailure(e instanceof Error ? e.message : "Could not record your agreement.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stage flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Before you describe your symptoms</CardTitle>
          <CardDescription>
            Answering allergy questions means processing what you type about your
            body. Korean privacy law (제23조) asks for your separate agreement
            before the app may do that, and it asks for the four points below
            first.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <section className="flex flex-col gap-2">
            <h3 className="text-sm font-medium">What you are agreeing to</h3>
            <ul className="flex list-disc flex-col gap-1 pl-5 text-sm text-muted-foreground">
              {policy.required_notice_items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>

          <Separator />

          <section className="flex flex-col gap-2">
            <h3 className="text-sm font-medium">What leaves this phone</h3>
            <p className="text-sm text-muted-foreground">
              The text you type in the chat is sent from our server to the
              language model provider that writes the answer. Your email, your
              password and your saved location are not sent. Everything else
              stays on our server.
            </p>
          </section>

          <Separator />

          <section className="flex flex-col gap-2">
            <h3 className="text-sm font-medium">Nobody is watching</h3>
            <p className="text-sm text-muted-foreground">
              This app is not staffed. Nobody reads your messages, and nobody
              here can send an ambulance for you. If you are struggling to
              breathe, call 1333 for emergency medical help, or 1393 for suicide
              prevention, before you wait for an app to answer.
            </p>
          </section>

          {failure ? (
            <Alert variant="destructive">
              <AlertTitle>Not recorded</AlertTitle>
              <AlertDescription>{failure}</AlertDescription>
            </Alert>
          ) : null}

          <div className="flex flex-col gap-2">
            <Button className="min-h-11" onClick={() => void agree()} disabled={busy}>
              {busy ? "Saving…" : "Agree and continue"}
            </Button>
            <Button variant="ghost" className="min-h-11" onClick={() => navigate("/today")}>
              Not now
            </Button>
            <p className="text-xs text-muted-foreground">
              You can withdraw this agreement at any time in Settings, under
              Privacy and data.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

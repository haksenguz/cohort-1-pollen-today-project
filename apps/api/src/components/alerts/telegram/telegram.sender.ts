import { Injectable, Logger } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { UpstreamUnavailableError } from "../../../libs/errors/app-error";

const TELEGRAM_API = "https://api.telegram.org";

/**
 * Posts a message to a Telegram chat or channel.
 *
 * With no TELEGRAM_BOT_TOKEN configured it logs instead of sending, so the
 * whole pipeline — scheduler, forecast read, idempotency check — can be
 * exercised end to end before the bot exists. A dry run that silently does
 * nothing would be worse than useless, so it says so at WARN.
 */
@Injectable()
export class TelegramSender {
  private readonly log = new Logger(TelegramSender.name);

  constructor(private readonly config: ConfigService) {}

  get enabled(): boolean {
    return Boolean(this.config.get<string>("TELEGRAM_BOT_TOKEN"));
  }

  async send(chatId: string, text: string): Promise<void> {
    const token = this.config.get<string>("TELEGRAM_BOT_TOKEN");

    if (!token) {
      this.log.warn(`DRY RUN (no bot token) → ${chatId}\n${text}`);
      return;
    }

    const res = await fetch(`${TELEGRAM_API}/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text,
        disable_web_page_preview: true,
      }),
    }).catch((err: unknown) => {
      throw new UpstreamUnavailableError(
        `Telegram unreachable: ${String(err)}`,
      );
    });

    if (!res.ok) {
      // Telegram puts the real reason in the body, not the status line.
      const body = await res.text().catch(() => "");
      throw new UpstreamUnavailableError(
        `Telegram rejected the send: HTTP ${res.status} ${body.slice(0, 200)}`,
      );
    }
  }
}

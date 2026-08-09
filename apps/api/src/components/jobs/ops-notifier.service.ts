import { Injectable, Logger } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { TelegramSender } from "../alerts/telegram/telegram.sender";

/**
 * Failure notifications to the private ops channel.
 *
 * Separate from alert delivery on purpose: an ops message is for us, is never
 * idempotency-checked, and must never be confused with something a subscriber
 * sees. Milestone at Week 3 is "ops channel receives a message when a job
 * fails, proved by deliberately breaking a job".
 */
@Injectable()
export class OpsNotifier {
  private readonly log = new Logger(OpsNotifier.name);

  constructor(
    private readonly telegram: TelegramSender,
    private readonly config: ConfigService,
  ) {}

  async jobFailed(jobName: string, error: string): Promise<void> {
    const chatId = this.config.get<string>("TELEGRAM_OPS_CHAT_ID");

    if (!chatId) {
      this.log.warn(
        `no TELEGRAM_OPS_CHAT_ID set — ${jobName} failure not reported`,
      );
      return;
    }

    await this.telegram.send(chatId, `⚠️ ${jobName} failed\n\n${error}`);
  }
}

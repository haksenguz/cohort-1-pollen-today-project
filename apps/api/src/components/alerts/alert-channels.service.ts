import { Injectable, Logger } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { Region } from "@pollen/contracts";
import { z } from "zod";

/**
 * Region → Telegram channel.
 *
 * Channel names are configuration, never code (CONVENTIONS §11). One env var
 * holds a JSON object so adding a region is a deploy, not a release:
 *
 *   TELEGRAM_CHANNELS={"SEOUL":"@pollen_seoul","BUSAN":"@pollen_busan"}
 *
 * Parsed once at construction with Zod, because it arrives from outside the
 * system — a typo here would otherwise surface at 07:00 as a failed send.
 */
const ChannelMap = z.record(z.nativeEnum(Region), z.string().min(1));

@Injectable()
export class AlertChannels {
  private readonly log = new Logger(AlertChannels.name);
  private readonly channels: Partial<Record<Region, string>>;

  constructor(config: ConfigService) {
    const raw = config.get<string>("TELEGRAM_CHANNELS");

    if (!raw) {
      this.log.warn("TELEGRAM_CHANNELS is empty — no region will be alerted");
      this.channels = {};
      return;
    }

    this.channels = ChannelMap.parse(JSON.parse(raw));
    this.log.log(
      `configured for ${Object.keys(this.channels).length} region(s)`,
    );
  }

  /** Regions we can actually post to, in configuration order. */
  configuredRegions(): Region[] {
    return Object.keys(this.channels) as Region[];
  }

  channelFor(region: Region): string | undefined {
    return this.channels[region];
  }
}

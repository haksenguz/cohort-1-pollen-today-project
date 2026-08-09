import { Prop, Schema, SchemaFactory } from "@nestjs/mongoose";
import { HydratedDocument } from "mongoose";
import { PollenType, Region, RiskLevel } from "@pollen/contracts";

export type AlertDocument = HydratedDocument<Alert>;

/**
 * Persistence model. Deliberately separate from the GraphQL types in ../dto —
 * the shape we store and the shape we expose are allowed to diverge, and
 * coupling them makes both harder to change.
 *
 * The enum values come from the generated types, so the database and the SDL
 * validate against one list.
 */
@Schema({ collection: "alerts", timestamps: true })
export class Alert {
  // `type: String` is required, not decorative. A TypeScript enum is both a
  // type and a value, so the emitted `design:type` is the enum OBJECT — and
  // Mongoose reads that as a nested schema definition and throws
  // "SEOUL is not a valid type at path SEOUL". Spell the storage type out.
  @Prop({ type: String, required: true, enum: Object.values(Region) })
  region: Region;

  @Prop({ type: String, required: true, enum: Object.values(PollenType) })
  pollenType: PollenType;

  /** The day the alert is *about*, not the day it was sent. `YYYY-MM-DD` KST. */
  @Prop({ type: String, required: true, match: /^\d{4}-\d{2}-\d{2}$/ })
  targetDate: string;

  @Prop({ type: String, required: true, enum: Object.values(RiskLevel) })
  riskLevel: RiskLevel;

  @Prop({ required: true })
  channel: string;

  @Prop({ required: true })
  sentAt: Date;

  @Prop({ required: true })
  messageText: string;
}

export const AlertSchema = SchemaFactory.createForClass(Alert);

/**
 * THE IDEMPOTENCY GUARANTEE — see docs/adr/0003.
 *
 * A unique compound index means a second insert for the same channel, region,
 * pollen type and target date fails with E11000 at the database. A re-run of
 * the 07:00 job, or a scheduler restarted mid-run, is harmless by construction.
 *
 * Deliberately not an application-level "already sent?" flag: that is a
 * check-then-act race, where two workers can both read "not sent" before either
 * writes. The database refuses the duplicate however many processes race, so
 * correctness stops depending on our code being careful.
 */
AlertSchema.index(
  { channel: 1, region: 1, pollenType: 1, targetDate: 1 },
  { unique: true, name: "uniq_alert_delivery" },
);

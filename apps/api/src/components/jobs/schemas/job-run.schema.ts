import { Prop, Schema, SchemaFactory } from "@nestjs/mongoose";
import { HydratedDocument } from "mongoose";
import { JobStatus } from "@pollen/contracts";

export type JobRunDocument = HydratedDocument<JobRun>;

/** Instrumentation for every scheduled job. Feeds the status page. */
@Schema({ collection: "job_runs", timestamps: true })
export class JobRun {
  @Prop({ required: true, index: true })
  jobName: string;

  @Prop({ required: true })
  startedAt: Date;

  // Nullable fields need an explicit `type` — Mongoose cannot infer one from a
  // `Date | null` union, because the emitted metadata is just `Object`.
  @Prop({ type: Date, default: null })
  finishedAt: Date | null;

  // Also needs `type: String` — a TypeScript enum is a value as well as a type,
  // so the emitted `design:type` is the enum object, which Mongoose reads as a
  // nested schema definition. See alert.schema.ts.
  @Prop({ type: String, required: true, enum: Object.values(JobStatus) })
  status: JobStatus;

  @Prop({ type: Number, default: null })
  rowsAffected: number | null;

  @Prop({ type: String, default: null })
  error: string | null;
}

export const JobRunSchema = SchemaFactory.createForClass(JobRun);

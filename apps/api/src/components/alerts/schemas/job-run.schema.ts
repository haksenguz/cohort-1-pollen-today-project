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

  @Prop({ required: true, enum: Object.values(JobStatus) })
  status: JobStatus;

  @Prop({ type: Number, default: null })
  rowsAffected: number | null;

  @Prop({ type: String, default: null })
  error: string | null;
}

export const JobRunSchema = SchemaFactory.createForClass(JobRun);

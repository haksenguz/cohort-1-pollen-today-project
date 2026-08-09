import { Query, Resolver } from "@nestjs/graphql";
import type { SystemStatus } from "./dto/job-run.dto";
import { JobsService } from "./jobs.service";

@Resolver("SystemStatus")
export class JobsResolver {
  constructor(private readonly jobs: JobsService) {}

  @Query("systemStatus")
  status(): Promise<SystemStatus> {
    return this.jobs.status();
  }
}

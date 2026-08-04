import "reflect-metadata";
import { Logger } from "@nestjs/common";
import { NestFactory } from "@nestjs/core";
import { AppModule } from "./app.module";
import { GraphQLExceptionFilter } from "./libs/errors/graphql-exception.filter";

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // Every thrown error becomes a client-visible GraphQL error in exactly one
  // place. Bugs are logged here and returned opaque — see libs/errors.
  app.useGlobalFilters(new GraphQLExceptionFilter());
  app.enableCors();

  const port = Number(process.env.PORT ?? 8000);
  await app.listen(port);
  Logger.log(`listening on :${port} — GraphQL at /graphql`, "Bootstrap");
}

void bootstrap();

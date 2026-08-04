import { Module } from "@nestjs/common";
import { ApolloDriver, ApolloDriverConfig } from "@nestjs/apollo";
import { ConfigModule, ConfigService } from "@nestjs/config";
import { GraphQLModule } from "@nestjs/graphql";
import { MongooseModule } from "@nestjs/mongoose";
import { ScheduleModule } from "@nestjs/schedule";
import { join } from "node:path";
import { ComponentsModule } from "./components/components.module";
import { HealthController } from "./health.controller";
import { DateTimeScalar } from "./libs/scalars/date-time.scalar";
import { ObjectIdScalar } from "./libs/scalars/object-id.scalar";

/**
 * Infrastructure only. Every feature arrives through ComponentsModule, so this
 * file changes when the platform changes — not when someone adds a component.
 */
@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true, envFilePath: [".env"] }),

    GraphQLModule.forRoot<ApolloDriverConfig>({
      driver: ApolloDriver,
      // Schema-first: the SDL in src/schema is hand-written and is the
      // contract. TypeScript types are generated from it into
      // @pollen/contracts — never the other way round.
      typePaths: [join(__dirname, "schema", "**", "*.graphql")],
      playground: false,
      introspection: true,
    }),

    MongooseModule.forRootAsync({
      inject: [ConfigService],
      useFactory: (config: ConfigService) => ({
        uri: config.getOrThrow<string>("MONGODB_URI"),
      }),
    }),

    ScheduleModule.forRoot(),

    ComponentsModule,
  ],
  controllers: [HealthController],
  // Scalars declared in the SDL need a runtime implementation registered here.
  providers: [DateTimeScalar, ObjectIdScalar],
})
export class AppModule {}

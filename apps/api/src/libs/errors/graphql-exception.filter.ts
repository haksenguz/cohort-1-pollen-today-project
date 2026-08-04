import {
  ArgumentsHost,
  Catch,
  ExceptionFilter,
  HttpException,
  Logger,
} from "@nestjs/common";
import { GraphQLError } from "graphql";
import { isAppError } from "./app-error";

/**
 * The single place an exception becomes a client-visible GraphQL error.
 *
 * Expected domain errors keep their code and message. Everything else is a bug:
 * it is logged in full on the server and returned as an opaque INTERNAL_ERROR,
 * so stack traces and Mongo internals never reach a public client.
 */
@Catch()
export class GraphQLExceptionFilter implements ExceptionFilter {
  private readonly log = new Logger("GraphQL");

  catch(exception: unknown, _host: ArgumentsHost): GraphQLError {
    if (isAppError(exception)) {
      return new GraphQLError(exception.message, {
        extensions: { code: exception.code, ...exception.details },
      });
    }

    if (exception instanceof HttpException) {
      return new GraphQLError(exception.message, {
        extensions: { code: "HTTP_ERROR", status: exception.getStatus() },
      });
    }

    this.log.error(
      exception instanceof Error ? exception.message : String(exception),
      exception instanceof Error ? exception.stack : undefined,
    );

    return new GraphQLError("Something went wrong on our side.", {
      extensions: { code: "INTERNAL_ERROR" },
    });
  }
}

import { CustomScalar, Scalar } from "@nestjs/graphql";
import { DateTimeResolver } from "graphql-scalars";
import { ValueNode } from "graphql";

/**
 * Runtime implementation of `scalar DateTime`, declared in
 * src/schema/common.graphql.
 *
 * Schema-first gives no scalars for free — a scalar declared in SDL with no
 * implementation silently passes values through unvalidated. This delegates to
 * the RFC 3339 resolver from graphql-scalars rather than hand-rolling date
 * parsing.
 */
@Scalar("DateTime")
export class DateTimeScalar implements CustomScalar<string, Date> {
  description = DateTimeResolver.description ?? "RFC 3339 date-time";

  parseValue(value: unknown): Date {
    return DateTimeResolver.parseValue(value) as Date;
  }

  serialize(value: unknown): string {
    return DateTimeResolver.serialize(value) as unknown as string;
  }

  parseLiteral(ast: ValueNode): Date {
    return DateTimeResolver.parseLiteral(ast, undefined) as Date;
  }
}

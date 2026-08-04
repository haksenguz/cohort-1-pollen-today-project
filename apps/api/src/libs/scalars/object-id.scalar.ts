import { Scalar, CustomScalar } from "@nestjs/graphql";
import { Kind, ValueNode } from "graphql";
import { Types } from "mongoose";
import { BadInputError } from "../errors/app-error";

/**
 * Runtime implementation of `scalar ObjectId`, declared in
 * src/schema/common.graphql.
 *
 * Converts between Mongo's ObjectId and the 24-character hex string clients
 * see. Without it, `_id` leaks out as an opaque object and every resolver ends
 * up sprinkling `String(doc._id)`.
 */
@Scalar("ObjectId")
export class ObjectIdScalar implements CustomScalar<string, Types.ObjectId> {
  description = "Mongo ObjectId, serialised as a 24-character hex string";

  /** Client → server (variables). */
  parseValue(value: unknown): Types.ObjectId {
    return this.toObjectId(value);
  }

  /** Server → client. */
  serialize(value: unknown): string {
    return value instanceof Types.ObjectId
      ? value.toHexString()
      : String(value);
  }

  /** Client → server (inline literals in the query document). */
  parseLiteral(ast: ValueNode): Types.ObjectId {
    if (ast.kind !== Kind.STRING) {
      throw new BadInputError("ObjectId must be given as a string");
    }
    return this.toObjectId(ast.value);
  }

  private toObjectId(value: unknown): Types.ObjectId {
    if (typeof value !== "string" || !Types.ObjectId.isValid(value)) {
      throw new BadInputError(`Not a valid ObjectId: ${String(value)}`);
    }
    return new Types.ObjectId(value);
  }
}

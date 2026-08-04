import { Type } from "@nestjs/common";
import { Field, Int, ObjectType } from "@nestjs/graphql";

/**
 * Generic GraphQL type factory.
 *
 * GraphQL has no generics, so a generic wrapper has to be materialised per
 * concrete type. `Paginated(Alert)` produces a real `PaginatedAlert` type in the
 * SDL while staying one definition in TypeScript.
 *
 *   @ObjectType()
 *   class PaginatedAlert extends Paginated(Alert) {}
 */
export function Paginated<T>(classRef: Type<T>): Type<{
  items: T[];
  total: number;
  hasMore: boolean;
}> {
  @ObjectType({ isAbstract: true })
  abstract class PaginatedType {
    @Field(() => [classRef])
    items: T[];

    @Field(() => Int)
    total: number;

    @Field()
    hasMore: boolean;
  }

  return PaginatedType as Type<{ items: T[]; total: number; hasMore: boolean }>;
}

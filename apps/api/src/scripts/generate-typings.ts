import { GraphQLDefinitionsFactory } from "@nestjs/graphql";
import { join } from "node:path";

/**
 * Generates TypeScript types from the hand-written SDL in src/schema.
 *
 * The SDL is the contract; this file is derived and committed. CI regenerates
 * it and fails if the result differs, so a schema change cannot land without
 * the generated types moving with it in the same pull request.
 */
void new GraphQLDefinitionsFactory().generate({
  typePaths: [join(process.cwd(), "src/schema/**/*.graphql")],
  path: join(process.cwd(), "src/graphql.generated.ts"),
  outputAs: "interface",
  watch: false,
  emitTypenameField: false,
  skipResolverArgs: true,
  customScalarTypeMapping: {
    DateTime: "Date",
    ObjectId: "string",
  },
  additionalHeader: [
    "// GENERATED FROM src/schema/*.graphql — DO NOT EDIT BY HAND.",
    "// Regenerate with: pnpm --filter @pollen/api schema:generate",
  ].join("\n"),
});

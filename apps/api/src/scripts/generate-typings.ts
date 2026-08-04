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
  // Emitted into the shared package, not into apps/api — the web app needs the
  // same enums and types, and a second hand-written copy on the frontend is
  // exactly the drift schema-first exists to prevent.
  path: join(process.cwd(), "../../packages/contracts/src/graphql.ts"),
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

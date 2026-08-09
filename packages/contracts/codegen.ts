import type { CodegenConfig } from "@graphql-codegen/cli";

/**
 * Generates TypeScript types for the web app from the hand-written SDL.
 *
 * The SDL in apps/api/schema is the contract (ADR 0004). This file is the only
 * thing that turns it into TypeScript — the Python API reads the same SDL
 * directly, so both sides derive from one source.
 */
const config: CodegenConfig = {
  // A glob, not a list: a new .graphql file must be picked up automatically,
  // not silently ignored until someone remembers to add it here.
  schema: "../../apps/api/schema/**/*.graphql",
  generates: {
    "src/graphql.ts": {
      plugins: [
        {
          add: {
            content: [
              "// GENERATED from apps/api/schema/*.graphql — DO NOT EDIT BY HAND.",
              "// Regenerate with: pnpm --filter @pollen/contracts generate",
            ].join("\n"),
          },
        },
        "@graphql-codegen/typescript",
      ],
      config: {
        // Real TypeScript enums, not string unions: `Region.SEOUL` must be a
        // runtime value, and a bare string must not typecheck.
        enumsAsTypes: false,
        // Keep SCREAMING_SNAKE members. Without this, codegen renames them to
        // PascalCase (`Region.Seoul`) and every call site breaks.
        namingConvention: {
          enumValues: "keep",
        },
        scalars: {
          DateTime: "Date",
          ObjectId: "string",
        },
        skipTypename: true,
      },
    },
  },
};

export default config;

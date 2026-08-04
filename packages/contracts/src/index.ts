/**
 * The shared package. Both apps/api and apps/web import from here.
 *
 * - `./graphql.js` — GENERATED from apps/api/src/schema/*.graphql. Enums and
 *   types for everything the API exposes. Never edit by hand.
 * - `./enums.js`   — ordering helpers the SDL cannot express.
 * - `./external.js` — Zod schemas for data arriving from OUTSIDE the system.
 */
export * from "./graphql.js";
export * from "./enums.js";
export * from "./external.js";

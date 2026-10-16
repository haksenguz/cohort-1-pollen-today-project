/**
 * Starter prompts for a new conversation (TASKS.md B-014 C6).
 *
 * Data, not JSX, for the same reason `utils/format.ts` keeps `ALLERGEN_OPTIONS`
 * as its own list: the chips and the test that walks them share one definition,
 * so a prompt can never be on screen but untested.
 *
 * Each one is a complete plain-English symptom report, because the phone case
 * this exists for is the first sentence being the part that stalls. Nothing
 * here names a condition or a severity: the wording is what a person would
 * say, and the safety level is decided later by the rule engine (ADR 0001).
 */
export const SUGGESTED_PROMPTS = [
  "My eyes are itchy and watering",
  "I have been coughing since this morning",
  "My nose is running and I keep sneezing",
  "I feel tight in my chest",
] as const;
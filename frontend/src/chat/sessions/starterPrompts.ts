/**
 * Starter prompts for a new conversation (TASKS.md B-014 C6).
 *
 * Data, not JSX, for the same reason `utils/format.ts` keeps `ALLERGEN_OPTIONS`
 * as its own list: the chips and the test that walks them share one definition,
 * so a prompt can never be on screen but untested.
 *
 * Each one is a plain-English symptom report, because the phone case this
 * exists for is the first sentence being the part that stalls. Nothing here
 * names a condition or a severity: the wording is what a person would say,
 * and the safety level is decided later by the rule engine (ADR 0001).
 *
 * They are short enough to sit two to a row and no more than two lines deep,
 * because a taller block pushes the greeting off the top of a short screen.
 */
export const SUGGESTED_PROMPTS = [
  "Eyes itchy and watery",
  "Coughing since morning",
  "Runny nose, sneezing",
  "Tight in my chest",
] as const;
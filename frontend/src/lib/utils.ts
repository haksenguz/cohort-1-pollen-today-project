import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge conditional class names, then let later Tailwind utilities win over
 * earlier conflicting ones. Without the twMerge step, a caller passing
 * `className="p-4"` to a component whose base classes already set a padding
 * would get both rules in the output and the winner would depend on stylesheet
 * order rather than on the caller's intent.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Stable date formatting for editorial content.
//
// Why this helper exists:
// - blog posts currently use date-only frontmatter values like `2026-05-03`
// - those values become `Date` objects at UTC midnight
// - formatting them in the build machine's local timezone can shift the visible
//   calendar day backward or forward
//
// Example of the problem:
//   2026-05-03 (stored as UTC midnight)
//     -> formatted in a negative timezone
//     -> can appear as May 2 instead of May 3
//
// Fix:
// - always format editorial publish dates in UTC
// - that keeps the rendered date stable locally, in CI, and on Cloudflare
export function formatEditorialDate(
  date: Date,
  month: "short" | "long" = "short",
): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "UTC",
    year: "numeric",
    month,
    day: "numeric",
  }).format(date);
}

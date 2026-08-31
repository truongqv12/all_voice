/**
 * Locale-aware thousands formatting for the usage-stats counters, e.g.
 * `1234` -> `1.234` (vi-VN) or `1,234` (en-US). Falls back to the raw number
 * if `Intl` is unavailable.
 */
export function formatCount(n: number, language: string): string {
  const locale = language.startsWith('en') ? 'en-US' : 'vi-VN'
  try {
    return new Intl.NumberFormat(locale).format(n)
  } catch {
    return String(n)
  }
}

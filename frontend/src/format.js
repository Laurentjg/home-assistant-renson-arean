/* Number formatting that follows the Home Assistant user profile. */

// The explicit number formats a user can pick in their profile, mapped onto a
// locale that writes numbers that way.
const NUMBER_FORMAT_LOCALES = {
  comma_decimal: 'en-US',
  decimal_comma: 'de',
  space_comma: 'fr',
  quote_decimal: 'de-CH',
};

export function formatNumber(value, decimals, locale) {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  // Avoid "-0,0" for values that round to zero.
  const rounded = Math.abs(value) < 0.5 / 10 ** decimals ? 0 : value;
  const options = { minimumFractionDigits: decimals, maximumFractionDigits: decimals };
  const numberFormat = locale && locale.number_format;
  if (numberFormat === 'none') {
    return new Intl.NumberFormat('en-US', { ...options, useGrouping: false }).format(rounded);
  }
  const tag = NUMBER_FORMAT_LOCALES[numberFormat] || (locale && locale.language) || undefined;
  try {
    return new Intl.NumberFormat(tag, options).format(rounded);
  } catch (_err) {
    return new Intl.NumberFormat(undefined, options).format(rounded);
  }
}

export function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

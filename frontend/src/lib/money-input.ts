export function sanitizeMoneyInput(raw: string, allowNegative = false): string {
  const negative = allowNegative && raw.trimStart().startsWith("-");
  const filtered = raw.replace(/[^\d.,]/g, "");
  const separators = [...filtered.matchAll(/[.,]/g)];
  const decimalIndex = separators.length ? separators.at(-1)?.index : undefined;
  let whole = decimalIndex === undefined ? filtered : filtered.slice(0, decimalIndex);
  const fraction = decimalIndex === undefined ? "" : filtered.slice(decimalIndex + 1);
  whole = whole.replace(/[.,]/g, "").replace(/^0+(?=\d)/, "");
  const digits = whole || (decimalIndex === undefined ? "" : "0");
  const value = decimalIndex === undefined ? digits : `${digits}.${fraction.replace(/[.,]/g, "").slice(0, 4)}`;
  return negative ? `-${value}` : value;
}

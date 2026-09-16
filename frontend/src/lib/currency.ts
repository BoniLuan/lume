const formatters = new Map<string, Intl.NumberFormat>();

export function currency(value: string | number, code = "BRL"): string {
  let formatter = formatters.get(code);
  if (!formatter) {
    formatter = new Intl.NumberFormat("en", {
      style: "currency",
      currency: code,
      minimumFractionDigits: 2,
    });
    formatters.set(code, formatter);
  }
  return formatter.format(Number(value));
}

export function percentage(value: string | number): string {
  return `${Math.min(Number(value), 999).toFixed(0)}%`;
}

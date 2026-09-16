export function todayInSaoPaulo(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

export function currentMonth(): string {
  return todayInSaoPaulo().slice(0, 7);
}

export function displayDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    timeZone: "UTC",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T12:00:00Z`));
}

export function monthLabel(value: string): string {
  return new Intl.DateTimeFormat("en", { timeZone: "UTC", month: "long", year: "numeric" }).format(
    new Date(`${value}-01T12:00:00Z`),
  );
}

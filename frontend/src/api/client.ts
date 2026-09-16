export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

let csrfToken: string | null = null;

export function setCsrfToken(value: string | null | undefined): void {
  csrfToken = value ?? null;
}

type ApiOptions = Omit<RequestInit, "body"> & { body?: unknown };

function detailFrom(value: unknown): string {
  if (!value || typeof value !== "object" || !("detail" in value)) return "Request failed";
  const detail = (value as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item: unknown) => {
        if (item && typeof item === "object" && "msg" in item) {
          return String(item.msg);
        }
        return "Invalid value";
      })
      .join(". ");
  }
  return "Request failed";
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const method = options.method?.toUpperCase() ?? "GET";
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body !== undefined) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(path, {
    ...options,
    method,
    headers,
    credentials: "include",
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new ApiError(response.status, detailFrom(payload));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

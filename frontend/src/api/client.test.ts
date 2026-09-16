import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, setCsrfToken } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

describe("API client", () => {
  it("sends cookie credentials and CSRF only on unsafe requests", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    setCsrfToken("bound-token");

    await api("/api/v1/accounts");
    await api("/api/v1/accounts", { method: "POST", body: { name: "Cash" } });

    const getInit = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const postInit = fetchMock.mock.calls[1]?.[1] as RequestInit;
    expect(getInit.credentials).toBe("include");
    expect(new Headers(getInit.headers).has("X-CSRF-Token")).toBe(false);
    expect(new Headers(postInit.headers).get("X-CSRF-Token")).toBe("bound-token");
    expect(postInit.body).toBe('{"name":"Cash"}');
  });

  it("turns API validation responses into readable errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: [{ msg: "Amount must be positive" }] }), {
          status: 422,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(api("/api/v1/transactions")).rejects.toEqual(
      new ApiError(422, "Amount must be positive"),
    );
  });
});

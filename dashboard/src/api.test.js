import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

function mockFetchOnce(status, body, { ok } = {}) {
  global.fetch = vi.fn().mockResolvedValue({
    ok: ok ?? (status >= 200 && status < 300),
    status,
    json: async () => body,
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("api.login", () => {
  it("POSTs form-encoded credentials, not JSON", async () => {
    mockFetchOnce(200, { access_token: "t", token_type: "bearer" });
    await api.login("alice", "s3cret");

    const [, options] = global.fetch.mock.calls[0];
    expect(options.method).toBe("POST");
    expect(options.headers["Content-Type"]).toBe("application/x-www-form-urlencoded");
    expect(options.body).toBe("username=alice&password=s3cret");
  });
});

describe("api.overview", () => {
  it("sends the bearer token in the Authorization header", async () => {
    mockFetchOnce(200, { olist_customers: 93357 });
    await api.overview("my-jwt");

    const [url, options] = global.fetch.mock.calls[0];
    expect(url).toContain("/analytics/overview");
    expect(options.headers["Authorization"]).toBe("Bearer my-jwt");
  });

  it("omits the Authorization header when no token is given", async () => {
    mockFetchOnce(200, {});
    await api.overview(undefined);
    const [, options] = global.fetch.mock.calls[0];
    expect(options.headers["Authorization"]).toBeUndefined();
  });
});

describe("error handling", () => {
  it("throws an ApiError with the server-provided detail on a non-2xx response", async () => {
    mockFetchOnce(403, { detail: "Rôle 'analyst' non autorisé pour cette action" });
    await expect(api.adminOverview("token")).rejects.toMatchObject({
      status: 403,
      message: "Rôle 'analyst' non autorisé pour cette action",
    });
  });

  it("throws an ApiError even if the error body is not valid JSON", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => {
        throw new SyntaxError("not json");
      },
    });
    await expect(api.overview("token")).rejects.toBeInstanceOf(ApiError);
  });

  it("does not throw on a successful response", async () => {
    mockFetchOnce(200, { ok: true });
    await expect(api.overview("token")).resolves.toEqual({ ok: true });
  });

  it("returns null on a 204 No Content response instead of parsing a body", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 204, json: async () => { throw new Error("should not be called"); } });
    await expect(api.deleteUser("token", "bob")).resolves.toBeNull();
  });
});

describe("query parameter building", () => {
  it("includes optional filters only when provided", async () => {
    mockFetchOnce(200, []);
    await api.churnList("token", { limit: 10, offset: 0 });
    let [url] = global.fetch.mock.calls[0];
    expect(url).not.toContain("risk_level");

    mockFetchOnce(200, []);
    await api.churnList("token", { risk_level: "high", limit: 10, offset: 0 });
    [url] = global.fetch.mock.calls[0];
    expect(url).toContain("risk_level=high");
  });
});

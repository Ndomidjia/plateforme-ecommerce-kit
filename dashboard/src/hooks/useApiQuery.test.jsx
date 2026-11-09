import { renderHook, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useApiQuery } from "./useApiQuery";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => mockNavigate };
});

const wrapper = ({ children }) => <MemoryRouter>{children}</MemoryRouter>;

beforeEach(() => {
  mockNavigate.mockClear();
  useAuth.mockReturnValue({ token: "fake-token", logout: vi.fn() });
});

describe("useApiQuery", () => {
  it("starts in a loading state and resolves to the fetched data", async () => {
    const fetcher = vi.fn().mockResolvedValue({ olist_customers: 96096 });
    const { result } = renderHook(() => useApiQuery(fetcher, []), { wrapper });

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toEqual({ olist_customers: 96096 });
    expect(result.current.error).toBeNull();
    expect(fetcher).toHaveBeenCalledWith("fake-token");
  });

  it("exposes a non-401 failure as an error, without logging the user out", async () => {
    const logout = vi.fn();
    useAuth.mockReturnValue({ token: "fake-token", logout });
    const fetcher = vi.fn().mockRejectedValue(new ApiError(500, "Erreur serveur"));

    const { result } = renderHook(() => useApiQuery(fetcher, []), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBeInstanceOf(ApiError);
    expect(logout).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("logs the user out and redirects to /login on a 401, instead of setting an error", async () => {
    const logout = vi.fn();
    useAuth.mockReturnValue({ token: "expired-token", logout });
    const fetcher = vi.fn().mockRejectedValue(new ApiError(401, "Jeton expiré"));

    const { result } = renderHook(() => useApiQuery(fetcher, []), { wrapper });
    await waitFor(() => expect(logout).toHaveBeenCalled());

    expect(mockNavigate).toHaveBeenCalledWith("/login");
    expect(result.current.error).toBeNull();
  });

  it("reload() re-invokes the fetcher and updates the data", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce({ v: 1 }).mockResolvedValueOnce({ v: 2 });
    const { result } = renderHook(() => useApiQuery(fetcher, []), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ v: 1 });

    result.current.reload();
    await waitFor(() => expect(result.current.data).toEqual({ v: 2 }));
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});

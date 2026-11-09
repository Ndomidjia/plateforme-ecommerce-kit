import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";
import { api } from "../api";

vi.mock("../api", () => ({
  api: { login: vi.fn() },
}));

function makeJwt(claims) {
  const base64url = (obj) =>
    btoa(JSON.stringify(obj)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `${base64url({ alg: "HS256" })}.${base64url(claims)}.signature`;
}

function Probe() {
  const { token, user, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="token">{token ?? "none"}</span>
      <span data-testid="username">{user?.username ?? "none"}</span>
      <span data-testid="role">{user?.role ?? "none"}</span>
      <button onClick={() => login("alice", "s3cret")}>login</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

afterEach(() => {
  localStorage.clear();
});

describe("AuthProvider", () => {
  it("starts logged out when localStorage has no token", () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    expect(screen.getByTestId("token")).toHaveTextContent("none");
    expect(screen.getByTestId("username")).toHaveTextContent("none");
  });

  it("restores the session from a token already in localStorage", () => {
    localStorage.setItem("token", makeJwt({ sub: "bob", role: "admin" }));
    render(<AuthProvider><Probe /></AuthProvider>);
    expect(screen.getByTestId("username")).toHaveTextContent("bob");
    expect(screen.getByTestId("role")).toHaveTextContent("admin");
  });

  it("login() stores the token and decodes username/role from it", async () => {
    api.login.mockResolvedValue({ access_token: makeJwt({ sub: "alice", role: "analyst" }) });
    const user = userEvent.setup();
    render(<AuthProvider><Probe /></AuthProvider>);

    await act(() => user.click(screen.getByText("login")));

    expect(screen.getByTestId("username")).toHaveTextContent("alice");
    expect(screen.getByTestId("role")).toHaveTextContent("analyst");
    expect(localStorage.getItem("token")).toBeTruthy();
  });

  it("logout() clears the token from state and from localStorage", async () => {
    localStorage.setItem("token", makeJwt({ sub: "bob", role: "admin" }));
    const user = userEvent.setup();
    render(<AuthProvider><Probe /></AuthProvider>);

    await act(() => user.click(screen.getByText("logout")));

    expect(screen.getByTestId("token")).toHaveTextContent("none");
    expect(localStorage.getItem("token")).toBeNull();
  });
});

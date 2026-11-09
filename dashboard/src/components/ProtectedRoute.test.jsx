import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ProtectedRoute } from "./ProtectedRoute";
import { useAuth } from "../auth/AuthContext";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

function renderWithRoute({ initialPath = "/admin", requireRole } = {}) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/login" element={<div>Page de connexion</div>} />
        <Route path="/" element={<div>Vue d'ensemble</div>} />
        <Route element={<ProtectedRoute requireRole={requireRole} />}>
          <Route path="/admin" element={<div>Page Administration</div>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe("ProtectedRoute", () => {
  it("redirects to /login when there is no token", () => {
    useAuth.mockReturnValue({ token: null, user: null });
    renderWithRoute();
    expect(screen.getByText("Page de connexion")).toBeInTheDocument();
  });

  it("renders the protected page when authenticated and no role is required", () => {
    useAuth.mockReturnValue({ token: "t", user: { username: "alice", role: "analyst" } });
    renderWithRoute({ requireRole: undefined });
    expect(screen.getByText("Page Administration")).toBeInTheDocument();
  });

  it("renders the protected page when the user has the required role", () => {
    useAuth.mockReturnValue({ token: "t", user: { username: "bob", role: "admin" } });
    renderWithRoute({ requireRole: "admin" });
    expect(screen.getByText("Page Administration")).toBeInTheDocument();
  });

  it("redirects an authenticated user without the required role back to the home page, not to login", () => {
    useAuth.mockReturnValue({ token: "t", user: { username: "alice", role: "analyst" } });
    renderWithRoute({ requireRole: "admin" });
    expect(screen.getByText("Vue d'ensemble")).toBeInTheDocument();
    expect(screen.queryByText("Page Administration")).not.toBeInTheDocument();
  });
});

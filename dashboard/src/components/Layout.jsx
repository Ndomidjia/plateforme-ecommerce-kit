import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const links = [
  { to: "/", label: "Vue d'ensemble", end: true },
  { to: "/funnel", label: "Funnel" },
  { to: "/churn", label: "Scoring churn" },
  { to: "/rfm", label: "Segments RFM" },
  { to: "/recommendations", label: "Recommandations" },
  { to: "/association-rules", label: "Règles d'association" },
  { to: "/sentiment", label: "Sentiment (avis)" },
  { to: "/retention", label: "Calculateur rétention" },
  { to: "/customer-360", label: "Vue client 360°" },
];

const adminLinks = [
  { to: "/rgpd", label: "RGPD" },
  { to: "/admin", label: "Administration" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>E-commerce Analytics</h1>
        <nav>
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => (isActive ? "active" : "")}>
              {l.label}
            </NavLink>
          ))}
          {user?.role === "admin" && (
            <>
              <div style={{ margin: "12px 8px 4px", fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", color: "var(--text-muted)" }}>
                Administration
              </div>
              {adminLinks.map((l) => (
                <NavLink key={l.to} to={l.to} className={({ isActive }) => (isActive ? "active" : "")}>
                  {l.label}
                </NavLink>
              ))}
            </>
          )}
        </nav>
        <div className="user-box">
          <div>{user?.username} · {user?.role}</div>
          <button onClick={handleLogout}>Déconnexion</button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}

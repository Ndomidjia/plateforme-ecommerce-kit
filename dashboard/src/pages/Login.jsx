import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
      navigate("/");
    } catch {
      setError("Identifiants invalides");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>Plateforme e-commerce</h1>
        <label htmlFor="username">Utilisateur</label>
        <input id="username" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        <label htmlFor="password">Mot de passe</label>
        <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <p style={{ color: "var(--status-critical)", fontSize: 13 }}>{error}</p>}
        <button type="submit" disabled={submitting}>{submitting ? "Connexion…" : "Se connecter"}</button>
      </form>
    </div>
  );
}

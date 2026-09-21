import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useApiQuery } from "../hooks/useApiQuery";

const MODULE_LABEL = {
  rfm: "RFM (Olist)",
  market_basket: "Market basket (Olist)",
  funnel: "Funnel (Retailrocket)",
  recommendations: "Recommandations (Retailrocket)",
  churn: "Scoring churn",
  sentiment: "Sentiment (deep learning)",
  customer_360: "Vue client 360° (dépend de RFM/sentiment/market basket)",
};

const STATUS_LABEL = { running: "En cours", success: "Succès", failed: "Échec", never_run: "Jamais lancé" };
const STATUS_COLOR = {
  running: "var(--status-warning)",
  success: "var(--status-good)",
  failed: "var(--status-critical)",
  never_run: "var(--text-muted)",
};

function UserManagement() {
  const { token, user: currentUser } = useAuth();
  const users = useApiQuery((t) => api.listUsers(t), []);
  const [form, setForm] = useState({ username: "", password: "", role: "analyst" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleCreate(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createUser(token, form);
      setForm({ username: "", password: "", role: "analyst" });
      users.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur inattendue");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(username) {
    if (!window.confirm(`Supprimer le compte '${username}' ?`)) return;
    try {
      await api.deleteUser(token, username);
      users.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur inattendue");
    }
  }

  return (
    <div className="card">
      <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>Comptes API</h3>

      <form className="filters" onSubmit={handleCreate}>
        <input placeholder="Utilisateur" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
        <input placeholder="Mot de passe" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
          <option value="analyst">analyst</option>
          <option value="admin">admin</option>
        </select>
        <button type="submit" disabled={busy}>Créer</button>
      </form>

      {error && <div className="error-box">{error}</div>}

      {users.loading && <p>Chargement…</p>}
      {users.data && (
        <table>
          <thead><tr><th>Utilisateur</th><th>Rôle</th><th>Créé le</th><th></th></tr></thead>
          <tbody>
            {users.data.map((u) => (
              <tr key={u.username}>
                <td>{u.username}</td>
                <td>{u.role}</td>
                <td>{u.created_at}</td>
                <td>
                  {u.username !== currentUser.username && (
                    <button type="button" onClick={() => handleDelete(u.username)} style={{ color: "var(--status-critical)" }}>
                      Supprimer
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function RecomputePanel() {
  const { token } = useAuth();
  const status = useApiQuery((t) => api.recomputeStatus(t), []);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  const hasRunning = status.data?.some((m) => m.status === "running");

  useEffect(() => {
    if (hasRunning && !pollRef.current) {
      pollRef.current = setInterval(() => status.reload(), 4000);
    }
    if (!hasRunning && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [hasRunning, status]);

  async function handleTrigger(module) {
    setError(null);
    try {
      await api.triggerRecompute(token, module);
      status.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur inattendue");
    }
  }

  return (
    <div className="card">
      <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
        Recalcul des modules ML
      </h3>
      <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>
        Relance un script d'analyse en arrière-plan sur le serveur. Le churn scoring prend
        plusieurs minutes (validation croisée) ; les autres modules sont plus rapides.
      </p>
      {error && <div className="error-box">{error}</div>}
      {status.loading && <p>Chargement…</p>}
      {status.data && (
        <table>
          <thead><tr><th>Module</th><th>Statut</th><th>Dernier lancement</th><th></th></tr></thead>
          <tbody>
            {status.data.map((m) => (
              <tr key={m.module}>
                <td>{MODULE_LABEL[m.module] ?? m.module}</td>
                <td><span className="badge" style={{ color: STATUS_COLOR[m.status] }}>
                  <span style={{ width: 7, height: 7, borderRadius: "50%", background: STATUS_COLOR[m.status], display: "inline-block", marginRight: 5 }} />
                  {STATUS_LABEL[m.status]}
                </span></td>
                <td>{m.started_at ? new Date(m.started_at).toLocaleString("fr-FR") : "—"}</td>
                <td>
                  <button type="button" onClick={() => handleTrigger(m.module)} disabled={m.status === "running"}>
                    Relancer
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const MODEL_LABEL = {
  churn_scoring: "Scoring churn (Random Forest)",
  customer_360_proxy: "Proxy de risque — Vue client 360°",
};

function ModelRegistryPanel() {
  const { token } = useAuth();
  const registry = useApiQuery((t) => api.listModelRegistry(t), []);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);

  async function handleRollback(modelName) {
    if (!window.confirm(
      `Revenir à la version précédente de '${MODEL_LABEL[modelName] ?? modelName}' ? ` +
      "La version active actuelle sera conservée pour inspection, mais ne sera plus servie."
    )) return;
    setBusy(modelName);
    setError(null);
    try {
      await api.rollbackModel(token, modelName);
      registry.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur inattendue");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="card">
      <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
        Versions des modèles
      </h3>
      <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>
        Une nouvelle version n'est promue en production que si elle n'est pas significativement
        moins bonne que la version active (voir analytics/model_registry.py). Si un recalcul promu
        se révèle problématique, un retour en arrière restaure la version précédente (un seul
        niveau — l'historique complet des métriques de chaque exécution reste consultable dans
        analytics.model_metrics_history).
      </p>
      {error && <div className="error-box">{error}</div>}
      {registry.loading && <p>Chargement…</p>}
      {registry.data && (
        <table>
          <thead>
            <tr><th>Modèle</th><th>Version active</th><th>Métrique (AUC)</th><th>Retour en arrière</th><th></th></tr>
          </thead>
          <tbody>
            {registry.data.map((m) => (
              <tr key={m.model_name}>
                <td>{MODEL_LABEL[m.model_name] ?? m.model_name}</td>
                <td>{m.active_version}</td>
                <td>{m.active_metric != null ? Number(m.active_metric).toFixed(4) : "—"}</td>
                <td>
                  {m.has_backup
                    ? `Disponible (${m.previous_version}, AUC ${Number(m.previous_metric).toFixed(4)})`
                    : "Aucune sauvegarde"}
                </td>
                <td>
                  <button
                    type="button"
                    onClick={() => handleRollback(m.model_name)}
                    disabled={!m.has_backup || busy === m.model_name}
                    style={{ color: "var(--status-critical)" }}
                  >
                    Revenir en arrière
                  </button>
                </td>
              </tr>
            ))}
            {registry.data.length === 0 && (
              <tr><td colSpan={5} style={{ color: "var(--text-muted)" }}>
                Aucun modèle enregistré pour l'instant — se remplit au premier recalcul de churn ou vue client 360°.
              </td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function Admin() {
  return (
    <>
      <h2>Administration</h2>
      <UserManagement />
      <RecomputePanel />
      <ModelRegistryPanel />
    </>
  );
}

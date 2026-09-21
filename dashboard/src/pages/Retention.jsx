import { useState } from "react";
import { api, ApiError } from "../api";
import { StatTile } from "../components/StatTile";
import { useAuth } from "../auth/AuthContext";

export default function Retention() {
  const { token } = useAuth();
  const [topN, setTopN] = useState(500);
  const [successRate, setSuccessRate] = useState(30);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleCompute(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      setResult(await api.retentionEstimate(token, { top_n: topN, success_rate: successRate / 100 }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur inattendue");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <h2>Calculateur de rétention</h2>
      <div className="card">
        <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 0 }}>
          Outil d'aide à la décision : si une campagne de rétention cible les N clients les plus à
          risque de churn et réussit à les retenir avec le taux de succès indiqué, quelle valeur
          (LTV cumulée) espère-t-on sauver ? Estimation simple (LTV moyenne × taux de succès
          supposé) — un ordre de grandeur pour prioriser, pas une prédiction garantie.
        </p>

        <form className="filters" onSubmit={handleCompute}>
          <label htmlFor="top-n" style={{ fontSize: 13, color: "var(--text-secondary)" }}>Nb clients ciblés</label>
          <input id="top-n" type="number" min="1" max="50000" value={topN} onChange={(e) => setTopN(e.target.value)} style={{ width: 100 }} />
          <label htmlFor="success-rate" style={{ fontSize: 13, color: "var(--text-secondary)" }}>Taux de succès (%)</label>
          <input id="success-rate" type="number" min="0" max="100" value={successRate} onChange={(e) => setSuccessRate(e.target.value)} style={{ width: 80 }} />
          <button type="submit" disabled={loading}>{loading ? "Calcul…" : "Calculer"}</button>
        </form>

        {error && <div className="error-box">{error}</div>}

        {result && (
          <div style={{ display: "flex", gap: 16, marginTop: 20 }}>
            <StatTile label="Clients ciblés" value={result.targeted_customers.toLocaleString("fr-FR")} />
            <StatTile label="Probabilité de churn moyenne" value={`${(result.avg_churn_proba_targeted * 100).toFixed(1)}%`} />
            <StatTile label="LTV cumulée ciblée" value={result.total_ltv_targeted.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} />
            <StatTile label="Valeur estimée sauvée" value={result.estimated_value_saved.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} />
          </div>
        )}
      </div>
    </>
  );
}

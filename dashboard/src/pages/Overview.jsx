import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import { AlertBanner } from "../components/AlertBanner";
import { AnomalyBanner } from "../components/AnomalyBanner";
import { StatTile } from "../components/StatTile";
import { useApiQuery } from "../hooks/useApiQuery";

const ACTION_LABEL = { export: "Export", erasure: "Suppression" };

function TrendTile({ delta }) {
  if (delta === null || delta === undefined) {
    return <StatTile label="Tendance conversion (semaine)" value="—" />;
  }
  const pct = (delta * 100).toFixed(1);
  const color = delta >= 0 ? "var(--status-good)" : "var(--status-critical)";
  const arrow = delta >= 0 ? "▲" : "▼";
  return (
    <div className="card" style={{ flex: 1, textAlign: "center" }}>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>Tendance conversion (semaine)</div>
      <div style={{ fontSize: 26, fontWeight: 700, color, fontVariantNumeric: "tabular-nums" }}>
        {arrow} {Math.abs(pct)}%
      </div>
    </div>
  );
}

export default function Overview() {
  const { user } = useAuth();
  const overview = useApiQuery((token) => api.overview(token), []);
  const anomalies = useApiQuery((token) => api.anomalies(token), []);
  const adminOverview = useApiQuery(
    (token) => (user.role === "admin" ? api.adminOverview(token) : Promise.resolve(null)),
    [user.role],
  );

  return (
    <>
      <h2>Vue d'ensemble</h2>

      {overview.loading && <p>Chargement…</p>}
      {overview.error && <div className="error-box">{overview.error.message}</div>}
      {overview.data && (
        <>
          <AlertBanner kpis={overview.data} />
          <AnomalyBanner anomalies={anomalies.data} />
          <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
            <StatTile label="Clients Olist" value={overview.data.olist_customers.toLocaleString("fr-FR")} />
            <StatTile label="Visiteurs Retailrocket" value={overview.data.retailrocket_visitors.toLocaleString("fr-FR")} />
            <StatTile label="Clients churn" value={overview.data.churn_customers.toLocaleString("fr-FR")} />
          </div>
          <div style={{ display: "flex", gap: 16, marginBottom: 24 }}>
            <StatTile label="Risque churn élevé" value={`${(overview.data.churn_pct_high_risk * 100).toFixed(1)}%`} />
            <StatTile label="Segment RFM dominant" value={overview.data.rfm_dominant_segment} />
            <StatTile label="Conversion funnel globale" value={`${(overview.data.funnel_global_conversion_rate * 100).toFixed(2)}%`} />
            <StatTile label="Règles d'association fortes" value={overview.data.association_rules_significant_count} />
          </div>
          <div style={{ display: "flex", gap: 16, marginBottom: 24 }}>
            <StatTile
              label="Valeur totale à risque (LTV)"
              value={overview.data.total_value_at_risk.toLocaleString("fr-FR", { maximumFractionDigits: 0 })}
            />
            <StatTile
              label="Couverture catalogue reco"
              value={`${(overview.data.recommendation_catalog_coverage_pct * 100).toFixed(1)}%`}
            />
            <TrendTile delta={overview.data.funnel_trend_delta_pct} />
            <StatTile
              label="Avis négatifs (sentiment)"
              value={overview.data.pct_negative_reviews != null ? `${(overview.data.pct_negative_reviews * 100).toFixed(1)}%` : "—"}
            />
          </div>
        </>
      )}

      {user.role === "admin" && (
        <>
          <h2 style={{ fontSize: 16, color: "var(--text-secondary)" }}>Administration</h2>
          {adminOverview.loading && <p>Chargement…</p>}
          {adminOverview.error && <div className="error-box">{adminOverview.error.message}</div>}
          {adminOverview.data && (
            <>
              <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
                {adminOverview.data.users_by_role.map((r) => (
                  <StatTile key={r.role} label={`Comptes ${r.role}`} value={r.count} />
                ))}
                <StatTile label="Actions RGPD tracées" value={adminOverview.data.rgpd_total_actions} />
                <StatTile
                  label="Modèle churn actif"
                  value={adminOverview.data.churn_model_version ?? "—"}
                />
              </div>

              <div className="card">
                <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
                  Dernières actions RGPD
                </h3>
                <table>
                  <thead>
                    <tr><th>Action</th><th>Client</th><th>Par</th><th>Quand</th></tr>
                  </thead>
                  <tbody>
                    {adminOverview.data.rgpd_recent.map((entry, i) => (
                      <tr key={i}>
                        <td>{ACTION_LABEL[entry.action] ?? entry.action}</td>
                        <td>{entry.schema_name} #{entry.subject_id}</td>
                        <td>{entry.requested_by}</td>
                        <td>{entry.requested_at}</td>
                      </tr>
                    ))}
                    {adminOverview.data.rgpd_recent.length === 0 && (
                      <tr><td colSpan={4} style={{ color: "var(--text-muted)" }}>Aucune action pour l'instant</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}

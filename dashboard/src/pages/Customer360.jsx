import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { ExportCsvButton } from "../components/ExportCsvButton";
import { StatTile } from "../components/StatTile";
import { useApiQuery } from "../hooks/useApiQuery";

const RISK_COLOR = { low: "var(--status-good)", medium: "var(--status-warning)", high: "var(--status-critical)" };
const RISK_LABEL = { low: "Faible", medium: "Moyen", high: "Élevé" };
const ORDER = ["low", "medium", "high"];

export default function Customer360() {
  const [riskFilter, setRiskFilter] = useState("");
  const summary = useApiQuery((token) => api.customer360Summary(token), []);
  const list = useApiQuery((token) => api.customer360List(token, { risk_level: riskFilter || undefined, limit: 50 }), [riskFilter]);

  const chartData = summary.data
    ? ORDER.map((level) => {
        const row = summary.data.risk_distribution.find((r) => r.risk_level === level);
        return { risk_level: level, label: RISK_LABEL[level], count: row?.count ?? 0 };
      })
    : [];

  return (
    <>
      <h2>Vue client 360° (Olist)</h2>

      <div className="card" style={{ borderColor: "var(--status-critical)", borderWidth: 2 }}>
        <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--status-critical)" }}>
          ⚠ Fiabilité limitée — à lire avant d'utiliser cette page
        </h3>
        <p style={{ fontSize: 13, marginBottom: 8 }}>
          Cette vue combine, pour chaque client Olist : son segment RFM, un <strong>proxy</strong> de
          risque de non-réachat (pas un vrai churn observé — il n'existe aucune étiquette de départ
          réelle pour les clients Olist), le sentiment moyen de ses avis et une recommandation de
          catégorie.
        </p>
        {summary.data && (
          <p style={{ fontSize: 13, marginBottom: 0, fontWeight: 600 }}>
            {summary.data.model_reliability_note}
          </p>
        )}
      </div>

      {summary.loading && <p>Chargement…</p>}
      {summary.error && <div className="error-box">{summary.error.message}</div>}
      {summary.data && (
        <>
          <div style={{ display: "flex", gap: 16, margin: "20px 0" }}>
            <StatTile label="Clients Olist" value={summary.data.total_customers.toLocaleString("fr-FR")} />
            <StatTile label="Évaluables (assez de recul)" value={summary.data.evaluated_customers.toLocaleString("fr-FR")} />
            <StatTile label="Trop récents (censurés)" value={summary.data.censored_customers.toLocaleString("fr-FR")} />
            <StatTile label="Fenêtre de réachat" value={`${summary.data.repurchase_threshold_days} j`} />
          </div>

          <div className="card">
            <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
              Répartition du proxy de risque (terciles, clients évaluables)
            </h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                <CartesianGrid stroke="var(--gridline)" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 13, fill: "var(--text-muted)" }} stroke="var(--baseline)" />
                <YAxis tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--baseline)" />
                <Tooltip
                  formatter={(v) => v.toLocaleString("fr-FR")}
                  contentStyle={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13 }}
                />
                <Bar dataKey="count" name="Clients" radius={[4, 4, 0, 0]} maxBarSize={80}>
                  {chartData.map((d) => (
                    <Cell key={d.risk_level} fill={RISK_COLOR[d.risk_level]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      <div className="card">
        <div className="filters">
          <label htmlFor="risk-select" style={{ fontSize: 13, color: "var(--text-secondary)" }}>Niveau de risque (proxy)</label>
          <select id="risk-select" value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)}>
            <option value="">Tous</option>
            <option value="high">Élevé</option>
            <option value="medium">Moyen</option>
            <option value="low">Faible</option>
          </select>
          <ExportCsvButton data={list.data} filename="customer_360.csv" />
        </div>

        {list.loading && <p>Chargement…</p>}
        {list.error && <div className="error-box">{list.error.message}</div>}
        {list.data && (
          <table>
            <thead>
              <tr>
                <th>Client</th><th>Segment RFM</th><th>Risque (proxy)</th><th>Note avis moy.</th>
                <th>Sentiment dominant</th><th>Catégorie principale</th><th>Recommandation</th>
              </tr>
            </thead>
            <tbody>
              {list.data.map((row) => (
                <tr key={row.customer_unique_id}>
                  <td title={row.customer_unique_id}>{row.customer_unique_id.slice(0, 10)}…</td>
                  <td>{row.rfm_segment ?? "—"}</td>
                  <td><span className={`badge ${row.proxy_risk_level}`}>{RISK_LABEL[row.proxy_risk_level] ?? "—"}</span></td>
                  <td>{row.avg_review_score != null ? row.avg_review_score.toFixed(1) : "—"}</td>
                  <td>{row.dominant_sentiment ?? "—"}</td>
                  <td>{row.top_category ?? "—"}</td>
                  <td>
                    {row.recommended_category
                      ? row.recommended_category_lift != null
                        ? <span title={`Règle d'association, lift=${row.recommended_category_lift.toFixed(4)}`}>{row.recommended_category} <span style={{ color: "var(--status-good)", fontSize: 11 }}>(règle)</span></span>
                        : <span title="Pas de règle d'association pour ce client : catégorie la plus vendue globalement">{row.recommended_category} <span style={{ color: "var(--text-muted)", fontSize: 11 }}>(populaire)</span></span>
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

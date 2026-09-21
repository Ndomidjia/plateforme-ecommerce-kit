import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { ExportCsvButton } from "../components/ExportCsvButton";
import { useApiQuery } from "../hooks/useApiQuery";

const RISK_COLOR = { low: "var(--status-good)", medium: "var(--status-warning)", high: "var(--status-critical)" };
const RISK_LABEL = { low: "Faible", medium: "Moyen", high: "Élevé" };
const ORDER = ["low", "medium", "high"];

export default function Churn() {
  const [riskFilter, setRiskFilter] = useState("");
  const summary = useApiQuery((token) => api.churnSummary(token), []);
  const list = useApiQuery((token) => api.churnList(token, { risk_level: riskFilter || undefined, limit: 50 }), [riskFilter]);
  const importance = useApiQuery((token) => api.churnFeatureImportance(token), []);
  const returns = useApiQuery((token) => api.returnsByRisk(token), []);
  const actions = useApiQuery((token) => api.marketingActions(token, { risk_level: "high", limit: 20 }), []);

  // Tableaux dérivés mémorisés : cette page a 5 requêtes indépendantes,
  // chacune re-rend tout le composant à sa résolution. Sans useMemo, chaque
  // re-rendu recrée un nouveau tableau (même si les valeurs n'ont pas
  // changé), ce qui peut faire redémarrer l'animation d'entrée de Recharts
  // à répétition et laisser un graphique visuellement vide au mauvais moment.
  const chartData = useMemo(
    () => summary.data
      ? ORDER.map((level) => {
          const row = summary.data.find((r) => r.risk_level === level);
          return { risk_level: level, label: RISK_LABEL[level], count: row?.count ?? 0 };
        })
      : [],
    [summary.data],
  );

  const importanceData = useMemo(
    () => importance.data
      ? [...importance.data].reverse().map((d) => ({ ...d, feature: d.feature.replace(/^(num|cat)__/, "") }))
      : [],
    [importance.data],
  );

  const returnsData = useMemo(
    () => returns.data
      ? ORDER.map((l) => returns.data.find((r) => r.risk_level === l)).filter(Boolean).map((r) => ({ ...r, label: RISK_LABEL[r.risk_level] }))
      : [],
    [returns.data],
  );

  return (
    <>
      <h2>Scoring churn (Random Forest)</h2>

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
          Répartition des clients par niveau de risque
        </h3>
        {summary.loading && <p>Chargement…</p>}
        {summary.error && <div className="error-box">{summary.error.message}</div>}
        {summary.data && (
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
        )}
      </div>

      <div style={{ display: "flex", gap: 20 }}>
        <div className="card" style={{ flex: 1 }}>
          <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
            Variables les plus déterminantes (Random Forest)
          </h3>
          {importance.loading && <p>Chargement…</p>}
          {importance.error && <div className="error-box">{importance.error.message}</div>}
          {importance.data && (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                data={importanceData}
                layout="vertical"
                margin={{ top: 8, right: 24, left: 100, bottom: 8 }}
              >
                <CartesianGrid stroke="var(--gridline)" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: "var(--text-muted)" }} stroke="var(--baseline)" />
                <YAxis type="category" dataKey="feature" width={140} tick={{ fontSize: 11, fill: "var(--text-muted)" }} stroke="var(--baseline)" />
                <Tooltip
                  formatter={(v) => v.toFixed(4)}
                  contentStyle={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13 }}
                />
                <Bar dataKey="importance" name="Importance" fill="var(--series-1)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card" style={{ flex: 1 }}>
          <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
            Taux de retour produit moyen par risque
          </h3>
          {returns.loading && <p>Chargement…</p>}
          {returns.error && <div className="error-box">{returns.error.message}</div>}
          {returns.data && (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={returnsData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                <CartesianGrid stroke="var(--gridline)" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 13, fill: "var(--text-muted)" }} stroke="var(--baseline)" />
                <YAxis tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--baseline)" />
                <Tooltip
                  formatter={(v) => v.toFixed(2)}
                  contentStyle={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13 }}
                />
                <Bar dataKey="avg_returns_rate" name="Taux de retour moyen" radius={[4, 4, 0, 0]} maxBarSize={80}>
                  {ORDER.map((l) => (
                    <Cell key={l} fill={RISK_COLOR[l]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
          Plan d'action marketing (clients à risque élevé)
        </h3>
        <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 0 }}>
          Pour chaque client à risque, le facteur retenu est celui où il s'écarte le plus de la
          moyenne des clients, pondéré par l'importance de la variable dans le modèle — une
          heuristique d'aide à la décision, pas un diagnostic causal garanti.
        </p>
        {actions.loading && <p>Chargement…</p>}
        {actions.error && <div className="error-box">{actions.error.message}</div>}
        {actions.data && (
          <table>
            <thead><tr><th>Client</th><th>Proba churn</th><th>Facteur principal</th><th>Action recommandée</th></tr></thead>
            <tbody>
              {actions.data.map((a) => (
                <tr key={a.customer_id}>
                  <td>#{a.customer_id}</td>
                  <td>{(a.churn_proba * 100).toFixed(1)}%</td>
                  <td>{a.primary_risk_factor}</td>
                  <td>{a.recommended_action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <div className="filters">
          <label htmlFor="risk-select" style={{ fontSize: 13, color: "var(--text-secondary)" }}>Niveau de risque</label>
          <select id="risk-select" value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)}>
            <option value="">Tous</option>
            <option value="high">Élevé</option>
            <option value="medium">Moyen</option>
            <option value="low">Faible</option>
          </select>
          <ExportCsvButton data={list.data} filename="churn_scores.csv" />
        </div>

        {list.loading && <p>Chargement…</p>}
        {list.error && <div className="error-box">{list.error.message}</div>}
        {list.data && (
          <table>
            <thead>
              <tr><th>Client</th><th>Probabilité de churn</th><th>Risque</th></tr>
            </thead>
            <tbody>
              {list.data.map((row) => (
                <tr key={row.customer_id}>
                  <td>#{row.customer_id}</td>
                  <td>{(row.churn_proba * 100).toFixed(1)}%</td>
                  <td><span className={`badge ${row.risk_level}`}>{RISK_LABEL[row.risk_level]}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

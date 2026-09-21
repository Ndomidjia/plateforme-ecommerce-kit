import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { ExportCsvButton } from "../components/ExportCsvButton";
import { StatTile } from "../components/StatTile";
import { useApiQuery } from "../hooks/useApiQuery";

// Codes d'état brésiliens (IBGE) -> nom complet. La donnée brute (code) reste
// celle renvoyée par l'API ; la traduction n'est faite qu'à l'affichage.
const STATE_NAMES = {
  AC: "Acre", AL: "Alagoas", AP: "Amapá", AM: "Amazonas", BA: "Bahia",
  CE: "Ceará", DF: "District fédéral", ES: "Espírito Santo", GO: "Goiás",
  MA: "Maranhão", MT: "Mato Grosso", MS: "Mato Grosso do Sud", MG: "Minas Gerais",
  PA: "Pará", PB: "Paraíba", PR: "Paraná", PE: "Pernambouc", PI: "Piauí",
  RJ: "Rio de Janeiro", RN: "Rio Grande do Norte", RS: "Rio Grande do Sud",
  RO: "Rondônia", RR: "Roraima", SC: "Santa Catarina", SP: "São Paulo",
  SE: "Sergipe", TO: "Tocantins",
};

// Ordre catégoriel fixe (jamais recalculé selon le tri/filtre courant).
const SEGMENT_COLOR = {
  "Champions": "var(--series-1)",
  "Fidèles": "var(--series-2)",
  "Nouveaux / Prometteurs": "var(--series-3)",
  "À risque": "var(--series-4)",
  "En sommeil": "var(--series-5)",
  "Autres": "var(--series-6)",
};

export default function Rfm() {
  const [segmentFilter, setSegmentFilter] = useState("");
  const summary = useApiQuery((token) => api.rfmSummary(token), []);
  const list = useApiQuery((token) => api.rfmList(token, { segment: segmentFilter || undefined, limit: 50 }), [segmentFilter]);
  const geo = useApiQuery((token) => api.geoDistribution(token), []);
  const delivery = useApiQuery((token) => api.deliveryKpi(token), []);
  const payments = useApiQuery((token) => api.paymentMethods(token), []);

  return (
    <>
      <h2>Segmentation RFM (Olist)</h2>

      {delivery.data && (
        <div style={{ display: "flex", gap: 16, marginBottom: 20 }}>
          <StatTile label="Délai de livraison moyen" value={`${delivery.data.avg_delivery_days.toFixed(1)} j`} />
          <StatTile
            label="Écart vs estimation"
            value={`${delivery.data.avg_delay_vs_estimate_days >= 0 ? "+" : ""}${delivery.data.avg_delay_vs_estimate_days.toFixed(1)} j`}
          />
          <StatTile label="Livraisons en retard" value={`${(delivery.data.pct_late_deliveries * 100).toFixed(1)}%`} />
        </div>
      )}

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
          Nombre de clients par segment
        </h3>
        {summary.loading && <p>Chargement…</p>}
        {summary.error && <div className="error-box">{summary.error.message}</div>}
        {summary.data && (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={summary.data} layout="vertical" margin={{ top: 8, right: 24, left: 100, bottom: 8 }}>
              <CartesianGrid stroke="var(--gridline)" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--baseline)" />
              <YAxis type="category" dataKey="segment" width={140} tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--baseline)" />
              <Tooltip
                formatter={(v) => v.toLocaleString("fr-FR")}
                contentStyle={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13 }}
              />
              <Bar dataKey="count" name="Clients" radius={[0, 4, 4, 0]}>
                {summary.data.map((d) => (
                  <Cell key={d.segment} fill={SEGMENT_COLOR[d.segment] ?? "var(--series-7)"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
          Répartition géographique (top 10 états)
        </h3>
        {geo.loading && <p>Chargement…</p>}
        {geo.error && <div className="error-box">{geo.error.message}</div>}
        {geo.data && (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={geo.data.slice(0, 10).map((d) => ({ ...d, state_label: STATE_NAMES[d.customer_state] ?? d.customer_state }))}
              layout="vertical"
              margin={{ top: 8, right: 24, left: 20, bottom: 8 }}
            >
              <CartesianGrid stroke="var(--gridline)" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--baseline)" />
              <YAxis type="category" dataKey="state_label" width={140} tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--baseline)" />
              <Tooltip
                formatter={(v) => v.toLocaleString("fr-FR")}
                contentStyle={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13 }}
              />
              <Bar dataKey="customer_count" name="Clients" fill="var(--series-1)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
          Répartition des moyens de paiement
        </h3>
        {payments.loading && <p>Chargement…</p>}
        {payments.error && <div className="error-box">{payments.error.message}</div>}
        {payments.data && (
          <table>
            <thead><tr><th>Moyen de paiement</th><th>Nb transactions</th><th>Montant moyen</th><th>Montant total</th></tr></thead>
            <tbody>
              {payments.data.map((p) => (
                <tr key={p.payment_type}>
                  <td>{p.payment_type}</td>
                  <td>{p.count.toLocaleString("fr-FR")}</td>
                  <td>{p.avg_value.toFixed(2)} R$</td>
                  <td>{p.total_value.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} R$</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <div className="filters">
          <label htmlFor="segment-select" style={{ fontSize: 13, color: "var(--text-secondary)" }}>Segment</label>
          <select id="segment-select" value={segmentFilter} onChange={(e) => setSegmentFilter(e.target.value)}>
            <option value="">Tous</option>
            {Object.keys(SEGMENT_COLOR).map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <ExportCsvButton data={list.data} filename="rfm_segments.csv" />
        </div>

        {list.loading && <p>Chargement…</p>}
        {list.error && <div className="error-box">{list.error.message}</div>}
        {list.data && (
          <table>
            <thead>
              <tr><th>Client</th><th>Récence (j)</th><th>Fréquence</th><th>Montant</th><th>Segment</th></tr>
            </thead>
            <tbody>
              {list.data.map((row) => (
                <tr key={row.customer_unique_id}>
                  <td title={row.customer_unique_id}>{row.customer_unique_id.slice(0, 10)}…</td>
                  <td>{row.recency_days}</td>
                  <td>{row.frequency}</td>
                  <td>{row.monetary.toFixed(2)} R$</td>
                  <td>{row.segment}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

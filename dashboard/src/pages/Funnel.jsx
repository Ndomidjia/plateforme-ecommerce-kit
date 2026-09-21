import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { StatTile } from "../components/StatTile";
import { useApiQuery } from "../hooks/useApiQuery";

export default function Funnel() {
  const { data, loading, error } = useApiQuery((token) => api.funnel(token), []);

  if (loading) return <p>Chargement…</p>;
  if (error) return <div className="error-box">{error.message}</div>;

  // La ligne "globale" (synthèse sur toute la période) couvre ~4,5 mois et
  // fausserait le graphique hebdomadaire : on l'isole pour les stat tiles.
  const global = data.reduce((a, b) => (durationDays(b) > durationDays(a) ? b : a));
  const weekly = data.filter((row) => row !== global).sort((a, b) => a.period_start.localeCompare(b.period_start));

  return (
    <>
      <h2>Funnel de conversion (Retailrocket)</h2>

      <div style={{ display: "flex", gap: 16, marginBottom: 20 }}>
        <StatTile label="Visiteurs (vue)" value={global.views.toLocaleString("fr-FR")} />
        <StatTile label="Ajouts panier" value={global.addtocarts.toLocaleString("fr-FR")} />
        <StatTile label="Transactions" value={global.transactions.toLocaleString("fr-FR")} />
        <StatTile label="Conversion globale" value={`${(global.view_to_cart_rate * global.cart_to_buy_rate * 100).toFixed(2)}%`} />
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
          Taux de conversion par semaine
        </h3>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={weekly} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
            <CartesianGrid stroke="var(--gridline)" vertical={false} />
            <XAxis dataKey="period_start" tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--baseline)" />
            <YAxis tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--baseline)" />
            <Tooltip
              formatter={(v) => `${(v * 100).toFixed(2)}%`}
              contentStyle={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13 }}
            />
            <Legend wrapperStyle={{ fontSize: 13 }} />
            <Line type="monotone" dataKey="view_to_cart_rate" name="Vue → panier" stroke="var(--series-1)" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="cart_to_buy_rate" name="Panier → achat" stroke="var(--series-2)" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

function durationDays(row) {
  return (new Date(row.period_end) - new Date(row.period_start)) / 86400000;
}

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { ExportCsvButton } from "../components/ExportCsvButton";
import { useApiQuery } from "../hooks/useApiQuery";

const SENTIMENT_COLOR = { negative: "var(--status-critical)", neutral: "var(--status-warning)", positive: "var(--status-good)" };
const SENTIMENT_LABEL = { negative: "Négatif", neutral: "Neutre", positive: "Positif" };
const ORDER = ["negative", "neutral", "positive"];

export default function Sentiment() {
  const [sentimentFilter, setSentimentFilter] = useState("");
  const summary = useApiQuery((token) => api.sentimentSummary(token), []);
  const trend = useApiQuery((token) => api.sentimentTrend(token), []);
  const list = useApiQuery((token) => api.sentimentList(token, { sentiment: sentimentFilter || undefined, limit: 50 }), [sentimentFilter]);

  const chartData = summary.data
    ? ORDER.map((s) => {
        const row = summary.data.find((r) => r.sentiment === s);
        return { sentiment: s, label: SENTIMENT_LABEL[s], count: row?.count ?? 0 };
      })
    : [];

  return (
    <>
      <h2>Analyse de sentiment (deep learning, avis Olist)</h2>
      <div className="card">
        <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 0 }}>
          Réseau de neurones (PyTorch) entraîné sur les commentaires texte des avis. Le sentiment
          est dérivé par apprentissage faible depuis la note laissée par le client (1-2★ = négatif,
          3★ = neutre, 4-5★ = positif) : il n'existe pas d'étiquette de sentiment annotée
          manuellement dans ce dataset. Scores calculés par validation croisée (chaque avis est
          noté par un modèle qui ne l'a pas vu à l'entraînement).
        </p>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
          Répartition des avis par sentiment
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
              <Bar dataKey="count" name="Avis" radius={[4, 4, 0, 0]} maxBarSize={80}>
                {chartData.map((d) => (
                  <Cell key={d.sentiment} fill={SENTIMENT_COLOR[d.sentiment]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
          Évolution du taux d'avis négatifs dans le temps
        </h3>
        {trend.loading && <p>Chargement…</p>}
        {trend.error && <div className="error-box">{trend.error.message}</div>}
        {trend.data && (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={trend.data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid stroke="var(--gridline)" vertical={false} />
              <XAxis dataKey="period" tick={{ fontSize: 11, fill: "var(--text-muted)" }} stroke="var(--baseline)" />
              <YAxis tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--baseline)" />
              <Tooltip
                formatter={(v) => `${(v * 100).toFixed(1)}%`}
                contentStyle={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13 }}
              />
              <Legend wrapperStyle={{ fontSize: 13 }} />
              <Line type="monotone" dataKey="pct_negative" name="% avis négatifs" stroke="var(--status-critical)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="card">
        <div className="filters">
          <label htmlFor="sentiment-select" style={{ fontSize: 13, color: "var(--text-secondary)" }}>Sentiment</label>
          <select id="sentiment-select" value={sentimentFilter} onChange={(e) => setSentimentFilter(e.target.value)}>
            <option value="">Tous</option>
            <option value="negative">Négatif</option>
            <option value="neutral">Neutre</option>
            <option value="positive">Positif</option>
          </select>
          <ExportCsvButton data={list.data} filename="review_sentiment.csv" />
        </div>

        {list.loading && <p>Chargement…</p>}
        {list.error && <div className="error-box">{list.error.message}</div>}
        {list.data && (
          <table>
            <thead>
              <tr><th>Avis</th><th>Commande</th><th>Note</th><th>Sentiment</th><th>Confiance</th></tr>
            </thead>
            <tbody>
              {list.data.map((row) => (
                <tr key={`${row.review_id}-${row.order_id}`}>
                  <td title={row.review_id}>{row.review_id.slice(0, 10)}…</td>
                  <td title={row.order_id}>{row.order_id.slice(0, 10)}…</td>
                  <td>{"★".repeat(row.review_score)}</td>
                  <td><span className={`badge ${row.sentiment}`}>{SENTIMENT_LABEL[row.sentiment]}</span></td>
                  <td>{(row.sentiment_proba * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

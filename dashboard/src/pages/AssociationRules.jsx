import { api } from "../api";
import { ExportCsvButton } from "../components/ExportCsvButton";
import { useApiQuery } from "../hooks/useApiQuery";

export default function AssociationRules() {
  const { data, loading, error } = useApiQuery((token) => api.associationRules(token, { limit: 50 }), []);

  return (
    <>
      <h2>Règles d'association (market basket, Olist)</h2>
      <div className="card">
        <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 0 }}>
          Un lift ≥ 1 (surligné) indique une association plus fréquente que le hasard ne le
          prédirait. Sur Olist, la quasi-totalité des paires de catégories ont un lift &lt; 1 :
          99,25% des commandes livrées ne portent que sur une seule catégorie.
        </p>
        <div className="filters" style={{ marginBottom: 10 }}>
          <ExportCsvButton data={data} filename="association_rules.csv" />
        </div>
        {loading && <p>Chargement…</p>}
        {error && <div className="error-box">{error.message}</div>}
        {data && (
          <table>
            <thead>
              <tr><th>Antécédent</th><th>Conséquent</th><th>Support</th><th>Confiance</th><th>Lift</th></tr>
            </thead>
            <tbody>
              {data.map((r, i) => (
                <tr key={i} style={r.lift >= 1 ? { background: "color-mix(in srgb, var(--status-good) 10%, transparent)" } : undefined}>
                  <td>{r.antecedents}</td>
                  <td>{r.consequents}</td>
                  <td>{r.support.toFixed(6)}</td>
                  <td>{(r.confidence * 100).toFixed(2)}%</td>
                  <td style={r.lift >= 1 ? { color: "var(--status-good)", fontWeight: 600 } : undefined}>{r.lift.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

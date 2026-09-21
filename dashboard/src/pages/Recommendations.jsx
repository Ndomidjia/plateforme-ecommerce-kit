import { useState } from "react";
import { api, ApiError } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useApiQuery } from "../hooks/useApiQuery";

export default function Recommendations() {
  const { token } = useAuth();
  const [itemId, setItemId] = useState("");
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const topItems = useApiQuery((t) => api.topItems(t, 10), []);

  async function search(id) {
    if (!id) return;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const data = await api.recommendations(token, id);
      setResults(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur inattendue");
    } finally {
      setLoading(false);
    }
  }

  function handleSearch(e) {
    e.preventDefault();
    search(itemId);
  }

  return (
    <>
      <h2>Recommandations item-item (Retailrocket)</h2>

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
          Produits les plus engageants
        </h3>
        {topItems.loading && <p>Chargement…</p>}
        {topItems.error && <div className="error-box">{topItems.error.message}</div>}
        {topItems.data && (
          <table>
            <thead><tr><th>Produit</th><th>Vues</th><th>Ajouts panier</th><th>Taux conversion</th><th></th></tr></thead>
            <tbody>
              {topItems.data.map((it) => (
                <tr key={it.item_id}>
                  <td>#{it.item_id}</td>
                  <td>{it.views.toLocaleString("fr-FR")}</td>
                  <td>{it.addtocarts.toLocaleString("fr-FR")}</td>
                  <td>{((it.addtocarts / it.views) * 100).toFixed(2)}%</td>
                  <td>
                    <button type="button" onClick={() => { setItemId(String(it.item_id)); search(it.item_id); }}>
                      Voir les recos
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <form className="filters" onSubmit={handleSearch}>
          <label htmlFor="item-id" style={{ fontSize: 13, color: "var(--text-secondary)" }}>ID produit</label>
          <input id="item-id" value={itemId} onChange={(e) => setItemId(e.target.value)} placeholder="ex: 460732" />
          <button type="submit" disabled={loading}>{loading ? "Recherche…" : "Rechercher"}</button>
        </form>

        {error && <div className="error-box">{error}</div>}
        {results && (
          <table>
            <thead>
              <tr><th>Produit recommandé</th><th>Score de similarité</th><th>Méthode</th></tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={`${r.recommended_item_id}-${r.method}`}>
                  <td>#{r.recommended_item_id}</td>
                  <td>{r.score.toFixed(4)}</td>
                  <td>{r.method}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

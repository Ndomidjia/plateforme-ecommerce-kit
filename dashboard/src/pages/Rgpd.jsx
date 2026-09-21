import { useState } from "react";
import { api, ApiError } from "../api";
import { useAuth } from "../auth/AuthContext";

export default function Rgpd() {
  const { token } = useAuth();
  const [customerId, setCustomerId] = useState("");
  const [exported, setExported] = useState(null);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleExport() {
    if (!customerId) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      setExported(await api.rgpdExport(token, customerId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur inattendue");
      setExported(null);
    } finally {
      setBusy(false);
    }
  }

  async function handleErase() {
    if (!customerId) return;
    if (!window.confirm(`Anonymiser définitivement le client #${customerId} ? Cette action est irréversible.`)) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.rgpdErase(token, customerId);
      setMessage(res.detail);
      setExported(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur inattendue");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h2>RGPD — droit d'accès et droit à l'oubli</h2>
      <div className="card">
        <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 0 }}>
          Réservé aux administrateurs. Chaque export ou suppression est tracé dans le journal
          d'audit (app.rgpd_audit_log). La suppression anonymise les champs identifiants
          (âge, genre, pays, ville) et conserve les métriques comportementales agrégées.
        </p>
        <div className="filters">
          <label htmlFor="customer-id" style={{ fontSize: 13, color: "var(--text-secondary)" }}>ID client (churn)</label>
          <input id="customer-id" value={customerId} onChange={(e) => setCustomerId(e.target.value)} placeholder="ex: 1" />
          <button type="button" onClick={handleExport} disabled={busy}>Exporter (droit d'accès)</button>
          <button type="button" onClick={handleErase} disabled={busy} style={{ color: "var(--status-critical)" }}>
            Anonymiser (droit à l'oubli)
          </button>
        </div>

        {error && <div className="error-box">{error}</div>}
        {message && <p style={{ color: "var(--status-good)", fontSize: 14 }}>{message}</p>}
        {exported && (
          <pre style={{ background: "var(--page-plane)", padding: 14, borderRadius: 8, fontSize: 12, overflowX: "auto" }}>
            {JSON.stringify(exported, null, 2)}
          </pre>
        )}
      </div>
    </>
  );
}

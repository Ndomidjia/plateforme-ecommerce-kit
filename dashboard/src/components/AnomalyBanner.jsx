const SEVERITY_COLOR = { warning: "var(--status-warning)", critical: "var(--status-critical)" };

export function AnomalyBanner({ anomalies }) {
  if (!anomalies || anomalies.length === 0) return null;

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <h3 style={{ marginTop: 0, fontSize: 14, color: "var(--text-secondary)" }}>
        Anomalies détectées automatiquement
      </h3>
      <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 0 }}>
        Écart statistique (z-score) de la période la plus récente par rapport à l'historique —
        détecte un changement anormal dans l'état actuel, pas une recherche rétroactive dans
        tout l'historique.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {anomalies.map((a, i) => (
          <div
            key={i}
            style={{
              display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 8,
              border: `1px solid ${SEVERITY_COLOR[a.severity]}`,
              background: `color-mix(in srgb, ${SEVERITY_COLOR[a.severity]} 10%, var(--surface-1))`,
              fontSize: 13,
            }}
          >
            <span style={{ fontWeight: 700, color: SEVERITY_COLOR[a.severity] }}>
              z={a.z_score.toFixed(2)}
            </span>
            <span>
              <strong>{a.metric}</strong> ({a.period}) : {(a.value * 100).toFixed(2)}% observé vs{" "}
              {(a.expected_value * 100).toFixed(2)}% attendu
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

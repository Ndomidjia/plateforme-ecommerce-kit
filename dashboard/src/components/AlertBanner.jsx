const SEVERITY_COLOR = { warning: "var(--status-warning)", critical: "var(--status-critical)" };
const SEVERITY_LABEL = { warning: "Attention", critical: "Critique" };

// Règles d'alerte : seuils métier appliqués aux KPIs de la page Vue
// d'ensemble. Chaque règle décrit sa propre condition et son message —
// ajouter un KPI surveillé ne demande qu'une entrée ici.
const RULES = [
  {
    id: "churn-high-risk",
    severity: (k) => (k.churn_pct_high_risk >= 0.25 ? "critical" : k.churn_pct_high_risk >= 0.15 ? "warning" : null),
    message: (k) => `${(k.churn_pct_high_risk * 100).toFixed(1)}% des clients sont à risque de churn élevé — envisager une campagne de rétention ciblée.`,
  },
  {
    id: "funnel-trend",
    severity: (k) => {
      if (k.funnel_trend_delta_pct === null || k.funnel_trend_delta_pct === undefined) return null;
      if (k.funnel_trend_delta_pct <= -0.15) return "critical";
      if (k.funnel_trend_delta_pct <= -0.05) return "warning";
      return null;
    },
    message: (k) => `Le taux de conversion a chuté de ${Math.abs(k.funnel_trend_delta_pct * 100).toFixed(1)}% par rapport à la semaine précédente.`,
  },
  {
    id: "reco-coverage",
    severity: (k) => (k.recommendation_catalog_coverage_pct < 0.1 ? "warning" : null),
    message: (k) => `La couverture du catalogue en recommandations est faible (${(k.recommendation_catalog_coverage_pct * 100).toFixed(1)}%) — peu de produits bénéficient d'une reco.`,
  },
  {
    id: "negative-reviews",
    severity: (k) => {
      if (k.pct_negative_reviews === null || k.pct_negative_reviews === undefined) return null;
      if (k.pct_negative_reviews >= 0.35) return "critical";
      if (k.pct_negative_reviews >= 0.25) return "warning";
      return null;
    },
    message: (k) => `${(k.pct_negative_reviews * 100).toFixed(1)}% des avis analysés sont négatifs — surveiller la satisfaction produit/livraison.`,
  },
];

export function AlertBanner({ kpis }) {
  const alerts = RULES
    .map((rule) => ({ ...rule, severity: rule.severity(kpis) }))
    .filter((a) => a.severity !== null);

  if (alerts.length === 0) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
      {alerts.map((a) => (
        <div
          key={a.id}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "10px 14px",
            borderRadius: 8,
            border: `1px solid ${SEVERITY_COLOR[a.severity]}`,
            background: `color-mix(in srgb, ${SEVERITY_COLOR[a.severity]} 10%, var(--surface-1))`,
            fontSize: 13,
          }}
        >
          <span style={{ fontWeight: 700, color: SEVERITY_COLOR[a.severity] }}>{SEVERITY_LABEL[a.severity]}</span>
          <span style={{ color: "var(--text-primary)" }}>{a.message(kpis)}</span>
        </div>
      ))}
    </div>
  );
}

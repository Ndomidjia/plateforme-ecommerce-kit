import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AlertBanner } from "./AlertBanner";

const BASE_KPIS = {
  churn_pct_high_risk: 0.1,
  funnel_trend_delta_pct: 0,
  recommendation_catalog_coverage_pct: 0.5,
  pct_negative_reviews: 0.1,
};

describe("AlertBanner", () => {
  it("renders nothing when every KPI is below its alert threshold", () => {
    const { container } = render(<AlertBanner kpis={BASE_KPIS} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a warning (not critical) when churn risk is between 15% and 25%", () => {
    render(<AlertBanner kpis={{ ...BASE_KPIS, churn_pct_high_risk: 0.2 }} />);
    expect(screen.getByText("Attention")).toBeInTheDocument();
    expect(screen.queryByText("Critique")).not.toBeInTheDocument();
  });

  it("shows a critical alert when churn risk is at or above 25%", () => {
    render(<AlertBanner kpis={{ ...BASE_KPIS, churn_pct_high_risk: 0.25 }} />);
    expect(screen.getByText("Critique")).toBeInTheDocument();
    expect(screen.getByText(/25\.0% des clients sont à risque/)).toBeInTheDocument();
  });

  it("does not alert on a conversion trend that improved", () => {
    render(<AlertBanner kpis={{ ...BASE_KPIS, funnel_trend_delta_pct: 0.2 }} />);
    expect(screen.queryByText(/conversion a chuté/)).not.toBeInTheDocument();
  });

  it("alerts critically on a conversion drop of 15% or more", () => {
    render(<AlertBanner kpis={{ ...BASE_KPIS, funnel_trend_delta_pct: -0.2 }} />);
    expect(screen.getByText(/conversion a chuté de 20\.0%/)).toBeInTheDocument();
  });

  it("does not alert when funnel_trend_delta_pct is null (no data yet)", () => {
    render(<AlertBanner kpis={{ ...BASE_KPIS, funnel_trend_delta_pct: null }} />);
    expect(screen.queryByText(/conversion a chuté/)).not.toBeInTheDocument();
  });

  it("warns on low recommendation catalog coverage", () => {
    render(<AlertBanner kpis={{ ...BASE_KPIS, recommendation_catalog_coverage_pct: 0.05 }} />);
    expect(screen.getByText(/couverture du catalogue/)).toBeInTheDocument();
  });

  it("stacks multiple simultaneous alerts", () => {
    render(
      <AlertBanner
        kpis={{ ...BASE_KPIS, churn_pct_high_risk: 0.3, pct_negative_reviews: 0.4 }}
      />
    );
    expect(screen.getByText(/à risque de churn élevé/)).toBeInTheDocument();
    expect(screen.getByText(/avis analysés sont négatifs/)).toBeInTheDocument();
  });
});

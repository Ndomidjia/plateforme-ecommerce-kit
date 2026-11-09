import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnomalyBanner } from "./AnomalyBanner";

describe("AnomalyBanner", () => {
  it("renders nothing when there are no anomalies", () => {
    const { container } = render(<AnomalyBanner anomalies={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when anomalies is null or undefined", () => {
    const { container: c1 } = render(<AnomalyBanner anomalies={null} />);
    expect(c1).toBeEmptyDOMElement();
    const { container: c2 } = render(<AnomalyBanner anomalies={undefined} />);
    expect(c2).toBeEmptyDOMElement();
  });

  it("renders the metric, period, observed and expected values for each anomaly", () => {
    render(
      <AnomalyBanner
        anomalies={[
          { severity: "critical", z_score: 3.2, metric: "sentiment négatif", period: "2016-12", value: 0.686, expected_value: 0.25 },
        ]}
      />
    );
    expect(screen.getByText(/z=3\.20/)).toBeInTheDocument();
    expect(screen.getByText("sentiment négatif")).toBeInTheDocument();
    expect(screen.getByText(/68\.60% observé/)).toBeInTheDocument();
    expect(screen.getByText(/25\.00% attendu/)).toBeInTheDocument();
  });

  it("renders one row per anomaly when several are reported at once", () => {
    render(
      <AnomalyBanner
        anomalies={[
          { severity: "warning", z_score: 2.1, metric: "conversion", period: "S42", value: 0.01, expected_value: 0.02 },
          { severity: "critical", z_score: 4.5, metric: "churn", period: "S43", value: 0.3, expected_value: 0.1 },
        ]}
      />
    );
    expect(screen.getByText(/z=2\.10/)).toBeInTheDocument();
    expect(screen.getByText(/z=4\.50/)).toBeInTheDocument();
  });
});

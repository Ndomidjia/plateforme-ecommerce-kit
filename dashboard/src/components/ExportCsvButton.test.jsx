import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExportCsvButton } from "./ExportCsvButton";
import * as csvModule from "../utils/csv";

describe("ExportCsvButton", () => {
  it("renders nothing when there is no data to export", () => {
    const { container: empty } = render(<ExportCsvButton data={[]} filename="x.csv" />);
    expect(empty).toBeEmptyDOMElement();

    const { container: nullData } = render(<ExportCsvButton data={null} filename="x.csv" />);
    expect(nullData).toBeEmptyDOMElement();
  });

  it("renders a button when there is data", () => {
    render(<ExportCsvButton data={[{ a: 1 }]} filename="x.csv" />);
    expect(screen.getByRole("button", { name: "Exporter CSV" })).toBeInTheDocument();
  });

  it("triggers downloadCsv with the given filename and data on click", () => {
    const spy = vi.spyOn(csvModule, "downloadCsv").mockImplementation(() => {});
    const data = [{ customer_id: 1, risk_level: "high" }];

    render(<ExportCsvButton data={data} filename="churn.csv" />);
    fireEvent.click(screen.getByRole("button", { name: "Exporter CSV" }));

    expect(spy).toHaveBeenCalledWith("churn.csv", data);
    spy.mockRestore();
  });
});

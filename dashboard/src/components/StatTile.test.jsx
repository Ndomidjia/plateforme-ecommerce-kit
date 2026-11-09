import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatTile } from "./StatTile";

describe("StatTile", () => {
  it("renders the label and the value", () => {
    render(<StatTile label="Clients Olist" value="96 096" />);
    expect(screen.getByText("Clients Olist")).toBeInTheDocument();
    expect(screen.getByText("96 096")).toBeInTheDocument();
  });

  it("renders a numeric value as text", () => {
    render(<StatTile label="Comptes admin" value={2} />);
    expect(screen.getByText("2")).toBeInTheDocument();
  });
});

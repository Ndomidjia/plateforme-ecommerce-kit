import { describe, expect, it } from "vitest";
import { rowsToCsv } from "./csv";

describe("rowsToCsv", () => {
  it("returns an empty string for no rows", () => {
    expect(rowsToCsv([])).toBe("");
    expect(rowsToCsv(null)).toBe("");
    expect(rowsToCsv(undefined)).toBe("");
  });

  it("writes a header row from the keys of the first object", () => {
    const csv = rowsToCsv([{ a: 1, b: 2 }]);
    expect(csv.split("\n")[0]).toBe("a,b");
  });

  it("writes one data row per object, in column order", () => {
    const csv = rowsToCsv([{ a: 1, b: "x" }, { a: 2, b: "y" }]);
    expect(csv).toBe("a,b\n1,x\n2,y");
  });

  it("quotes a cell containing a comma", () => {
    const csv = rowsToCsv([{ name: "Dupont, Jean" }]);
    expect(csv).toBe('name\n"Dupont, Jean"');
  });

  it("quotes and escapes a cell containing a double quote", () => {
    const csv = rowsToCsv([{ name: 'Le "Patron"' }]);
    expect(csv).toBe('name\n"Le ""Patron"""');
  });

  it("quotes a cell containing a newline", () => {
    const csv = rowsToCsv([{ note: "ligne1\nligne2" }]);
    expect(csv).toBe('note\n"ligne1\nligne2"');
  });

  it("renders null and undefined cells as an empty string, not the literal word", () => {
    const csv = rowsToCsv([{ a: null, b: undefined, c: 0 }]);
    expect(csv).toBe("a,b,c\n,,0");
  });

  it("does not quote a plain cell unnecessarily", () => {
    const csv = rowsToCsv([{ a: "bed_bath_table" }]);
    expect(csv).toBe("a\nbed_bath_table");
  });
});

import { downloadCsv } from "../utils/csv";

export function ExportCsvButton({ data, filename }) {
  if (!data || data.length === 0) return null;
  return (
    <button type="button" onClick={() => downloadCsv(filename, data)}>
      Exporter CSV
    </button>
  );
}

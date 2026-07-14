import { Download } from "lucide-react";
import { useState } from "react";

import type { DashboardMetric } from "../../api";
import { METRIC_LABELS } from "./catalog";
import { formatMetric } from "./format";

function drawText(
  context: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  font: string,
  color: string,
) {
  context.font = font;
  context.fillStyle = color;
  context.fillText(text, x, y);
}

export function ExportPng({
  title,
  subtitle,
  metrics,
}: {
  title: string;
  subtitle: string;
  metrics: DashboardMetric[];
}) {
  const [exporting, setExporting] = useState(false);

  const exportReport = async () => {
    setExporting(true);
    try {
      const canvas = document.createElement("canvas");
      canvas.width = 1440;
      canvas.height = 900;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("canvas_unavailable");
      context.fillStyle = "#f5f7fb";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.fillStyle = "#151b2b";
      context.fillRect(0, 0, canvas.width, 150);
      drawText(context, "ACCUMULATE · SOCIAL MEDIA", 74, 62, "700 22px system-ui", "#a9a2ff");
      drawText(context, title, 74, 112, "700 42px system-ui", "#ffffff");
      drawText(context, subtitle, 74, 194, "500 20px system-ui", "#69738a");

      metrics.slice(0, 6).forEach((metric, index) => {
        const column = index % 3;
        const row = Math.floor(index / 3);
        const x = 74 + column * 444;
        const y = 246 + row * 230;
        context.fillStyle = "#ffffff";
        context.beginPath();
        context.roundRect(x, y, 406, 190, 22);
        context.fill();
        drawText(context, METRIC_LABELS[metric.metric_id], x + 28, y + 48, "600 20px system-ui", "#69738a");
        drawText(context, formatMetric(metric), x + 28, y + 112, "700 42px system-ui", "#182238");
        const comparison = metric.delta_pct === null ? "Comparison unavailable" : `${metric.delta_pct >= 0 ? "+" : ""}${metric.delta_pct.toFixed(1)}% vs previous period`;
        drawText(context, comparison, x + 28, y + 154, "500 17px system-ui", "#69738a");
      });
      drawText(context, "Generated from the selected Brand scope. Unavailable values are not inferred.", 74, 838, "500 17px system-ui", "#69738a");

      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
      if (!blob) throw new Error("png_generation_failed");
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${title.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-")}-report.png`;
      anchor.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  return (
    <button className="secondary-button export-button" disabled={exporting} onClick={() => void exportReport()} type="button">
      <Download size={17} /> {exporting ? "Preparing…" : "Export PNG"}
    </button>
  );
}

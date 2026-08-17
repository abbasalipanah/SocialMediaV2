import { Download } from "lucide-react";
import html2canvas from "html2canvas";
import { useState } from "react";

import type { DashboardMetric } from "../../api";

const MAX_CAPTURE_PIXELS = 24_000_000;

function afterNextPaint() {
  return new Promise<void>((resolve) => {
    window.requestAnimationFrame(() => window.requestAnimationFrame(() => resolve()));
  });
}

function captureRoot(): HTMLElement {
  const root = document.querySelector<HTMLElement>(".route-content > main")
    ?? document.querySelector<HTMLElement>("main");
  if (!root) throw new Error("report_capture_root_unavailable");
  return root;
}

function captureScale(width: number, height: number): number {
  const pixelLimitedScale = Math.sqrt(MAX_CAPTURE_PIXELS / Math.max(1, width * height));
  return Math.max(1, Math.min(2, pixelLimitedScale));
}

export async function exportDashboardPng({
  title,
}: {
  title: string;
}) {
  // Let React remove the export popover before cloning the live application.
  await afterNextPaint();
  await document.fonts?.ready;

  const root = captureRoot();
  const bounds = root.getBoundingClientRect();
  // Keep the same horizontal layout as the live page. Recharts deliberately
  // exposes SVG labels outside its plot and that visual overflow must not
  // widen the capture or trigger a different responsive breakpoint.
  const width = Math.ceil(Math.max(1, root.clientWidth, bounds.width));
  const height = Math.ceil(Math.max(root.scrollHeight, root.clientHeight, bounds.height));
  const canvas = await html2canvas(root, {
    allowTaint: false,
    backgroundColor: "#f8fafc",
    height,
    ignoreElements: (element) => element.classList.contains("report-export-panel"),
    logging: false,
    scale: captureScale(width, height),
    scrollX: 0,
    scrollY: 0,
    useCORS: true,
    width,
    windowHeight: Math.max(window.innerHeight, height),
    windowWidth: window.innerWidth,
  });

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
  if (!blob) throw new Error("png_generation_failed");
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${title.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-")}-report.png`;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function ExportPng({
  title,
}: {
  title: string;
  subtitle: string;
  metrics: DashboardMetric[];
}) {
  const [exporting, setExporting] = useState(false);

  const exportReport = async () => {
    setExporting(true);
    try {
      await exportDashboardPng({ title });
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

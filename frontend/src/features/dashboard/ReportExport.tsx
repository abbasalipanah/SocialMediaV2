import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Image as ImageIcon,
  LoaderCircle,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  apiBlob,
  apiMutation,
  apiQuery,
  queryString,
  reportJobSchema,
  type DashboardMetric,
  type Platform,
  type ReportJob,
} from "../../api";
import type { DashboardTab } from "./catalog";
import { exportDashboardPng } from "./ExportPng";

type ReportSurface = "overview" | Platform;

type ReportExportProps = {
  surface: ReportSurface;
  tab: DashboardTab["id"];
  brandId: string;
  rollup: boolean;
  accountId?: number;
  startDate: string;
  endDate: string;
  title: string;
  subtitle: string;
  metrics: DashboardMetric[];
};

const POLL_INTERVAL_MS = 500;
const MAX_POLLS = 1_240;

function wait(milliseconds: number, signal: AbortSignal) {
  if (signal.aborted) return Promise.reject(new DOMException("Aborted", "AbortError"));
  return new Promise<void>((resolve, reject) => {
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    const timer = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, milliseconds);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function errorCopy(error: unknown): string {
  const detail = error instanceof Error ? error.message : "report_generation_failed";
  if (detail.includes("report_queue_full") || detail.includes("report_owner_job_limit")) {
    return "The report queue is busy. Please try again shortly.";
  }
  if (detail.includes("report_workbook_size_limit")) {
    return "This report is too large for one workbook. Choose a shorter date period.";
  }
  return "The Excel report could not be prepared. Please try again.";
}

export function ReportExport(props: ReportExportProps) {
  const [open, setOpen] = useState(false);
  const [job, setJob] = useState<ReportJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pngBusy, setPngBusy] = useState(false);
  const [starting, setStarting] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const excelBusy = starting || (job !== null && job.state !== "failed");

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node) && !excelBusy) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !excelBusy) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [excelBusy]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const exportPng = async () => {
    setError(null);
    setPngBusy(true);
    setOpen(false);
    try {
      await exportDashboardPng(props);
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "png_generation_failed";
      setError(`The PNG snapshot could not be prepared (${detail}). Please try again.`);
      setOpen(true);
    } finally {
      setPngBusy(false);
    }
  };

  const exportXlsx = async () => {
    setError(null);
    setStarting(true);
    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;
    try {
      const params = queryString({
        surface: props.surface,
        tab: props.surface === "overview" ? "overview" : props.tab,
        brand_id: props.brandId,
        rollup: props.rollup,
        start_date: props.startDate,
        end_date: props.endDate,
        account_id: props.accountId,
      });
      let current = await apiMutation(
        `/api/reports/xlsx${params}`,
        reportJobSchema,
        { method: "POST", signal: controller.signal },
      );
      setJob(current);
      for (let poll = 0; current.state !== "ready"; poll += 1) {
        if (current.state === "failed") {
          throw new Error(current.error_code ?? "report_generation_failed");
        }
        if (poll >= MAX_POLLS) throw new Error("report_generation_timeout");
        await wait(POLL_INTERVAL_MS, controller.signal);
        current = await apiQuery(
          `/api/reports/xlsx/${encodeURIComponent(current.job_id)}`,
          reportJobSchema,
          controller.signal,
        );
        setJob(current);
      }
      const result = await apiBlob(
        `/api/reports/xlsx/${encodeURIComponent(current.job_id)}/download`,
        { method: "POST", signal: controller.signal },
      );
      saveBlob(
        result.blob,
        result.filename ?? `accumulate-${props.surface}-${props.tab}-${props.endDate}.xlsx`,
      );
      setJob({ ...current, stage: "Downloaded" });
      window.setTimeout(() => {
        setJob(null);
        setOpen(false);
      }, 900);
    } catch (cause) {
      if (controller.signal.aborted) return;
      setError(errorCopy(cause));
      setJob(null);
    } finally {
      setStarting(false);
      if (abortRef.current === controller) abortRef.current = null;
    }
  };

  return (
    <div className="report-export" ref={rootRef}>
      <button
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label="Download report"
        className="dashboard-download-button"
        onClick={() => setOpen((current) => excelBusy || !current)}
        title={`${props.title} · ${props.startDate} to ${props.endDate}`}
        type="button"
      >
        {excelBusy ? <LoaderCircle className="report-export-spinner" size={19} /> : <Download size={19} />}
      </button>
      {open && (
        <div aria-label="Download report" className="report-export-panel" role="dialog">
          <div className="report-export-heading">
            <strong>Download report</strong>
            <span>Export the current scoped dashboard.</span>
          </div>
          {!job && !starting && (
            <div className="report-export-options">
              <button disabled={pngBusy} onClick={() => void exportPng()} type="button">
                <span><ImageIcon size={18} /></span>
                <span><strong>PNG snapshot</strong><small>Main dashboard screenshot</small></span>
              </button>
              <button disabled={pngBusy} onClick={() => void exportXlsx()} type="button">
                <span><FileSpreadsheet size={18} /></span>
                <span><strong>Excel workbook</strong><small>Charts and card data by sheet</small></span>
              </button>
            </div>
          )}
          {(job || starting) && (
            <div aria-live="polite" className="report-export-progress">
              <div>
                {job?.stage === "Downloaded" ? <CheckCircle2 size={19} /> : <LoaderCircle className="report-export-spinner" size={19} />}
                <span><strong>{job?.stage ?? "Joining report queue"}</strong><small>Temporary file · removed after download</small></span>
                <b>{job?.progress ?? 1}%</b>
              </div>
              <progress aria-label="Excel report progress" max="100" value={job?.progress ?? 1} />
            </div>
          )}
          {error && (
            <div className="report-export-error" role="alert">
              <AlertCircle size={17} /><span>{error}</span>
              <button onClick={() => setError(null)} type="button">Dismiss</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

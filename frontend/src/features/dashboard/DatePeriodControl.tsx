import { CalendarDays, Pencil } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import {
  RANGE_OPTIONS,
  type RangeKey,
  type ReportingPeriod,
} from "./catalog";

type DatePeriodControlProps = {
  ariaLabel: string;
  controlClassName: string;
  iconClassName?: string;
  label: string;
  onChange: (period: ReportingPeriod) => void;
  period: ReportingPeriod;
  resolvedEndDate: string;
  resolvedStartDate: string;
};

const DAY_MS = 86_400_000;

function latestSelectableDate(): string {
  return new Date(Date.now() - DAY_MS).toISOString().slice(0, 10);
}

function validationError(startDate: string, endDate: string, latestDate: string): string | null {
  if (!startDate || !endDate) return "Choose both a start and end date.";
  const start = Date.parse(`${startDate}T00:00:00Z`);
  const end = Date.parse(`${endDate}T00:00:00Z`);
  if (!Number.isFinite(start) || !Number.isFinite(end)) return "Choose valid dates.";
  if (end < start) return "End date must be on or after start date.";
  if (end > Date.parse(`${latestDate}T00:00:00Z`)) return "End date cannot be later than yesterday.";
  if ((end - start) / DAY_MS > 365) return "Selected period cannot exceed one year.";
  return null;
}

export function DatePeriodControl({
  ariaLabel,
  controlClassName,
  iconClassName,
  label,
  onChange,
  period,
  resolvedEndDate,
  resolvedStartDate,
}: DatePeriodControlProps) {
  const panelId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [displayedKey, setDisplayedKey] = useState<RangeKey>(period.key);
  const [draftStartDate, setDraftStartDate] = useState(period.startDate ?? resolvedStartDate);
  const [draftEndDate, setDraftEndDate] = useState(period.endDate ?? resolvedEndDate);
  const [open, setOpen] = useState(false);
  const [showError, setShowError] = useState(false);
  const latestDate = latestSelectableDate();
  const error = validationError(draftStartDate, draftEndDate, latestDate);

  useEffect(() => {
    setDisplayedKey(period.key);
    setDraftStartDate(period.startDate ?? resolvedStartDate);
    setDraftEndDate(period.endDate ?? resolvedEndDate);
  }, [period, resolvedEndDate, resolvedStartDate]);

  const closeEditor = () => {
    setOpen(false);
    setShowError(false);
    setDisplayedKey(period.key);
    setDraftStartDate(period.startDate ?? resolvedStartDate);
    setDraftEndDate(period.endDate ?? resolvedEndDate);
  };

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) closeEditor();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeEditor();
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, period, resolvedEndDate, resolvedStartDate]);

  const openEditor = () => {
    setDraftStartDate(period.startDate ?? resolvedStartDate);
    setDraftEndDate(period.endDate ?? resolvedEndDate);
    setDisplayedKey("selected_period");
    setShowError(false);
    setOpen(true);
  };

  const selectRange = (key: RangeKey) => {
    if (key === "selected_period") {
      openEditor();
      return;
    }
    setDisplayedKey(key);
    setOpen(false);
    setShowError(false);
    onChange({ key });
  };

  const apply = () => {
    if (error) {
      setShowError(true);
      return;
    }
    onChange({
      key: "selected_period",
      startDate: draftStartDate,
      endDate: draftEndDate,
    });
    setOpen(false);
    setShowError(false);
  };

  return (
    <div className="date-period-picker" ref={rootRef}>
      <label className={controlClassName}>
        <span className={iconClassName}><CalendarDays size={18} /></span>
        <span>
          <small>{label}</small>
          <select
            aria-controls={open ? panelId : undefined}
            aria-expanded={open}
            aria-label={ariaLabel}
            onChange={(event) => selectRange(event.target.value as RangeKey)}
            value={displayedKey}
          >
            {RANGE_OPTIONS.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
          </select>
        </span>
      </label>
      {displayedKey === "selected_period" && !open && (
        <button
          aria-label="Edit selected period"
          className="date-period-edit"
          onClick={openEditor}
          title={`${period.startDate ?? resolvedStartDate} to ${period.endDate ?? resolvedEndDate}`}
          type="button"
        >
          <Pencil size={14} />
        </button>
      )}
      {open && (
        <div aria-label="Selected period" className="date-period-panel" id={panelId} role="dialog">
          <strong>Selected Period</strong>
          <span>Choose a reporting range through yesterday.</span>
          <div className="date-period-fields">
            <label>
              <span>Start date</span>
              <input
                max={draftEndDate || latestDate}
                onChange={(event) => {
                  setDraftStartDate(event.target.value);
                  setShowError(false);
                }}
                type="date"
                value={draftStartDate}
              />
            </label>
            <label>
              <span>End date</span>
              <input
                max={latestDate}
                min={draftStartDate || undefined}
                onChange={(event) => {
                  setDraftEndDate(event.target.value);
                  setShowError(false);
                }}
                type="date"
                value={draftEndDate}
              />
            </label>
          </div>
          {showError && error && <p role="alert">{error}</p>}
          <div className="date-period-actions">
            <button onClick={closeEditor} type="button">Cancel</button>
            <button className="primary" onClick={apply} type="button">Apply</button>
          </div>
        </div>
      )}
    </div>
  );
}

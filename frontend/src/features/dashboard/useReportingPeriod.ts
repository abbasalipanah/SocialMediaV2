import { useCallback, useEffect, useState } from "react";

import { useAuth } from "../../auth";
import {
  DEFAULT_REPORTING_PERIOD,
  PRESET_RANGE_OPTIONS,
  type ReportingPeriod,
} from "./catalog";

const DAY_MS = 86_400_000;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const PRESET_KEYS = new Set<string>(PRESET_RANGE_OPTIONS.map((option) => option.id));

export function reportingPeriodStorageKey(userId: string): string {
  return `social-media-v2:reporting-period:${userId}`;
}

function validStoredDate(value: unknown): value is string {
  if (typeof value !== "string" || !DATE_PATTERN.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function parseStoredPeriod(raw: string | null): ReportingPeriod {
  if (!raw) return DEFAULT_REPORTING_PERIOD;
  try {
    const value = JSON.parse(raw) as Record<string, unknown>;
    if (PRESET_KEYS.has(String(value.key))) {
      return { key: value.key as ReportingPeriod["key"] };
    }
    if (
      value.key === "selected_period"
      && validStoredDate(value.startDate)
      && validStoredDate(value.endDate)
    ) {
      const start = Date.parse(`${value.startDate}T00:00:00Z`);
      const end = Date.parse(`${value.endDate}T00:00:00Z`);
      const latest = Date.now() - DAY_MS;
      if (start <= end && end <= latest && (end - start) / DAY_MS <= 365) {
        return {
          key: "selected_period",
          startDate: value.startDate,
          endDate: value.endDate,
        };
      }
    }
  } catch {
    // A broken browser preference must not make the dashboard unavailable.
  }
  return DEFAULT_REPORTING_PERIOD;
}

function readStoredPeriod(storageKey: string): ReportingPeriod {
  try {
    return parseStoredPeriod(window.localStorage.getItem(storageKey));
  } catch {
    return DEFAULT_REPORTING_PERIOD;
  }
}

export function useReportingPeriod(): readonly [ReportingPeriod, (period: ReportingPeriod) => void] {
  const { user } = useAuth();
  if (!user) throw new Error("useReportingPeriod requires an authenticated user");
  const storageKey = reportingPeriodStorageKey(user.user_id);
  const [period, setPeriod] = useState<ReportingPeriod>(() => readStoredPeriod(storageKey));

  useEffect(() => {
    setPeriod(readStoredPeriod(storageKey));
  }, [storageKey]);

  const updatePeriod = useCallback((nextPeriod: ReportingPeriod) => {
    setPeriod(nextPeriod);
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(nextPeriod));
    } catch {
      // The in-memory selection still works when browser storage is unavailable.
    }
  }, [storageKey]);

  useEffect(() => {
    const syncAcrossTabs = (event: StorageEvent) => {
      if (event.key === storageKey) {
        setPeriod(parseStoredPeriod(event.newValue));
      }
    };
    window.addEventListener("storage", syncAcrossTabs);
    return () => window.removeEventListener("storage", syncAcrossTabs);
  }, [storageKey]);

  return [period, updatePeriod] as const;
}

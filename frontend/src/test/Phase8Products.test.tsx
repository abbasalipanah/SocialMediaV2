import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DashboardMetric, ReportingAccount } from "../api";
import { MetricBand } from "../features/dashboard/DashboardCards";
import { platformTabs } from "../features/dashboard/catalog";
import { AccountsTable } from "../features/settings/SettingsTables";
import { Dialog } from "../ui";

const metric = (value: number | null, status: "available" | "partial" | "unavailable"): DashboardMetric => ({
  metric_id: "followers",
  value,
  previous_value: null,
  delta_pct: null,
  semantic_type: "snapshot",
  unit: "count",
  data_status: status,
});

const baseDashboard = {
  meta: {
    dashboard_id: "test",
    platform: "facebook" as const,
    requested_brand_id: "hotel-1",
    rollup: false,
    resolved_brand_ids: ["hotel-1"],
    resolved_account_ids: [1],
    date_range: { start_on: "2026-07-01", end_on: "2026-07-14", key: "last_30_days" },
    generated_at: "2026-07-14T12:00:00Z",
    last_sync_at: null,
    freshness: "never_synced" as const,
    observed_days: 0,
    expected_days: 30,
    data_status: "unavailable" as const,
    warnings: [],
  },
  series: [],
  breakdowns: [],
  content: [],
  community: {
    total_comments: 0,
    answered_comments: 0,
    unanswered_comments: 0,
    comment_likes: 0,
    data_status: "unavailable" as const,
  },
};

const account: ReportingAccount = {
  account_id: 17,
  brand_id: "hotel-1",
  platform: "facebook",
  external_id: "page-17",
  display_name: "Coastal Facebook",
  status: "active",
  connection_state: "connected",
  health_status: "healthy",
  backfill_status: "complete",
  nightly_enabled: true,
  last_synced_at: null,
};

describe("Phase 8 product surfaces", () => {
  it("keeps unavailable metrics honest instead of rendering a synthetic zero", () => {
    render(<MetricBand data={{ ...baseDashboard, metrics: [metric(null, "unavailable")] }} scope="facebook" />);
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
    expect(screen.getByText("Comparison unavailable")).toBeInTheDocument();
  });

  it("keeps Stories inside Instagram and gates TikTok Audience by capability", () => {
    expect(platformTabs("instagram", true).map((tab) => tab.label)).toEqual([
      "Cover", "Page", "Content", "Stories", "Audience",
    ]);
    expect(platformTabs("tiktok", false).map((tab) => tab.label)).toEqual(["Overview", "Videos"]);
    expect(platformTabs("tiktok", true).map((tab) => tab.label)).toEqual(["Overview", "Videos", "Audience"]);
  });

  it("filters the table and leaves manual sync disabled when backend mutation is unavailable", async () => {
    const user = userEvent.setup();
    render(<AccountsTable items={[account]} mutationAvailable={false} />);
    expect(screen.getByText("Coastal Facebook")).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText("Search this view"), "missing");
    expect(screen.getByText("No matching records.")).toBeInTheDocument();
    await user.clear(screen.getByPlaceholderText("Search this view"));
    await user.click(screen.getByRole("button", { name: "Review Coastal Facebook" }));
    expect(screen.getByRole("dialog", { name: "Coastal Facebook" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sync now/ })).toBeDisabled();
  });

  it("traps an accessible dialog, closes on Escape and returns focus", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { rerender } = render(<><button type="button">Launch setup</button><Dialog onClose={onClose} open={false} title="Setup"><button type="button">First action</button></Dialog></>);
    screen.getByRole("button", { name: "Launch setup" }).focus();
    rerender(<><button type="button">Launch setup</button><Dialog onClose={onClose} open title="Setup"><button type="button">First action</button><button type="button">Last action</button></Dialog></>);
    expect(await screen.findByRole("dialog", { name: "Setup" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
    rerender(<><button type="button">Launch setup</button><Dialog onClose={onClose} open={false} title="Setup"><button type="button">First action</button></Dialog></>);
    expect(screen.getByRole("button", { name: "Launch setup" })).toHaveFocus();
  });
});

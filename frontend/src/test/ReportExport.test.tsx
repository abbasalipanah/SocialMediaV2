import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReportExport } from "../features/dashboard/ReportExport";

const readyJob = {
  job_id: "report-job-1",
  state: "ready",
  progress: 100,
  stage: "Ready to download",
  filename: "accumulate-pine-beach-instagram-stories-2026-08-09.xlsx",
  created_at: "2026-08-10T12:00:00Z",
  expires_at: "2026-08-10T12:10:00Z",
  error_code: null,
};

afterEach(() => {
  vi.restoreAllMocks();
  Reflect.deleteProperty(URL, "createObjectURL");
  Reflect.deleteProperty(URL, "revokeObjectURL");
});

describe("ReportExport", () => {
  it("queues the exact dashboard scope, reports 100%, and downloads once", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(readyJob), {
          status: 202,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(new Blob(["xlsx"]), {
          status: 200,
          headers: {
            "Content-Disposition": `attachment; filename="${readyJob.filename}"`,
            "Content-Type":
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          },
        }),
      );
    const createObjectURL = vi.fn(() => "blob:report");
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: createObjectURL,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    render(
      <ReportExport
        accountId={1412}
        brandId="1410"
        endDate="2026-08-09"
        metrics={[]}
        rollup={false}
        startDate="2026-07-11"
        subtitle="Pine Beach Belek"
        surface="instagram"
        tab="stories"
        title="Instagram Stories"
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Download report" }));
    const dialog = screen.getByRole("dialog", { name: "Download report" });
    await user.click(within(dialog).getByRole("button", { name: /Excel workbook/i }));

    await screen.findByText("Downloaded");
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByText(/removed after download/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      "/api/reports/xlsx?surface=instagram&tab=stories&brand_id=1410&rollup=false&start_date=2026-07-11&end_date=2026-08-09&account_id=1412",
    );
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: "POST" });
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "/api/reports/xlsx/report-job-1/download",
    );
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: "POST" });
    await waitFor(() => expect(createObjectURL).toHaveBeenCalledOnce());
  });
});

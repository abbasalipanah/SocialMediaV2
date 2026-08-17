import html2canvas from "html2canvas";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { exportDashboardPng } from "../features/dashboard/ExportPng";

vi.mock("html2canvas", () => ({ default: vi.fn() }));

const renderPage = vi.mocked(html2canvas);

beforeEach(() => {
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    callback(0);
    return 1;
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  Reflect.deleteProperty(URL, "createObjectURL");
  Reflect.deleteProperty(URL, "revokeObjectURL");
});

describe("main dashboard PNG export", () => {
  it("renders only the complete main layout instead of the app chrome or rebuilt metric cards", async () => {
    const shell = document.createElement("div");
    shell.className = "app-frame";
    shell.innerHTML = `
      <aside class="app-sidebar">Navigation</aside>
      <header class="app-topbar">Workspace</header>
      <div class="route-content">
        <main>Complete dashboard layout<div class="report-export-panel">Open export menu</div></main>
      </div>
    `;
    const root = shell.querySelector("main")!;
    Object.defineProperties(root, {
      clientHeight: { configurable: true, value: 900 },
      clientWidth: { configurable: true, value: 1440 },
      scrollHeight: { configurable: true, value: 1800 },
      // Simulate a chart label overflowing the main layout horizontally.
      scrollWidth: { configurable: true, value: 1900 },
    });
    vi.spyOn(root, "getBoundingClientRect").mockReturnValue({
      bottom: 900,
      height: 900,
      left: 0,
      right: 1440,
      toJSON: () => ({}),
      top: 0,
      width: 1440,
      x: 0,
      y: 0,
    });
    document.body.append(shell);
    vi.spyOn(window, "innerWidth", "get").mockReturnValue(1920);

    const toBlob = vi.fn((callback: BlobCallback) => callback(new Blob(["png"], { type: "image/png" })));
    renderPage.mockResolvedValue({ toBlob } as unknown as HTMLCanvasElement);
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:dashboard") });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    const download = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    await exportDashboardPng({ title: "Social Media Overview" });
    await new Promise<void>((resolve) => window.setTimeout(resolve, 0));

    expect(renderPage).toHaveBeenCalledOnce();
    const [captureTarget, options] = renderPage.mock.calls[0]!;
    expect(captureTarget).toBe(root);
    expect(options).toMatchObject({
      backgroundColor: "#f8fafc",
      height: 1800,
      scrollX: 0,
      scrollY: 0,
      useCORS: true,
      width: 1440,
      windowHeight: 1800,
      windowWidth: 1920,
    });
    expect(options?.ignoreElements?.(root.querySelector(".report-export-panel")!)).toBe(true);
    expect(toBlob).toHaveBeenCalledOnce();
    expect(download).toHaveBeenCalledOnce();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:dashboard");
  });
});

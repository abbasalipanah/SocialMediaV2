import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const frontendRoot = process.cwd();
const STYLES = readFileSync(resolve(frontendRoot, "src/styles.css"), "utf8");
const DRAWER = readFileSync(
  resolve(frontendRoot, "src/features/settings/SetupDrawer.tsx"),
  "utf8",
);

function zIndexOf(selector: string): number {
  const rule = STYLES.split("\n").find(
    (line) => line.startsWith(`${selector} {`) && line.includes("z-index"),
  );
  if (!rule) throw new Error(`no z-index rule for ${selector}`);
  return Number(/z-index:\s*(\d+)/.exec(rule)?.[1]);
}

describe("connection modal stacking", () => {
  it("puts the connection dialog above the drawer that opens it", () => {
    // Both sat at 100, so with equal stacking the drawer won on DOM order and
    // the dialog rendered behind it: visible, dimmed, impossible to click.
    expect(zIndexOf(".tiktok-connect-layer")).toBeGreaterThan(zIndexOf(".dialog-layer"));
  });

  it("reads a platform's state from the account, not the connection list", () => {
    // A Meta connection is stored once under `facebook` and serves Instagram
    // too, so a per-platform lookup called a linked Instagram profile
    // "Not Connected".
    expect(DRAWER).toContain("linked[0]?.connection_state");
  });
});

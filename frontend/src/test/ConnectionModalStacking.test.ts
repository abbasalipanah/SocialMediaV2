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

describe("connection modal mounting", () => {
  const MODALS = ["TikTokConnectionModal", "MetaConnectionModal"] as const;

  it("mounts each connection modal through a portal", () => {
    // The dialog that opens them portals to the document body. A modal left in
    // the page tree sits in whatever stacking context an ancestor creates and
    // cannot rise above that dialog, whatever z-index it carries -- raising the
    // z-index alone did not bring it forward.
    for (const modal of MODALS) {
      const source = readFileSync(
        resolve(frontendRoot, `src/features/integrations/${modal}.tsx`),
        "utf8",
      );
      expect(source).toContain('from "react-dom"');
      expect(source).toContain("return createPortal(");
      expect(source).toContain("document.body,");
    }
  });
});

describe("authorization window lifetime", () => {
  const MODALS = ["TikTokConnectionModal", "MetaConnectionModal"] as const;

  function source(modal: string): string {
    return readFileSync(
      resolve(frontendRoot, `src/features/integrations/${modal}.tsx`),
      "utf8",
    );
  }

  it("does not close the popup from effect cleanup", () => {
    // The cleanup ran on any re-render that re-ran the effect -- a refetch on
    // window focus, a changed Brand -- and killed the authorization window the
    // moment it opened, which read as "it closes before the page appears".
    for (const modal of MODALS) {
      const cleanup = /return \(\) => \{([\s\S]*?)\};/.exec(source(modal))?.[1] ?? "";
      expect(cleanup).toContain("removeEventListener");
      expect(cleanup).not.toContain("close()");
    }
  });

  it("closes the popup when the dialog is deliberately dismissed", () => {
    for (const modal of MODALS) {
      const text = source(modal);
      expect(text).toContain("const dismiss = () => {");
      expect(text).not.toContain("onClick={onClose}");
    }
  });
});

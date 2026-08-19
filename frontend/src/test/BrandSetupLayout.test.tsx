import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const frontendRoot = process.cwd();
const SOURCE = readFileSync(
  resolve(frontendRoot, "src/features/settings/SetupDrawer.tsx"),
  "utf8",
);
const STYLES = readFileSync(resolve(frontendRoot, "src/styles.css"), "utf8");

/**
 * Brand Setup was a four-step wizard: it opened on a list of every Brand in
 * scope, said nothing about the one being set up, and hid the other three
 * quarters of its state behind Continue. It now reads the way Brand Setup reads
 * in Performance Marketing -- one scrolling page of numbered sections.
 */
describe("Brand Setup layout", () => {
  it("shows the four sections on one page rather than as wizard steps", () => {
    for (const title of ["Brand Information", "Social Accounts", "Sync Settings", "Readiness"]) {
      expect(SOURCE).toContain(`title="${title}"`);
    }
    expect(SOURCE).not.toMatch(/Step \{?\w* ?\+ ?1\}? of/);
    expect(SOURCE).not.toContain("Continue");
  });

  it("numbers the sections", () => {
    expect(SOURCE).toContain("{index}. {title}");
  });

  it("describes the Brand whose row was clicked", () => {
    // Opening setup from a row and then showing the session's Brand meant every
    // row opened the same one -- whichever Brand Accumulate launched.
    expect(SOURCE).toContain("brand: SettingsBrand | null");
    expect(SOURCE).not.toContain("selectedBrandId");
  });

  it("scopes accounts, connections and jobs to that Brand", () => {
    for (const collection of ["accounts", "connections", "jobs"]) {
      expect(SOURCE).toContain(
        `${collection}.filter(`,
      );
    }
    expect(SOURCE).toContain("=== brand.brand_id");
  });

  it("does not offer linking the backend would refuse", () => {
    // A provider connection is bound to the Brand the session was launched
    // with; the backend answers any other one with meta_self_service_brand_forbidden.
    expect(SOURCE).toContain("meta_connection_manage");
    expect(SOURCE).toContain("tiktok_connection_manage");
  });

  it("drops the wizard chrome from the stylesheet too", () => {
    for (const orphan of [".setup-navigation", ".setup-progress", ".setup-brand-list"]) {
      expect(STYLES).not.toContain(orphan);
    }
    expect(STYLES).toContain(".setup-section");
    expect(STYLES).toContain(".setup-field-grid");
  });

  it("keeps the field grid readable on a narrow screen", () => {
    expect(STYLES).toContain("@media (max-width: 620px)");
  });
});

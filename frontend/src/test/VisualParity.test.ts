import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const frontendRoot = process.cwd();
const html = readFileSync(resolve(frontendRoot, "index.html"), "utf8");
const styles = readFileSync(resolve(frontendRoot, "src/styles.css"), "utf8");

describe("V1 visual theme parity", () => {
  it("loads the same Inter weights used by the Accumulate shell", () => {
    expect(html).toContain("family=Inter:wght@300;400;500;600;700");
    expect(styles).toContain(
      'font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;',
    );
  });

  it("keeps the canonical V1 Social Media palette", () => {
    expect(styles).toContain("--sm-bg: #f8fafc;");
    expect(styles).toContain("--sm-copy: #172033;");
    expect(styles).toContain("--sm-muted: #78849a;");
    expect(styles).toContain("--sm-primary: #5b4cf0;");
    expect(styles).toContain("--sm-primary-soft: #f1efff;");
  });

  it("does not introduce pure-black UI colors", () => {
    expect(styles).not.toMatch(/#000(?:000)?\b|rgb\(0[ ,]+0[ ,]+0(?:\s*\/[^)]*)?\)|\bblack\b/i);
  });
});

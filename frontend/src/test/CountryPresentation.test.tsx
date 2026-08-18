import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  CountryTableLabel,
  countryCode,
  countryDisplayName,
  countryFlagSrc,
  countryLookupKey,
} from "../features/dashboard/countryPresentation";

describe("country presentation", () => {
  it("expands provider country codes into full country names", () => {
    expect(countryDisplayName("TR")).toBe("Türkiye");
    expect(countryDisplayName("de")).toBe("Germany");
    expect(countryDisplayName("GB")).toBe("United Kingdom");
    expect(countryDisplayName("US")).toBe("United States");
    expect(countryCode("United States of America")).toBe("US");
    expect(countryCode("Others")).toBeNull();
    expect(countryLookupKey("TR")).toBe("turkey");
  });

  it("renders a local circular flag label for country tables", () => {
    const { container } = render(<CountryTableLabel value="TR" />);
    expect(screen.getByText("Türkiye")).toBeInTheDocument();
    // An image path, not the regional-indicator emoji: Windows renders no flag
    // for those code points and falls back to the two letters.
    expect(countryFlagSrc("TR")).toBe("/flags/tr.svg");
    expect(countryFlagSrc("Germany")).toBe("/flags/de.svg");
    expect(countryFlagSrc("Other")).toBeNull();
    const flag = container.querySelector(".country-flag");
    expect(flag).toHaveAttribute("src", "/flags/tr.svg");
    // Decorative: the country name beside it already carries the meaning.
    expect(flag).toHaveAttribute("alt", "");
  });
});

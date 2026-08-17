import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  CountryTableLabel,
  countryCode,
  countryDisplayName,
  countryFlag,
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
    expect(countryFlag("TR")).toBe("🇹🇷");
    expect(container.querySelector(".country-flag")).toHaveTextContent("🇹🇷");
  });
});

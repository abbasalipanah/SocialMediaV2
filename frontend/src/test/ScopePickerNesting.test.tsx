import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ScopePicker } from "../ui";

/**
 * A flat list of parents hid the child Brands behind a second dropdown, so
 * which Brands a family contained could only be discovered by selecting it.
 * The tree is drawn the way it reads in Accumulate: children under their parent.
 */
const OPTIONS = [
  { id: "218998", label: "Limak International Hotels & Resorts", detail: "10 Brands" },
  { id: "219392", label: "Limak Ambassadore Hotel Ankara", nested: true },
  { id: "219397", label: "Limak Arcadia Sport Resort Hotel", nested: true },
  { id: "1", label: "Pia Bella" },
  { id: "2", label: "Cornelia Diamond" },
  { id: "3", label: "Rixos Premium" },
  { id: "4", label: "Titanic Beach" },
];

describe("ScopePicker nesting", () => {
  it("marks child Brands as nested and leaves parents flat", () => {
    render(<ScopePicker onSelect={vi.fn()} options={OPTIONS} selectedId="218998" />);

    const child = screen.getByRole("option", { name: /Arcadia/ });
    const parent = screen.getByRole("option", { name: /Limak International/ });

    expect(child.className).toContain("scope-option-nested");
    expect(parent.className).not.toContain("scope-option-nested");
  });

  it("selects the child Brand itself, not its family", () => {
    const onSelect = vi.fn();
    render(<ScopePicker onSelect={onSelect} options={OPTIONS} selectedId="218998" />);

    fireEvent.click(screen.getByRole("option", { name: /Arcadia/ }));

    expect(onSelect).toHaveBeenCalledWith("219397");
  });

  it("drops the indent while searching, when the parent may be filtered out", () => {
    render(<ScopePicker onSelect={vi.fn()} options={OPTIONS} selectedId="218998" />);

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Arcadia" } });

    // Indenting under whichever row happened to survive the filter would be a
    // lie about the hierarchy.
    expect(screen.getByRole("option", { name: /Arcadia/ }).className).not.toContain(
      "scope-option-nested",
    );
  });
});

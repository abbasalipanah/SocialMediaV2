import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Popover } from "../ui";

describe("Popover accessibility", () => {
  it("closes on Escape and restores focus to its trigger", async () => {
    const user = userEvent.setup();
    render(
      <Popover label="Brand family" value="Parent Group">
        {() => <button type="button">First option</button>}
      </Popover>,
    );
    const trigger = screen.getByRole("button", { name: /Brand family Parent Group/ });
    await user.click(trigger);
    expect(screen.getByRole("dialog", { name: "Brand family" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Brand family" })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("traps focus and closes when interaction moves outside", async () => {
    const user = userEvent.setup();
    render(
      <div>
        <Popover label="Social account" value="All accounts">
          {() => (
            <>
              <button type="button">First option</button>
              <button type="button">Last option</button>
            </>
          )}
        </Popover>
        <button type="button">Outside</button>
      </div>,
    );
    await user.click(screen.getByRole("button", { name: /Social account All accounts/ }));
    const first = screen.getByRole("button", { name: "First option" });
    const last = screen.getByRole("button", { name: "Last option" });
    await vi.waitFor(() => expect(first).toHaveFocus());
    await user.tab({ shift: true });
    expect(last).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Outside" }));
    expect(screen.queryByRole("dialog", { name: "Social account" })).not.toBeInTheDocument();
  });
});

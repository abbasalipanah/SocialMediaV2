import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OAuthConnectionModal } from "../features/integrations/OAuthConnectionModal";

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("OAuthConnectionModal", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("starts YouTube authorization and accepts only its scoped callback", async () => {
    const replace = vi.fn();
    const popup = {
      closed: false,
      close: vi.fn(),
      location: { replace },
    } as unknown as Window;
    vi.spyOn(window, "open").mockReturnValue(popup);
    const request = vi.fn(async () => json({
      authorization_url: "https://accounts.example.test/youtube",
      expires_at: "2026-09-01T10:10:00Z",
    }));
    vi.stubGlobal("fetch", request);
    const onAuthorized = vi.fn();

    render(
      <OAuthConnectionModal
        brandId="42"
        brandName="Channel Brand"
        onAuthorized={onAuthorized}
        onClose={vi.fn()}
        provider="youtube"
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Continue with YouTube" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith(
      "/api/integrations/youtube/oauth/start?brand_id=42",
      expect.objectContaining({ method: "POST" }),
    ));
    expect(replace).toHaveBeenCalledWith("https://accounts.example.test/youtube");

    fireEvent(window, new MessageEvent("message", {
      data: {
        type: "social-media:youtube-oauth",
        status: "success",
        brandId: "42",
        connectionId: 9,
        errorCode: "",
      },
      origin: window.location.origin,
      source: popup,
    }));

    expect(await screen.findByText(/YouTube authorization completed/)).toBeInTheDocument();
    expect(onAuthorized).toHaveBeenCalledOnce();
  });

  it("starts X authorization through the dedicated OAuth endpoint", async () => {
    const replace = vi.fn();
    const popup = {
      closed: false,
      close: vi.fn(),
      location: { replace },
    } as unknown as Window;
    vi.spyOn(window, "open").mockReturnValue(popup);
    const request = vi.fn(async () => json({
      authorization_url: "https://x.com/i/oauth2/authorize?state=signed",
      expires_at: "2026-09-01T10:10:00Z",
    }));
    vi.stubGlobal("fetch", request);

    render(
      <OAuthConnectionModal
        brandId="42"
        brandName="X Brand"
        onAuthorized={vi.fn()}
        onClose={vi.fn()}
        provider="x"
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Continue with X" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith(
      "/api/integrations/x/oauth/start?brand_id=42",
      expect.objectContaining({ method: "POST" }),
    ));
    expect(replace).toHaveBeenCalledWith(
      "https://x.com/i/oauth2/authorize?state=signed",
    );
  });

  it("starts LinkedIn Company Page authorization through its OAuth endpoint", async () => {
    const replace = vi.fn();
    const popup = {
      closed: false,
      close: vi.fn(),
      location: { replace },
    } as unknown as Window;
    vi.spyOn(window, "open").mockReturnValue(popup);
    const request = vi.fn(async () => json({
      authorization_url: "https://www.linkedin.com/oauth/v2/authorization?state=signed",
      expires_at: "2026-09-01T10:10:00Z",
    }));
    vi.stubGlobal("fetch", request);

    render(
      <OAuthConnectionModal
        brandId="42"
        brandName="LinkedIn Brand"
        onAuthorized={vi.fn()}
        onClose={vi.fn()}
        provider="linkedin"
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Continue with LinkedIn" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith(
      "/api/integrations/linkedin/oauth/start?brand_id=42",
      expect.objectContaining({ method: "POST" }),
    ));
    expect(replace).toHaveBeenCalledWith(
      "https://www.linkedin.com/oauth/v2/authorization?state=signed",
    );
  });
});

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Check,
  Facebook,
  Instagram,
  Link2,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import {
  apiMutation,
  apiQuery,
  apiUrl,
  metaLinkResponseSchema,
  metaSelfServiceReadinessSchema,
  metaSelfServiceStartSchema,
  queryString,
  type MetaDiscovery,
  type Platform,
} from "../../api";

type MetaOAuthMessage = {
  type: "social-media:meta-oauth";
  status: "success" | "error";
  brandId: string;
  connectionId: number | null;
  facebookCount: number;
  instagramCount: number;
  connectionState: string;
  errorCode: string;
};

const READINESS_COPY: Record<string, string> = {
  provider_activation_not_configured: "Meta provider activation is not configured in this runtime yet.",
  provider_activation_unavailable: "Meta provider activation is temporarily unavailable.",
  writes_disabled: "Connection writes are disabled in this runtime.",
};

function discoveryKey(item: Pick<MetaDiscovery, "external_id" | "platform">): string {
  return `${item.platform}:${item.external_id}`;
}

export function MetaConnectionModal({
  brandId,
  brandName,
  focusPlatform,
  onClose,
  onConnected,
}: {
  brandId: string;
  brandName: string;
  focusPlatform: Extract<Platform, "facebook" | "instagram">;
  onClose: () => void;
  onConnected: () => void;
}) {
  const popupRef = useRef<Window | null>(null);
  const onConnectedRef = useRef(onConnected);
  const queryClient = useQueryClient();
  const [isConnecting, setIsConnecting] = useState(false);
  const [isLinking, setIsLinking] = useState(false);
  const [activeConnectionId, setActiveConnectionId] = useState<number | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [selectionInitialized, setSelectionInitialized] = useState(false);
  const [status, setStatus] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const readiness = useQuery({
    queryKey: ["integrations", "meta", "self-service", brandId],
    queryFn: ({ signal }) => apiQuery(
      `/api/integrations/meta/self-service/readiness${queryString({ brand_id: brandId })}`,
      metaSelfServiceReadinessSchema,
      signal,
    ),
    retry: false,
  });
  onConnectedRef.current = onConnected;

  const linkedAccountKeys = useMemo(
    () => new Set((readiness.data?.linked_accounts ?? []).map(discoveryKey)),
    [readiness.data?.linked_accounts],
  );
  const availableDiscoveries = useMemo(() => {
    const rows = readiness.data?.discoveries ?? [];
    const connectionId = activeConnectionId ?? rows.reduce<number | null>(
      (latest, item) => latest === null || item.connection_id > latest ? item.connection_id : latest,
      null,
    );
    return connectionId === null ? [] : rows.filter((item) => item.connection_id === connectionId);
  }, [activeConnectionId, readiness.data?.discoveries]);

  useEffect(() => {
    if (selectionInitialized || availableDiscoveries.length === 0) return;
    const firstDiscovery = availableDiscoveries[0];
    if (!firstDiscovery) return;
    setActiveConnectionId(firstDiscovery.connection_id);
    setSelected(new Set(
      availableDiscoveries
        .filter((item) => linkedAccountKeys.has(discoveryKey(item)))
        .map(discoveryKey),
    ));
    setSelectionInitialized(true);
  }, [availableDiscoveries, linkedAccountKeys, selectionInitialized]);

  useEffect(() => {
    const expectedOrigin = new URL(apiUrl("/"), window.location.origin).origin;
    const receiveOAuthResult = (event: MessageEvent<MetaOAuthMessage>) => {
      if (event.origin !== expectedOrigin) return;
      if (popupRef.current && event.source && event.source !== popupRef.current) return;
      const payload = event.data;
      if (!payload || payload.type !== "social-media:meta-oauth" || payload.brandId !== brandId) return;
      popupRef.current = null;
      setIsConnecting(false);
      if (payload.status === "error" || payload.connectionId === null) {
        setStatus({
          tone: "error",
          message: payload.errorCode === "meta_authorization_declined"
            ? "Meta authorization was cancelled. No account was linked."
            : "Meta authorization could not be completed. Please try again.",
        });
        return;
      }
      setActiveConnectionId(payload.connectionId);
      setSelected(new Set());
      setSelectionInitialized(false);
      setStatus({
        tone: "success",
        message: `${payload.facebookCount} Facebook Page and ${payload.instagramCount} Instagram account discovered. Choose the accounts to link.`,
      });
      void queryClient.invalidateQueries({
        queryKey: ["integrations", "meta", "self-service", brandId],
      });
    };
    window.addEventListener("message", receiveOAuthResult);
    // Only the listener. This used to close the authorization window too, so
    // any re-render that re-ran the effect -- a refetch on window focus, a
    // changed Brand -- killed the popup the moment it opened, which read as
    // "it closes before the page appears". The window belongs to the user for
    // as long as they are authorizing; the callback page closes it itself.
    return () => {
      window.removeEventListener("message", receiveOAuthResult);
    };
  }, [brandId, queryClient]);

  // Dismissing the dialog is a deliberate abandon, so the authorization window
  // goes with it. A re-render is not, which is why the effect no longer does.
  const dismiss = () => {
    if (popupRef.current && !popupRef.current.closed) popupRef.current.close();
    popupRef.current = null;
    onClose();
  };

  const connect = async () => {
    setStatus(null);
    const popup = window.open(
      "about:blank",
      "social-media-meta-oauth",
      "popup=yes,width=620,height=760,resizable=yes,scrollbars=yes",
    );
    if (!popup) {
      setStatus({ tone: "error", message: "The Meta login window was blocked. Allow popups and try again." });
      return;
    }
    popupRef.current = popup;
    setIsConnecting(true);
    try {
      const started = await apiMutation(
        `/api/integrations/meta/oauth/start${queryString({ brand_id: brandId })}`,
        metaSelfServiceStartSchema,
        { method: "POST" },
      );
      popup.location.replace(started.authorization_url);
    } catch (error) {
      popup.close();
      popupRef.current = null;
      setIsConnecting(false);
      setStatus({
        tone: "error",
        message: error instanceof Error ? error.message.replaceAll("_", " ") : "Meta connection could not be started.",
      });
    }
  };

  const linkSelected = async () => {
    if (activeConnectionId === null) return;
    const accounts = availableDiscoveries
      .filter((item) => selected.has(discoveryKey(item)))
      .map((item) => ({ platform: item.platform, external_id: item.external_id }));
    setIsLinking(true);
    setStatus(null);
    try {
      const linked = await apiMutation(
        `/api/integrations/meta/accounts/link${queryString({ brand_id: brandId })}`,
        metaLinkResponseSchema,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ connection_id: activeConnectionId, accounts }),
        },
      );
      setStatus({
        tone: "success",
        message: linked.linked_count === 0
          ? `All Meta accounts were unlinked from ${brandName}.`
          : `${linked.linked_count} Meta account${linked.linked_count === 1 ? "" : "s"} saved for ${brandName}.`,
      });
      await queryClient.invalidateQueries({
        queryKey: ["integrations", "meta", "self-service", brandId],
      });
      onConnectedRef.current();
    } catch (error) {
      setStatus({
        tone: "error",
        message: error instanceof Error ? error.message.replaceAll("_", " ") : "The selected accounts could not be linked.",
      });
    } finally {
      setIsLinking(false);
    }
  };

  const toggle = (item: MetaDiscovery) => {
    const key = discoveryKey(item);
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const toggleCurrentLink = (item: Pick<MetaDiscovery, "external_id" | "platform">) => {
    const key = discoveryKey(item);
    setSelected((current) => {
      const next = selectionInitialized
        ? new Set(current)
        : new Set(
          availableDiscoveries
            .filter((candidate) => linkedAccountKeys.has(discoveryKey(candidate)))
            .map(discoveryKey),
        );
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
    setSelectionInitialized(true);
  };

  const unavailableReason = readiness.data && !readiness.data.oauth_start_available
    ? READINESS_COPY[readiness.data.reason] ?? "Meta self-service is unavailable in this runtime."
    : null;
  const focusLabel = focusPlatform === "facebook" ? "Facebook Pages" : "Instagram Business accounts";

  // Through a portal, like the dialog this can be opened from. That dialog
  // portals to the document body, so a modal left inside the page tree sits in
  // whatever stacking context an ancestor happens to create and cannot rise
  // above it, whatever z-index it carries -- it rendered behind the drawer,
  // dimmed by its backdrop and impossible to click.
  return createPortal(
    <div className="tiktok-connect-layer">
      <button aria-label="Close Meta connection modal" className="tiktok-connect-backdrop" onClick={dismiss} type="button" />
      <section aria-labelledby="meta-connect-title" aria-modal="true" className="tiktok-connect-modal meta-connect-modal" role="dialog">
        <header>
          <div className="meta-connect-icons" aria-hidden="true"><Facebook size={20} /><Instagram size={20} /></div>
          <div><h2 id="meta-connect-title">Manage Meta accounts</h2><p>Review or change the Facebook and Instagram accounts linked to {brandName}.</p></div>
          <button aria-label="Close Meta connection modal" onClick={dismiss} type="button"><X size={18} /></button>
        </header>

        {status && <div className={`tiktok-connect-status ${status.tone}`} role="status">{status.tone === "success" ? <Check size={17} /> : <AlertTriangle size={17} />}<span>{status.message}</span></div>}

        <div className="tiktok-connect-body">
          <article>
            <span className="tiktok-connect-step">1</span>
            <div><h3>Authorize with Facebook</h3><p>Meta returns the Pages you manage and their linked Instagram Business accounts. Provider tokens remain encrypted on the backend.</p></div>
          </article>
          <article>
            <span className="tiktok-connect-step">2</span>
            <div><h3>Select accounts for this Brand</h3><p>Choose {focusLabel} and any other Meta accounts this Brand should use. Saving replaces the current selection for {brandName}.</p></div>
          </article>

          {readiness.isPending ? <div className="tiktok-connect-readiness"><RefreshCw className="spin" size={16} />Checking Meta connection readiness…</div> : readiness.isError || !readiness.data ? <div className="tiktok-connect-readiness error"><AlertTriangle size={16} />Self-service access could not be verified.</div> : <div className={`tiktok-connect-readiness ${readiness.data.oauth_start_available ? "ready" : "blocked"}`}><ShieldCheck size={16} /><span><strong>{readiness.data.oauth_start_available ? "Ready to authorize" : "Authorization not active"}</strong>{unavailableReason && <small>{unavailableReason}</small>}<small>{readiness.data.facebook_linked_count} Facebook · {readiness.data.instagram_linked_count} Instagram currently linked.</small></span></div>}

          {readiness.data && readiness.data.linked_accounts.length > 0 && (
            <section className="meta-current-links" aria-label={`Accounts linked to ${brandName}`}>
              <h3>Currently linked to {brandName}</h3>
              <div>
                {readiness.data.linked_accounts.map((item) => (
                  <span className={selectionInitialized && !selected.has(discoveryKey(item)) ? "pending-unlink" : ""} key={discoveryKey(item)}>
                    <span className={`integration-platform-icon platform-${item.platform}`}>{item.platform === "facebook" ? <Facebook size={16} /> : <Instagram size={16} />}</span>
                    <span><strong>{item.display_name}</strong><small>{item.platform === "facebook" ? "Facebook Page" : "Instagram Business"} · {item.external_id}</small></span>
                    <button onClick={() => toggleCurrentLink(item)} type="button">
                      {selectionInitialized && !selected.has(discoveryKey(item)) ? "Keep linked" : "Unlink"}
                    </button>
                  </span>
                ))}
              </div>
            </section>
          )}

          {availableDiscoveries.length > 0 && (
            <fieldset className="meta-discovery-list">
              <legend>Accounts available in the Meta authorization</legend>
              {availableDiscoveries.map((item) => (
                <label key={discoveryKey(item)}>
                  <input checked={selected.has(discoveryKey(item))} onChange={() => toggle(item)} type="checkbox" />
                  <span className={`integration-platform-icon platform-${item.platform}`}>{item.platform === "facebook" ? <Facebook size={17} /> : <Instagram size={17} />}</span>
                  <span><strong>{item.display_name}</strong><small>{item.platform === "facebook" ? "Facebook Page" : "Instagram Business"} · {item.external_id}</small></span>
                  <em className={linkedAccountKeys.has(discoveryKey(item)) ? "linked" : "available"}>{linkedAccountKeys.has(discoveryKey(item)) ? "Currently linked" : "Available"}</em>
                </label>
              ))}
            </fieldset>
          )}

          {readiness.data && (
            <p className="meta-refresh-note">Need another account? Add or refresh from Meta to load every Facebook Page and linked Instagram Business account managed by the authorizing Meta user.</p>
          )}
        </div>

        <footer>
          <p>Opening this dialog does not contact Meta. Authorization starts only after you continue to Meta.</p>
          <button className="secondary-button" onClick={dismiss} type="button">Cancel</button>
          {availableDiscoveries.length > 0 && <button className={`secondary-button ${selected.size === 0 ? "meta-unlink-all-button" : ""}`} disabled={isLinking || !readiness.data?.oauth_start_available} onClick={() => void linkSelected()} type="button">{isLinking ? <RefreshCw className="spin" size={15} /> : <Check size={15} />}{isLinking ? "Saving…" : selected.size === 0 ? "Save and unlink all" : `Save changes (${selected.size} linked)`}</button>}
          <button className="primary-button compact-button" disabled={!readiness.data?.oauth_start_available || isConnecting} onClick={() => void connect()} type="button">{isConnecting ? <RefreshCw className="spin" size={15} /> : <Link2 size={15} />}{isConnecting ? "Connecting…" : readiness.data?.linked_accounts.length ? "Add / refresh accounts" : "Connect Meta"}</button>
        </footer>
      </section>
    </div>,
    document.body,
  );
}

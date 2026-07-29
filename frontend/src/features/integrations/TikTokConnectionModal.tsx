import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Link2, RefreshCw, ShieldCheck, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  apiMutation,
  apiQuery,
  apiUrl,
  queryString,
  tiktokSelfServiceReadinessSchema,
  tiktokSelfServiceStartSchema,
} from "../../api";

type TikTokOAuthMessage = {
  type: "social-media:tiktok-oauth";
  status: "success" | "error";
  brandId: string;
  connectionId: number | null;
  linkId: number | null;
  connectionState: string;
  errorCode: string;
};

const READINESS_COPY: Record<string, string> = {
  provider_activation_not_configured: "TikTok provider activation is not configured in this runtime yet.",
  provider_activation_unavailable: "TikTok provider activation is temporarily unavailable.",
  writes_disabled: "Connection writes are disabled in this runtime.",
};

export function TikTokConnectionModal({
  brandId,
  brandName,
  onClose,
  onConnected,
}: {
  brandId: string;
  brandName: string;
  onClose: () => void;
  onConnected: () => void;
}) {
  const popupRef = useRef<Window | null>(null);
  const onConnectedRef = useRef(onConnected);
  const queryClient = useQueryClient();
  const [isConnecting, setIsConnecting] = useState(false);
  const [status, setStatus] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const readiness = useQuery({
    queryKey: ["integrations", "tiktok", "self-service", brandId],
    queryFn: ({ signal }) => apiQuery(
      `/api/integrations/tiktok/self-service/readiness${queryString({ brand_id: brandId })}`,
      tiktokSelfServiceReadinessSchema,
      signal,
    ),
    retry: false,
  });
  onConnectedRef.current = onConnected;

  useEffect(() => {
    const expectedOrigin = new URL(apiUrl("/"), window.location.origin).origin;
    const receiveOAuthResult = (event: MessageEvent<TikTokOAuthMessage>) => {
      if (event.origin !== expectedOrigin) return;
      if (popupRef.current && event.source && event.source !== popupRef.current) return;
      const payload = event.data;
      if (!payload || payload.type !== "social-media:tiktok-oauth" || payload.brandId !== brandId) return;
      popupRef.current = null;
      setIsConnecting(false);
      if (payload.status === "error") {
        setStatus({
          tone: "error",
          message: payload.errorCode === "tiktok_self_service_callback_rejected"
            ? "TikTok authorization expired or was already used. Please try again."
            : "TikTok authorization could not be completed. Please try again.",
        });
        return;
      }
      setStatus({
        tone: "success",
        message: "TikTok authorization was received. The account is now pending verification.",
      });
      void queryClient.invalidateQueries({ queryKey: ["integrations", "tiktok", "self-service", brandId] });
      onConnectedRef.current();
    };
    window.addEventListener("message", receiveOAuthResult);
    return () => {
      window.removeEventListener("message", receiveOAuthResult);
      if (popupRef.current && !popupRef.current.closed) popupRef.current.close();
      popupRef.current = null;
    };
  }, [brandId, queryClient]);

  const connect = async () => {
    setStatus(null);
    const popup = window.open(
      "about:blank",
      "social-media-tiktok-oauth",
      "popup=yes,width=620,height=760,resizable=yes,scrollbars=yes",
    );
    if (!popup) {
      setStatus({ tone: "error", message: "The TikTok login window was blocked. Allow popups and try again." });
      return;
    }
    popupRef.current = popup;
    setIsConnecting(true);
    try {
      const started = await apiMutation(
        `/api/integrations/tiktok/oauth/start${queryString({ brand_id: brandId })}`,
        tiktokSelfServiceStartSchema,
        { method: "POST" },
      );
      popup.location.replace(started.authorization_url);
    } catch (error) {
      popup.close();
      popupRef.current = null;
      setIsConnecting(false);
      setStatus({
        tone: "error",
        message: error instanceof Error ? error.message.replaceAll("_", " ") : "TikTok connection could not be started.",
      });
    }
  };

  const unavailableReason = readiness.data && !readiness.data.oauth_start_available
    ? READINESS_COPY[readiness.data.reason] ?? "TikTok self-service is unavailable in this runtime."
    : null;

  return (
    <div className="tiktok-connect-layer">
      <button aria-label="Close TikTok connection modal" className="tiktok-connect-backdrop" onClick={onClose} type="button" />
      <section aria-labelledby="tiktok-connect-title" aria-modal="true" className="tiktok-connect-modal" role="dialog">
        <header>
          <div className="integration-platform-icon platform-tiktok"><span aria-hidden="true" className="integration-tiktok-mark">♪</span></div>
          <div><h2 id="tiktok-connect-title">Connect TikTok</h2><p>Authorize one TikTok Business account only for {brandName}.</p></div>
          <button aria-label="Close TikTok connection modal" onClick={onClose} type="button"><X size={18} /></button>
        </header>

        {status && <div className={`tiktok-connect-status ${status.tone}`} role="status">{status.tone === "success" ? <Check size={17} /> : <AlertTriangle size={17} />}<span>{status.message}</span></div>}

        <div className="tiktok-connect-body">
          <article>
            <span className="tiktok-connect-step">1</span>
            <div><h3>Authorize TikTok Business</h3><p>Sign in with the TikTok account you want to add to this Brand. The OAuth token stays on the backend and is never returned to the browser.</p></div>
          </article>
          <article>
            <span className="tiktok-connect-step">2</span>
            <div><h3>Verify the Brand link</h3><p>TikTok returns one Business account for this authorization. It is stored as pending verification before reporting is enabled.</p></div>
          </article>

          {readiness.isPending ? <div className="tiktok-connect-readiness"><RefreshCw className="spin" size={16} />Checking connection readiness…</div> : readiness.isError || !readiness.data ? <div className="tiktok-connect-readiness error"><AlertTriangle size={16} />Self-service access could not be verified.</div> : <div className={`tiktok-connect-readiness ${readiness.data.oauth_start_available ? "ready" : "blocked"}`}><ShieldCheck size={16} /><span><strong>{readiness.data.oauth_start_available ? "Ready to authorize" : "Authorization not active"}</strong>{unavailableReason && <small>{unavailableReason}</small>}<small>{readiness.data.linked_account_count} TikTok account{readiness.data.linked_account_count === 1 ? "" : "s"} currently linked.</small></span></div>}
        </div>

        <footer>
          <p>Opening this dialog does not contact TikTok. Authorization starts only after the button below.</p>
          <button className="secondary-button" onClick={onClose} type="button">Cancel</button>
          <button className="primary-button compact-button" disabled={!readiness.data?.oauth_start_available || isConnecting} onClick={() => void connect()} type="button">{isConnecting ? <RefreshCw className="spin" size={15} /> : <Link2 size={15} />}{isConnecting ? "Connecting…" : "Connect TikTok"}</button>
        </footer>
      </section>
    </div>
  );
}

import { AlertTriangle, Check, Link2, RefreshCw, ShieldCheck, X as CloseIcon, Youtube } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import {
  apiMutation,
  apiUrl,
  metaSelfServiceStartSchema,
  oauthChannelStartSchema,
  queryString,
  tiktokSelfServiceStartSchema,
} from "../../api";

export type OAuthProvider = "meta" | "tiktok" | "x" | "youtube";

type OAuthMessage = {
  type: `social-media:${OAuthProvider}-oauth`;
  status: "success" | "error";
  brandId: string;
  connectionId: number | null;
  errorCode: string;
};

const PROVIDER_COPY: Record<OAuthProvider, {
  label: string;
  popupName: string;
  messageType: OAuthMessage["type"];
  startPath: string;
  intro: string;
  completion: string;
}> = {
  meta: {
    label: "Meta",
    popupName: "social-media-meta-oauth",
    messageType: "social-media:meta-oauth",
    startPath: "/api/integrations/meta/oauth/start",
    intro: "Sign in to Meta and approve the requested Facebook and Instagram reporting permissions.",
    completion: "Meta authorization completed. Account discovery and Brand mapping remain in Settings and are not shown here.",
  },
  tiktok: {
    label: "TikTok",
    popupName: "social-media-tiktok-oauth",
    messageType: "social-media:tiktok-oauth",
    startPath: "/api/integrations/tiktok/oauth/start",
    intro: "TikTok will always show its authorization screen. Confirm that the displayed TikTok Business identity belongs to this Brand before approving.",
    completion: "TikTok authorization completed. Verification and account-level maintenance remain separate from this page.",
  },
  x: {
    label: "X",
    popupName: "social-media-x-oauth",
    messageType: "social-media:x-oauth",
    startPath: "/api/integrations/x/oauth/start",
    intro: "Sign in to X and approve read-only profile and post access.",
    completion: "X authorization completed. Select the account for this Brand in Settings.",
  },
  youtube: {
    label: "YouTube",
    popupName: "social-media-youtube-oauth",
    messageType: "social-media:youtube-oauth",
    startPath: "/api/integrations/youtube/oauth/start",
    intro: "Sign in to YouTube and approve read-only channel and analytics access.",
    completion: "YouTube authorization completed. Select the channel for this Brand in Settings.",
  },
};

export function OAuthConnectionModal({ provider, brandId, brandName, onClose, onAuthorized }: {
  provider: OAuthProvider;
  brandId: string;
  brandName: string;
  onClose: () => void;
  onAuthorized: () => void;
}) {
  const popupRef = useRef<Window | null>(null);
  const onAuthorizedRef = useRef(onAuthorized);
  const [isConnecting, setIsConnecting] = useState(false);
  const [status, setStatus] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const copy = PROVIDER_COPY[provider];
  onAuthorizedRef.current = onAuthorized;

  useEffect(() => {
    const expectedOrigin = new URL(apiUrl("/"), window.location.origin).origin;
    const receiveOAuthResult = (event: MessageEvent<OAuthMessage>) => {
      if (event.origin !== expectedOrigin) return;
      if (popupRef.current && event.source && event.source !== popupRef.current) return;
      const payload = event.data;
      if (!payload || payload.type !== copy.messageType || payload.brandId !== brandId) return;
      popupRef.current = null;
      setIsConnecting(false);
      if (payload.status === "error" || payload.connectionId === null) {
        setStatus({
          tone: "error",
          message: payload.errorCode
            ? payload.errorCode.replaceAll("_", " ")
            : `${copy.label} authorization could not be completed.`,
        });
        return;
      }
      setStatus({ tone: "success", message: copy.completion });
      onAuthorizedRef.current();
    };
    window.addEventListener("message", receiveOAuthResult);
    return () => window.removeEventListener("message", receiveOAuthResult);
  }, [brandId, copy]);

  const dismiss = () => {
    if (popupRef.current && !popupRef.current.closed) popupRef.current.close();
    popupRef.current = null;
    onClose();
  };

  const authorize = async () => {
    setStatus(null);
    const popup = window.open(
      "about:blank",
      copy.popupName,
      "popup=yes,width=620,height=760,resizable=yes,scrollbars=yes",
    );
    if (!popup) {
      setStatus({ tone: "error", message: `The ${copy.label} login window was blocked. Allow popups and try again.` });
      return;
    }
    popupRef.current = popup;
    setIsConnecting(true);
    try {
      const path = `${copy.startPath}${queryString({ brand_id: brandId })}`;
      const startSchema = provider === "meta"
        ? metaSelfServiceStartSchema
        : provider === "tiktok"
          ? tiktokSelfServiceStartSchema
          : oauthChannelStartSchema;
      const started = await apiMutation(path, startSchema, { method: "POST" });
      popup.location.replace(started.authorization_url);
    } catch (error) {
      popup.close();
      popupRef.current = null;
      setIsConnecting(false);
      setStatus({
        tone: "error",
        message: error instanceof Error
          ? error.message.replaceAll("_", " ")
          : `${copy.label} authorization could not be started.`,
      });
    }
  };

  return createPortal(
    <div className="tiktok-connect-layer">
      <button aria-label={`Close ${copy.label} authorization`} className="tiktok-connect-backdrop" onClick={dismiss} type="button" />
      <section aria-labelledby="oauth-connect-title" aria-modal="true" className="tiktok-connect-modal" role="dialog">
        <header>
          <div className={`integration-platform-icon platform-${provider}`}>
            {provider === "meta"
              ? <span aria-hidden="true" className="oauth-meta-mark">∞</span>
              : provider === "tiktok"
                ? <span aria-hidden="true" className="integration-tiktok-mark">♪</span>
                : provider === "youtube"
                  ? <Youtube aria-hidden="true" size={22} />
                  : <span aria-hidden="true" className="social-x-mark">𝕏</span>}
          </div>
          <div><h2 id="oauth-connect-title">Authorize {copy.label}</h2><p>{brandName} · OAuth authorization only</p></div>
          <button aria-label={`Close ${copy.label} authorization`} onClick={dismiss} type="button"><CloseIcon size={18} /></button>
        </header>

        {status && <div className={`tiktok-connect-status ${status.tone}`} role="status">{status.tone === "success" ? <Check size={17} /> : <AlertTriangle size={17} />}<span>{status.message}</span></div>}

        <div className="tiktok-connect-body">
          <article>
            <span className="tiktok-connect-step">1</span>
            <div><h3>Authorize with {copy.label}</h3><p>{copy.intro} Tokens are stored only by the backend and are never returned to the browser.</p></div>
          </article>
          <article>
            <span className="tiktok-connect-step">2</span>
            <div><h3>Keep account management separate</h3><p>This viewer-facing page does not list, select, link or unlink provider accounts. Agency admins and super admins manage account mappings in Settings.</p></div>
          </article>
          <div className="tiktok-connect-readiness ready"><ShieldCheck size={16} /><span><strong>OAuth-only connection</strong><small>Authorization starts only after the button below. No account details are loaded into this page.</small></span></div>
        </div>

        <footer>
          <p>Reauthorizing replaces provider access only; it does not expose account lists here.</p>
          <button className="secondary-button" onClick={dismiss} type="button">Cancel</button>
          <button className="primary-button compact-button" disabled={isConnecting} onClick={() => void authorize()} type="button">{isConnecting ? <RefreshCw className="spin" size={15} /> : <Link2 size={15} />}{isConnecting ? "Opening…" : `Continue with ${copy.label}`}</button>
        </footer>
      </section>
    </div>,
    document.body,
  );
}

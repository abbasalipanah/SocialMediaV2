import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Link2, Linkedin, RefreshCw, ShieldCheck, X as CloseIcon, Youtube } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import {
  apiMutation,
  apiQuery,
  apiUrl,
  oauthChannelLinkResponseSchema,
  oauthChannelReadinessSchema,
  oauthChannelStartSchema,
  oauthChannelUnlinkResponseSchema,
  queryString,
} from "../../api";

export type ManagedOAuthChannel = "linkedin" | "x" | "youtube";

type OAuthChannelMessage = {
  type: `social-media:${ManagedOAuthChannel}-oauth`;
  status: "success" | "error";
  brandId: string;
  platform: ManagedOAuthChannel;
  connectionId: number | null;
  discoveredCount: number;
  errorCode: string;
};

const PROVIDER_COPY: Record<ManagedOAuthChannel, {
  label: string;
  entity: string;
  entities: string;
  access: string;
}> = {
  x: {
    label: "X",
    entity: "account",
    entities: "accounts",
    access: "Read-only profile and post access",
  },
  linkedin: {
    label: "LinkedIn",
    entity: "Company Page",
    entities: "Company Pages",
    access: "Read-only Company Page analytics access",
  },
  youtube: {
    label: "YouTube",
    entity: "channel",
    entities: "channels",
    access: "Read-only channel and analytics access",
  },
};

function ProviderIcon({ provider, size }: { provider: ManagedOAuthChannel; size: number }) {
  if (provider === "youtube") return <Youtube aria-hidden="true" size={size} />;
  if (provider === "linkedin") return <Linkedin aria-hidden="true" size={size} />;
  return <span aria-hidden="true" className="social-x-mark">𝕏</span>;
}

export function OAuthChannelConnectionModal({
  brandId,
  brandName,
  onClose,
  onChanged,
  provider,
}: {
  brandId: string;
  brandName: string;
  onClose: () => void;
  onChanged: () => void;
  provider: ManagedOAuthChannel;
}) {
  const queryClient = useQueryClient();
  const copy = PROVIDER_COPY[provider];
  const popupRef = useRef<Window | null>(null);
  const selectionKeyRef = useRef("");
  const onChangedRef = useRef(onChanged);
  const [callbackConnectionId, setCallbackConnectionId] = useState<number | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [isAuthorizing, setIsAuthorizing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [unlinkingId, setUnlinkingId] = useState<string | null>(null);
  const [confirmUnlinkId, setConfirmUnlinkId] = useState<string | null>(null);
  const [status, setStatus] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const queryKey = ["integrations", provider, "self-service", brandId] as const;
  const readiness = useQuery({
    queryKey,
    queryFn: ({ signal }) => apiQuery(
      `/api/integrations/${provider}/self-service/readiness${queryString({ brand_id: brandId })}`,
      oauthChannelReadinessSchema,
      signal,
    ),
    retry: false,
  });
  onChangedRef.current = onChanged;

  const discoveries = useMemo(
    () => [...(readiness.data?.linked_accounts ?? []), ...(readiness.data?.available_accounts ?? [])],
    [readiness.data?.available_accounts, readiness.data?.linked_accounts],
  );
  const connectionId = callbackConnectionId ?? discoveries.reduce<number | null>(
    (latest, item) => item.connection_id !== null && (latest === null || item.connection_id > latest)
      ? item.connection_id
      : latest,
    null,
  );
  const selectableAccounts = useMemo(
    () => connectionId === null ? [] : discoveries.filter((item) => item.connection_id === connectionId),
    [connectionId, discoveries],
  );
  const linkedIds = useMemo(
    () => new Set((readiness.data?.linked_accounts ?? []).map((item) => item.external_id)),
    [readiness.data?.linked_accounts],
  );

  useEffect(() => {
    if (connectionId === null) return;
    const selectionKey = `${brandId}:${connectionId}:${selectableAccounts
      .map((item) => `${item.external_id}:${item.state}`)
      .sort()
      .join("|")}`;
    if (selectionKeyRef.current === selectionKey) return;
    selectionKeyRef.current = selectionKey;
    setSelected(new Set(
      selectableAccounts
        .filter((item) => linkedIds.has(item.external_id))
        .map((item) => item.external_id),
    ));
  }, [brandId, connectionId, linkedIds, selectableAccounts]);

  useEffect(() => {
    const expectedOrigin = new URL(apiUrl("/"), window.location.origin).origin;
    const receiveOAuthResult = (event: MessageEvent<OAuthChannelMessage>) => {
      if (event.origin !== expectedOrigin) return;
      if (!popupRef.current || event.source !== popupRef.current) return;
      const payload = event.data;
      if (
        !payload
        || payload.type !== `social-media:${provider}-oauth`
        || payload.platform !== provider
        || payload.brandId !== brandId
      ) return;
      popupRef.current = null;
      setIsAuthorizing(false);
      if (payload.status === "error" || payload.connectionId === null) {
        setStatus({
          tone: "error",
          message: payload.errorCode
            ? payload.errorCode.replaceAll("_", " ")
            : `${copy.label} authorization could not be completed.`,
        });
        return;
      }
      setCallbackConnectionId(payload.connectionId);
      selectionKeyRef.current = "";
      setStatus({
        tone: "success",
        message: `${payload.discoveredCount} ${copy.label} ${payload.discoveredCount === 1 ? copy.entity : copy.entities} found. Select what belongs to ${brandName}.`,
      });
      void queryClient.invalidateQueries({ queryKey });
    };
    window.addEventListener("message", receiveOAuthResult);
    return () => window.removeEventListener("message", receiveOAuthResult);
  }, [brandId, brandName, copy, provider, queryClient, queryKey]);

  useEffect(() => {
    if (!isAuthorizing) return;
    const timer = window.setInterval(() => {
      if (!popupRef.current?.closed) return;
      popupRef.current = null;
      setIsAuthorizing(false);
      setStatus((current) => current ?? {
        tone: "error",
        message: `The ${copy.label} login window closed before authorization completed.`,
      });
    }, 400);
    return () => window.clearInterval(timer);
  }, [copy.label, isAuthorizing]);

  const dismiss = () => {
    if (popupRef.current && !popupRef.current.closed) popupRef.current.close();
    popupRef.current = null;
    onClose();
  };

  const authorize = async () => {
    setStatus(null);
    const popup = window.open(
      "about:blank",
      `social-media-${provider}-oauth`,
      "popup=yes,width=620,height=760,resizable=yes,scrollbars=yes",
    );
    if (!popup) {
      setStatus({ tone: "error", message: `The ${copy.label} login window was blocked. Allow popups and try again.` });
      return;
    }
    popupRef.current = popup;
    setIsAuthorizing(true);
    try {
      const started = await apiMutation(
        `/api/integrations/${provider}/oauth/start${queryString({ brand_id: brandId })}`,
        oauthChannelStartSchema,
        { method: "POST" },
      );
      popup.location.replace(started.authorization_url);
    } catch (error) {
      popup.close();
      popupRef.current = null;
      setIsAuthorizing(false);
      setStatus({
        tone: "error",
        message: error instanceof Error ? error.message.replaceAll("_", " ") : `${copy.label} authorization could not be started.`,
      });
    }
  };

  const saveSelection = async () => {
    if (connectionId === null || selected.size === 0) return;
    setIsSaving(true);
    setStatus(null);
    try {
      const linked = await apiMutation(
        `/api/integrations/${provider}/accounts/link${queryString({ brand_id: brandId })}`,
        oauthChannelLinkResponseSchema,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ connection_id: connectionId, external_ids: [...selected] }),
        },
      );
      selectionKeyRef.current = "";
      setStatus({
        tone: "success",
        message: `${linked.linked_count} ${copy.label} ${linked.linked_count === 1 ? copy.entity : copy.entities} linked to ${brandName}.`,
      });
      await queryClient.invalidateQueries({ queryKey });
      onChangedRef.current();
    } catch (error) {
      setStatus({
        tone: "error",
        message: error instanceof Error ? error.message.replaceAll("_", " ") : "The selected channels could not be linked.",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const unlink = async (externalId: string) => {
    setUnlinkingId(externalId);
    setStatus(null);
    try {
      await apiMutation(
        `/api/integrations/${provider}/accounts/unlink${queryString({ brand_id: brandId, external_id: externalId })}`,
        oauthChannelUnlinkResponseSchema,
        { method: "DELETE" },
      );
      setConfirmUnlinkId(null);
      selectionKeyRef.current = "";
      setStatus({ tone: "success", message: `${copy.label} ${copy.entity} unlinked from ${brandName}.` });
      await queryClient.invalidateQueries({ queryKey });
      onChangedRef.current();
    } catch (error) {
      setStatus({
        tone: "error",
        message: error instanceof Error ? error.message.replaceAll("_", " ") : `The ${copy.label} ${copy.entity} could not be unlinked.`,
      });
    } finally {
      setUnlinkingId(null);
    }
  };

  const readinessCopy: Record<string, string> = {
    provider_activation_not_configured: `${copy.label} authorization is not configured in this runtime yet.`,
    provider_activation_unavailable: `${copy.label} authorization is temporarily unavailable.`,
    writes_disabled: "Connection changes are disabled in this runtime.",
  };
  const unavailableReason = readiness.data && !readiness.data.oauth_start_available
    ? readinessCopy[readiness.data.reason] ?? `${copy.label} authorization is unavailable in this runtime.`
    : null;
  const titleId = `${provider}-channel-title`;
  const managerLabel = `Close ${copy.label} ${copy.entity} manager`;

  return createPortal(
    <div className="tiktok-connect-layer">
      <button aria-label={managerLabel} className="tiktok-connect-backdrop" onClick={dismiss} type="button" />
      <section aria-labelledby={titleId} aria-modal="true" className="tiktok-connect-modal meta-connect-modal" role="dialog">
        <header>
          <div className={`integration-platform-icon platform-${provider}`}><ProviderIcon provider={provider} size={22} /></div>
          <div><h2 id={titleId}>Manage {copy.label} {copy.entities}</h2><p>{brandName} · {copy.access}</p></div>
          <button aria-label={managerLabel} onClick={dismiss} type="button"><CloseIcon size={18} /></button>
        </header>

        {status && <div className={`tiktok-connect-status ${status.tone}`} role="status">{status.tone === "success" ? <Check size={17} /> : <AlertTriangle size={17} />}<span>{status.message}</span></div>}

        <div className="tiktok-connect-body">
          {readiness.isPending ? (
            <div className="tiktok-connect-readiness"><RefreshCw className="spin" size={16} />Checking {copy.label} access…</div>
          ) : readiness.isError || !readiness.data ? (
            <div className="tiktok-connect-readiness error"><AlertTriangle size={16} />{copy.label} access could not be checked.</div>
          ) : !readiness.data.can_manage ? (
            <div className="tiktok-connect-readiness blocked"><AlertTriangle size={16} />Settings permission is required to manage {copy.label} {copy.entities}.</div>
          ) : (
            <>
              <div className={`tiktok-connect-readiness ${readiness.data.oauth_start_available ? "ready" : "blocked"}`}>
                <ShieldCheck size={16} />
                <span>
                  <strong>{readiness.data.oauth_start_available ? "Ready for read-only authorization" : "Authorization not active"}</strong>
                  {unavailableReason && <small>{unavailableReason}</small>}
                  <small>{readiness.data.linked_account_count} {readiness.data.linked_account_count === 1 ? copy.entity : copy.entities} currently linked.</small>
                </span>
              </div>

              {selectableAccounts.length > 0 && (
                <fieldset className="meta-discovery-list">
                  <legend>{copy.entities[0]?.toUpperCase()}{copy.entities.slice(1)} from the latest authorization</legend>
                  {selectableAccounts.map((item) => {
                    const checked = selected.has(item.external_id);
                    return (
                      <label key={item.external_id}>
                        <input
                          checked={checked}
                          onChange={() => setSelected((current) => {
                            const next = new Set(current);
                            if (next.has(item.external_id)) next.delete(item.external_id);
                            else next.add(item.external_id);
                            return next;
                          })}
                          type="checkbox"
                        />
                        <span className={`integration-platform-icon platform-${provider}`}><ProviderIcon provider={provider} size={17} /></span>
                        <span><strong>{item.display_name}</strong><small>{copy.label} {copy.entity} · {item.external_id}</small></span>
                        <em className={linkedIds.has(item.external_id) ? "linked" : checked ? "selected" : "available"}>{linkedIds.has(item.external_id) ? "Linked" : checked ? "Selected" : "Available"}</em>
                      </label>
                    );
                  })}
                </fieldset>
              )}

              {readiness.data.linked_accounts.length > 0 && (
                <section aria-label={`Linked ${copy.label} ${copy.entities}`} className="social-manager-tiktok-panel">
                  <div className="meta-platform-heading"><h3>Linked {copy.entities}</h3><p>Unlinking stops future collection for that {copy.entity}.</p></div>
                  {readiness.data.linked_accounts.map((item) => (
                    <article key={item.external_id}>
                      <span className={`integration-platform-icon platform-${provider}`}><ProviderIcon provider={provider} size={17} /></span>
                      <span><strong>{item.display_name}</strong><small>{copy.label} · {item.external_id}</small></span>
                      <div className="social-manager-tiktok-actions">
                        {confirmUnlinkId === item.external_id ? (
                          <>
                            <button disabled={unlinkingId !== null} onClick={() => setConfirmUnlinkId(null)} type="button">Cancel</button>
                            <button className="confirm" disabled={unlinkingId !== null} onClick={() => void unlink(item.external_id)} type="button">{unlinkingId === item.external_id ? <RefreshCw className="spin" size={13} /> : null}Confirm unlink</button>
                          </>
                        ) : <button disabled={unlinkingId !== null} onClick={() => setConfirmUnlinkId(item.external_id)} type="button">Unlink</button>}
                      </div>
                    </article>
                  ))}
                </section>
              )}

              {discoveries.length === 0 && (
                <p className="meta-account-empty">Authorize {copy.label} to discover {copy.entities} owned by the signed-in identity.</p>
              )}
            </>
          )}
        </div>

        <footer>
          <p>Only {copy.entities} explicitly selected here are linked to this Brand.</p>
          <button className="secondary-button" onClick={dismiss} type="button">Cancel</button>
          {selectableAccounts.length > 0 ? (
            <button className="primary-button compact-button" disabled={!readiness.data?.can_manage || selected.size === 0 || isSaving} onClick={() => void saveSelection()} type="button">{isSaving ? <RefreshCw className="spin" size={15} /> : <Check size={15} />}{isSaving ? "Saving…" : `Save selection (${selected.size})`}</button>
          ) : (
            <button className="primary-button compact-button" disabled={!readiness.data?.oauth_start_available || isAuthorizing} onClick={() => void authorize()} type="button">{isAuthorizing ? <RefreshCw className="spin" size={15} /> : <Link2 size={15} />}{isAuthorizing ? "Connecting…" : `Connect ${copy.label}`}</button>
          )}
        </footer>
      </section>
    </div>,
    document.body,
  );
}

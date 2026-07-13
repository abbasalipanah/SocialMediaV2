"""Signed internal provisioning endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from app.application.ports import AuthorityStore
from app.application.services.provisioning import (
    ProvisioningError,
    SignedRequest,
    apply_signed_event,
)
from app.core import AppSettings, Boundary, WritePolicy, mark_boundary


def create_internal_router(
    settings: AppSettings,
    policy: WritePolicy,
    store: AuthorityStore | None,
) -> APIRouter:
    router = APIRouter()

    @router.post("/internal/provisioning/events")
    @mark_boundary(Boundary.COMMAND)
    async def provisioning_event(
        request: Request,
        timestamp: str = Header(alias="X-Accumulate-Timestamp"),
        nonce: str = Header(alias="X-Accumulate-Nonce"),
        signature: str = Header(alias="X-Accumulate-Signature"),
    ) -> dict[str, str]:
        if store is None:
            raise HTTPException(503, "provisioning_store_unavailable")
        try:
            policy.assert_allows_mutation("provisioning_receive")
            status = apply_signed_event(
                secret=settings.provisioning_hmac_secret,
                method="POST",
                path="/internal/provisioning/events",
                body=await request.body(),
                signed=SignedRequest(timestamp=timestamp, nonce=nonce, signature=signature),
                store=store,
                session_store=store,
            )
        except PermissionError as exc:
            raise HTTPException(403, "writes_disabled") from exc
        except ProvisioningError as exc:
            reason = str(exc)
            if reason == "provisioning_not_configured":
                raise HTTPException(503, reason) from exc
            if reason == "nonce_replayed":
                raise HTTPException(409, reason) from exc
            if reason in {
                "invalid_nonce",
                "invalid_signature",
                "invalid_timestamp",
                "timestamp_out_of_window",
            }:
                raise HTTPException(401, reason) from exc
            raise HTTPException(422, reason) from exc
        return {"status": status}

    return router

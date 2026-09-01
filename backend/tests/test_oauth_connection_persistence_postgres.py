from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, create_engine, text

from app.application.ports import OAuthCredentialBinding, OAuthLinkSelection
from app.core import RuntimeMode, WritePolicy
from app.domain.platforms import PlatformId
from app.infrastructure.persistence.social_v2.collection_targets import (
    SocialCollectionTargetStore,
)
from app.infrastructure.persistence.social_v2.oauth_channels import (
    ProjectionOAuthConnectionStore,
)

DATABASE_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TEST_POSTGRES_URL is not configured"
)
NOW = datetime(2026, 8, 31, 12, tzinfo=UTC)


@pytest.fixture()
def engine() -> Iterator[Engine]:
    assert DATABASE_URL
    value = create_engine(DATABASE_URL)
    with value.begin() as connection:
        connection.execute(
            text(
                """TRUNCATE TABLE social_projection_state, linked_social_accounts,
                                  assets, platform_connections, brands, tenants
                   RESTART IDENTITY CASCADE"""
            )
        )
        connection.execute(text("INSERT INTO tenants (id, name) VALUES (1, 'Test')"))
        connection.execute(
            text("INSERT INTO brands (id, tenant_id, name) VALUES (17, 1, 'Brand')")
        )
    yield value
    value.dispose()


def test_oauth_connection_links_selection_and_disconnects_locally(
    engine: Engine,
) -> None:
    policy = WritePolicy(RuntimeMode.DEVELOPMENT, True)
    store = ProjectionOAuthConnectionStore(engine, policy, PlatformId.YOUTUBE)
    pending = store.create_pending(
        brand_id=17,
        platform=PlatformId.YOUTUBE,
        provider_subject_id="google-user-1",
        credentials=(
            OAuthCredentialBinding(
                platform=PlatformId.YOUTUBE,
                external_id="UC-channel",
                display_name="Example Channel",
                credential_reference="d" * 64,
            ),
            OAuthCredentialBinding(
                platform=PlatformId.YOUTUBE,
                external_id="UC-other",
                display_name="Other Channel",
                credential_reference="e" * 64,
            ),
        ),
        expires_at=NOW + timedelta(hours=1),
    )

    assert pending.state == "pending_verification"
    assert [
        item.status
        for item in store.list_discoveries(
            brand_id=17,
            platform=PlatformId.YOUTUBE,
        )
    ] == ["available", "available"]

    linked = store.link_accounts(
        brand_id=17,
        platform=PlatformId.YOUTUBE,
        connection_id=pending.connection_id,
        selections=(OAuthLinkSelection("UC-channel"), OAuthLinkSelection("UC-other")),
    )
    with engine.connect() as connection:
        linked_ids = list(
            connection.execute(
                text(
                    """SELECT external_id FROM linked_social_accounts
                       WHERE brand_id=17 AND platform='youtube'
                         AND status='connected'
                       ORDER BY external_id"""
                )
            ).scalars()
        )

    assert linked.state == "connected"
    assert linked_ids == ["UC-channel", "UC-other"]
    targets = SocialCollectionTargetStore(engine, policy).list_connected(
        platforms=(PlatformId.YOUTUBE,), brand_id=17
    )
    assert [target.external_id for target in targets] == ["UC-channel", "UC-other"]
    assert targets[0].credential_reference == "d" * 64
    assert [
        item.status
        for item in store.list_discoveries(
            brand_id=17,
            platform=PlatformId.YOUTUBE,
        )
    ] == ["linked", "linked"]

    partial_disconnect = store.disconnect(
        brand_id=17,
        platform=PlatformId.YOUTUBE,
        external_id="UC-other",
    )
    assert partial_disconnect is not None
    assert partial_disconnect.state == "connected"
    assert partial_disconnect.linked_count == 1

    replaced = store.link_accounts(
        brand_id=17,
        platform=PlatformId.YOUTUBE,
        connection_id=pending.connection_id,
        selections=(OAuthLinkSelection("UC-channel"),),
    )
    assert replaced.linked_count == 1
    with engine.connect() as connection:
        active_ids = list(
            connection.execute(
                text(
                    """SELECT external_id FROM linked_social_accounts
                       WHERE brand_id=17 AND platform='youtube'
                         AND status='connected'"""
                )
            ).scalars()
        )
    assert active_ids == ["UC-channel"]
    assert [
        item.status
        for item in store.list_discoveries(
            brand_id=17,
            platform=PlatformId.YOUTUBE,
        )
    ] == ["linked", "available"]

    disconnected = store.disconnect(
        brand_id=17,
        platform=PlatformId.YOUTUBE,
        external_id="UC-channel",
    )
    assert disconnected is not None
    assert disconnected.state == "disconnected"
    with engine.connect() as connection:
        connection_status = connection.execute(
            text("SELECT status FROM platform_connections WHERE id=:id"),
            {"id": pending.connection_id},
        ).scalar_one()
    assert connection_status == "disconnected"

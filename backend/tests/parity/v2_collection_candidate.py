"""V2 characterized collection slice subprocess candidate."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from app.application.ports.platforms import ProviderAccount, ProviderCredential  # noqa: E402
from app.application.services.collection import (  # noqa: E402
    CollectionTarget,
    collect_comments,
    collect_content,
    collect_profile,
)
from app.application.services.collection.media import (  # noqa: E402
    ContentMediaWriter,
    FetchedMedia,
)
from app.core.config import RuntimeMode  # noqa: E402
from app.core.write_policy import WritePolicy  # noqa: E402
from app.domain.metrics import bootstrap_metric_catalog  # noqa: E402
from app.domain.platforms import PlatformId  # noqa: E402
from app.infrastructure.checkpoints import ProjectionCheckpointStore  # noqa: E402
from app.infrastructure.persistence.media_files import AtomicMediaFiles  # noqa: E402
from app.infrastructure.persistence.social_v2 import (  # noqa: E402
    SocialCommentStore,
    SocialContentStore,
    SocialMediaStore,
    SocialMetricStore,
)
from app.infrastructure.providers.meta.facebook.comments import (  # noqa: E402
    FacebookCommentsReader,
)
from app.infrastructure.providers.meta.facebook.content import (  # noqa: E402
    FacebookContentReader,
)
from app.infrastructure.providers.meta.facebook.profile import (  # noqa: E402
    FacebookProfileReader,
)
from app.infrastructure.providers.meta.instagram.comments import (  # noqa: E402
    InstagramCommentsReader,
)
from app.infrastructure.providers.meta.instagram.content import (  # noqa: E402
    InstagramContentReader,
)
from app.infrastructure.providers.meta.instagram.profile import (  # noqa: E402
    InstagramProfileReader,
)
from app.infrastructure.providers.meta.rate_guard import MetaRateGuard  # noqa: E402
from app.infrastructure.providers.meta.transport import MetaTransport  # noqa: E402
from tests.parity.v2_transport_candidate import ForwardingTransport  # noqa: E402

FIXED_NOW = datetime(2026, 7, 14, 13, tzinfo=UTC)


def _fetch(source_url: str) -> FetchedMedia:
    return FetchedMedia(
        data=f"golden-media:{source_url}".encode(),
        mime_type="image/jpeg",
        status_code=200,
    )


def main() -> int:
    engine = create_engine(os.environ["PARITY_DATABASE_URL"])
    policy = WritePolicy(runtime_mode=RuntimeMode.DEVELOPMENT, writes_enabled=True)
    credential = ProviderCredential(access_token=os.environ["FIXTURE_PROVIDER_TOKEN"])
    fb_account = ProviderAccount(
        platform=PlatformId.FACEBOOK,
        account_id="page-1",
        credential=credential,
    )
    fb_target = CollectionTarget(account=fb_account, local_account_id=11, brand_id=7)
    ig_account = ProviderAccount(
        platform=PlatformId.INSTAGRAM,
        account_id="ig-1",
        credential=credential,
    )
    ig_target = CollectionTarget(account=ig_account, local_account_id=12, brand_id=7)
    transport = MetaTransport(
        credential=credential,
        rate_guard=MetaRateGuard(sleeper=lambda _: None),
        wire=ForwardingTransport(os.environ["FAKE_META_ORIGIN"]),
        egress_enabled=True,
        max_retries=0,
    )
    fb_profile = collect_profile(
        target=fb_target,
        reader=FacebookProfileReader(transport, clock=lambda: FIXED_NOW),
        metric_store=SocialMetricStore(engine, policy, bootstrap_metric_catalog()),
    )
    media_writer = ContentMediaWriter(
        target=fb_target,
        files=AtomicMediaFiles(Path(os.environ["PARITY_MEDIA_ROOT"])),
        media_store=SocialMediaStore(engine, policy),
        fetch=_fetch,
        clock=lambda: FIXED_NOW,
    )
    fb_content = collect_content(
        target=fb_target,
        reader=FacebookContentReader(transport, clock=lambda: FIXED_NOW),
        content_store=SocialContentStore(engine, policy),
        checkpoint_store=ProjectionCheckpointStore(engine, policy, clock=lambda: FIXED_NOW),
        record_sink=media_writer.persist,
    )
    fb_comments = collect_comments(
        target=fb_target,
        content_id="post-1",
        reader=FacebookCommentsReader(transport, clock=lambda: FIXED_NOW),
        comment_store=SocialCommentStore(engine, policy),
    )
    ig_profile = collect_profile(
        target=ig_target,
        reader=InstagramProfileReader(transport, clock=lambda: FIXED_NOW),
        metric_store=SocialMetricStore(engine, policy, bootstrap_metric_catalog()),
    )
    ig_media_writer = ContentMediaWriter(
        target=ig_target,
        files=AtomicMediaFiles(Path(os.environ["PARITY_MEDIA_ROOT"])),
        media_store=SocialMediaStore(engine, policy),
        fetch=_fetch,
        clock=lambda: FIXED_NOW,
    )
    ig_content = collect_content(
        target=ig_target,
        reader=InstagramContentReader(transport, clock=lambda: FIXED_NOW),
        content_store=SocialContentStore(engine, policy),
        checkpoint_store=ProjectionCheckpointStore(engine, policy, clock=lambda: FIXED_NOW),
        record_sink=ig_media_writer.persist,
    )
    ig_stories = collect_content(
        target=ig_target,
        reader=InstagramContentReader(
            transport,
            stories=True,
            clock=lambda: FIXED_NOW,
        ),
        content_store=SocialContentStore(engine, policy),
        checkpoint_store=ProjectionCheckpointStore(engine, policy, clock=lambda: FIXED_NOW),
        record_sink=ig_media_writer.persist,
        checkpoint_account_id=f"{ig_account.account_id}.stories",
    )
    ig_comments = collect_comments(
        target=ig_target,
        content_id="ig-post-1",
        reader=InstagramCommentsReader(transport, clock=lambda: FIXED_NOW),
        comment_store=SocialCommentStore(engine, policy),
    )
    transport.close()
    engine.dispose()
    print(
        json.dumps(
            {
                "status": ig_comments.status.value,
                "metric_count": fb_profile.metric_count + ig_profile.metric_count,
                "content_count": (
                    fb_content.content_count
                    + ig_content.content_count
                    + ig_stories.content_count
                ),
                "comment_count": fb_comments.comment_count + ig_comments.comment_count,
                "media_count": (
                    fb_content.media_count + ig_content.media_count + ig_stories.media_count
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

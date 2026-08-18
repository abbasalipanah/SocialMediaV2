"""One refused insight must not cost the whole account.

Meta declines an ineligible metric either with a 4xx or with a 200 carrying an
error payload. Only a 400 was tolerated, so any other refusal abandoned the
account's profile, content, comments and media as well — forty-four of
forty-nine Facebook accounts collected nothing for that reason.
"""

from __future__ import annotations

import pytest

from app.infrastructure.providers.meta.facebook.daily_metrics import _metric_refused
from app.infrastructure.providers.meta.transport import MetaTransportError


@pytest.mark.parametrize("status", [400, 403, 404, 200, None])
def test_provider_refusal_skips_only_that_metric(status) -> None:
    assert _metric_refused(MetaTransportError("meta_error_payload", status_code=status))


@pytest.mark.parametrize(
    "error",
    [
        MetaTransportError("meta_limit_response", status_code=200, retryable=True),
        MetaTransportError("meta_provider_rejected", status_code=500),
        MetaTransportError("meta_provider_rejected", status_code=503),
    ],
)
def test_rate_limits_and_server_faults_still_stop_the_run(error) -> None:
    # Recording an empty result for these would be a false negative.
    assert not _metric_refused(error)

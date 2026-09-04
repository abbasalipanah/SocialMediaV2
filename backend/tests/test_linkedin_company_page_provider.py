from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId
from app.infrastructure.providers.linkedin import (
    LinkedInAudienceReader,
    LinkedInContentReader,
    LinkedInDailyMetricsReader,
    LinkedInProfileReader,
    post_statistics_queries,
    posts_query,
    share_statistics_query,
)

NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)
ACCOUNT = ProviderAccount(
    platform=PlatformId.LINKEDIN,
    account_id="1234",
    credential=ProviderCredential(access_token="secret-access"),
)


def _interval(day: date) -> dict[str, int]:
    start = int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)
    return {"start": start, "end": start + 86_400_000}


def test_linkedin_wire_builds_company_page_queries_without_write_scopes() -> None:
    assert posts_query("1234", cursor="25") == {
        "q": "author",
        "author": "urn:li:organization:1234",
        "viewContext": "READER",
        "count": "25",
        "sortBy": "CREATED",
        "start": "25",
    }
    query = share_statistics_query("1234", since=date(2026, 8, 1), until=date(2026, 8, 2))
    assert query["q"] == "organizationalEntity"
    assert query["timeIntervals"].endswith("timeGranularityType:DAY)")
    assert post_statistics_queries(
        "1234",
        ("urn:li:share:1", "urn:li:ugcPost:2"),
    ) == (
        {
            "q": "organizationalEntity",
            "organizationalEntity": "urn:li:organization:1234",
            "shares": "List(urn:li:share:1)",
        },
        {
            "q": "organizationalEntity",
            "organizationalEntity": "urn:li:organization:1234",
            "ugcPosts[0]": "urn:li:ugcPost:2",
        },
    )


def test_linkedin_profile_and_supported_audience_facets_are_normalized() -> None:
    profile = LinkedInProfileReader(
        lambda _account: {
            "id": 1234,
            "localizedName": "Accumulated Example",
            "vanityName": "accumulated-example",
        },
        lambda _account: {"firstDegreeSize": 2048},
        clock=lambda: NOW,
    ).fetch_profile(ACCOUNT)
    assert profile.display_name == "Accumulated Example"
    assert profile.handle == "accumulated-example"
    assert profile.metric_values == {MetricId.FOLLOWERS: 2048}

    audience = LinkedInAudienceReader(
        lambda _account: {
            "elements": [
                {
                    "organizationalEntity": "urn:li:organization:1234",
                    "followerCountsByStaffCountRange": [
                        {
                            "staffCountRange": "SIZE_11_TO_50",
                            "followerCounts": {
                                "organicFollowerCount": 32,
                                "paidFollowerCount": 4,
                            },
                        }
                    ],
                    "followerCountsByAssociationType": [
                        {
                            "associationType": "EMPLOYEE",
                            "followerCounts": {
                                "organicFollowerCount": 8,
                                "paidFollowerCount": 0,
                            },
                        }
                    ],
                }
            ]
        },
        clock=lambda: NOW,
    ).fetch_audience(ACCOUNT)
    assert audience.breakdowns == {
        "staff_count": {"SIZE_11_TO_50": 32},
        "association_type": {"EMPLOYEE": 8},
    }


def test_linkedin_daily_metrics_merge_only_provider_returned_days() -> None:
    first = date(2026, 8, 30)
    second = date(2026, 8, 31)
    reader = LinkedInDailyMetricsReader(
        lambda _account, _since, _until: {
            "elements": [
                {
                    "organizationalEntity": "urn:li:organization:1234",
                    "timeRange": _interval(first),
                    "totalShareStatistics": {
                        "clickCount": 4,
                        "commentCount": 2,
                        "likeCount": 7,
                        "shareCount": 1,
                        "impressionCount": 100,
                        "uniqueImpressionsCount": 80,
                    },
                }
            ]
        },
        lambda _account, _since, _until: {
            "elements": [
                {
                    "organizationalEntity": "urn:li:organization:1234",
                    "timeRange": _interval(second),
                    "followerGains": {
                        "organicFollowerGain": 3,
                        "paidFollowerGain": 1,
                    },
                }
            ]
        },
        lambda _account, _since, _until: {
            "elements": [
                {
                    "organization": "urn:li:organization:1234",
                    "timeRange": _interval(first),
                    "totalPageStatistics": {
                        "views": {"allPageViews": {"pageViews": 12}},
                        "clicks": {},
                    },
                }
            ]
        },
    )

    rows = reader.fetch_daily_metrics(ACCOUNT, since=first, until=second)

    assert rows[0].observed_on == first
    assert rows[0].metric_values == {
        MetricId.VIEWS: 100,
        MetricId.REACH: 80,
        MetricId.INTERACTIONS: 14,
        MetricId.CLICKS: 4,
        MetricId.PAGE_VIEWS: 12,
    }
    assert rows[1].observed_on == second
    assert rows[1].metric_values == {MetricId.FOLLOWER_GAINS: 4}


def test_linkedin_content_keeps_organic_posts_and_the_provider_click_semantic() -> None:
    post_id = "urn:li:share:6856921137721544704"
    published = int(datetime(2026, 8, 31, tzinfo=UTC).timestamp() * 1000)
    payload = {
        "paging": {
            "start": 0,
            "count": 25,
            "links": [
                {
                    "rel": "next",
                    "href": "https://api.linkedin.com/rest/posts?q=author&start=25",
                }
            ],
        },
        "elements": [
            {
                "id": post_id,
                "author": "urn:li:organization:1234",
                "lifecycleState": "PUBLISHED",
                "publishedAt": published,
                "commentary": "Company update",
                "content": {"article": {"source": "https://example.test/article"}},
            },
            {
                "id": "urn:li:ugcPost:2",
                "author": "urn:li:organization:1234",
                "lifecycleState": "PUBLISHED",
                "publishedAt": published,
                "commentary": "Sponsored",
                "content": {},
                "adContext": {"isDsc": True},
            },
        ],
    }
    requested: list[tuple[str, ...]] = []
    reader = LinkedInContentReader(
        lambda _account, _cursor: payload,
        lambda _account, ids: (
            requested.append(ids)
            or (
                {
                    "elements": [
                        {
                            "organizationalEntity": "urn:li:organization:1234",
                            "share": post_id,
                            "totalShareStatistics": {
                                "clickCount": 5,
                                "commentCount": 2,
                                "likeCount": 9,
                                "shareCount": 1,
                                "impressionCount": 300,
                                "uniqueImpressionsCount": 240,
                            },
                        }
                    ]
                },
            )
        ),
        clock=lambda: NOW,
    )

    page = reader.list_content(ACCOUNT)

    assert requested == [(post_id,)]
    assert page.next_cursor == "25"
    assert len(page.items) == 1
    assert page.items[0].fields == {
        "content_type": "link",
        "permalink": f"https://www.linkedin.com/feed/update/{post_id}/",
        "message": "Company update",
        "media_url": "",
        "published_at": datetime(2026, 8, 31, tzinfo=UTC),
        "likes_count": 9,
        "comments_count": 2,
        "shares_count": 1,
        "views_count": 300,
        "reach_count": 240,
        "interactions_count": 17,
        "clicks_count": 5,
    }


def test_linkedin_content_stops_before_the_unsupported_analytics_archive() -> None:
    old_timestamp = int(datetime(2025, 8, 1, tzinfo=UTC).timestamp() * 1000)
    calls: list[tuple[str, ...]] = []
    page = LinkedInContentReader(
        lambda _account, _cursor: {
            "paging": {
                "start": 25,
                "count": 25,
                "links": [
                    {
                        "rel": "next",
                        "href": "https://api.linkedin.com/rest/posts?start=50",
                    }
                ],
            },
            "elements": [
                {
                    "id": "urn:li:share:1",
                    "author": "urn:li:organization:1234",
                    "lifecycleState": "PUBLISHED",
                    "publishedAt": old_timestamp,
                    "commentary": "Too old for share analytics",
                    "content": {},
                }
            ],
        },
        lambda _account, ids: calls.append(ids) or (),
        clock=lambda: NOW,
    ).list_content(ACCOUNT, cursor="25")

    assert page.items == ()
    assert page.next_cursor is None
    assert calls == [()]


def test_linkedin_daily_reader_rejects_an_account_mismatch() -> None:
    payload = {
        "elements": [
            {
                "organizationalEntity": "urn:li:organization:9999",
                "timeRange": _interval(date(2026, 8, 31)),
                "totalShareStatistics": {},
            }
        ]
    }
    reader = LinkedInDailyMetricsReader(
        lambda *_args: payload,
        lambda *_args: {"elements": []},
        lambda *_args: {"elements": []},
    )

    with pytest.raises(ValueError, match="linkedin_daily_account_mismatch"):
        reader.fetch_daily_metrics(
            ACCOUNT,
            since=date(2026, 8, 31),
            until=date(2026, 8, 31),
        )

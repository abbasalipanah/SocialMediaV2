"""A provider's Retry-After must not hand it the whole collection window.

`Retry-After` is the provider's choice and it is free to ask for an hour.
Honouring that inside a single request would spend one account's turn, and the
run's, waiting -- while every other account sat behind it uncollected.
"""

from __future__ import annotations

from app.infrastructure.providers.meta.transport import MAX_BACKOFF_SECONDS, MetaTransport


class _Recorder:
    def __init__(self) -> None:
        self.waits: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


def _transport(sleeper) -> MetaTransport:
    transport = MetaTransport.__new__(MetaTransport)
    transport._base_backoff_seconds = 0.6
    transport._sleeper = sleeper
    transport._jitter = lambda low, high: 0.0
    return transport


def test_an_hour_long_retry_after_is_capped() -> None:
    recorder = _Recorder()
    _transport(recorder)._sleep(0, 3600.0)

    assert recorder.waits == [MAX_BACKOFF_SECONDS]


def test_a_short_retry_after_is_honoured_exactly() -> None:
    recorder = _Recorder()
    _transport(recorder)._sleep(0, 5.0)

    assert recorder.waits == [5.0]


def test_backoff_still_grows_without_a_retry_after() -> None:
    recorder = _Recorder()
    transport = _transport(recorder)
    transport._sleep(0, None)
    transport._sleep(3, None)

    assert recorder.waits[1] > recorder.waits[0]
    assert all(wait <= MAX_BACKOFF_SECONDS for wait in recorder.waits)

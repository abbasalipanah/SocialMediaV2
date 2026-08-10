"""Bounded, session-owned jobs for transient report generation."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock, Timer, current_thread
from typing import Literal

ReportJobState = Literal["queued", "running", "ready", "failed"]
ProgressCallback = Callable[[int, str], None]


@dataclass(frozen=True)
class ReportArtifact:
    filename: str
    content: bytes


@dataclass(frozen=True)
class ReportJobView:
    job_id: str
    state: ReportJobState
    progress: int
    stage: str
    filename: str | None
    created_at: datetime
    expires_at: datetime | None
    error_code: str | None


@dataclass
class _ReportJob:
    job_id: str
    owner_session_hash: str
    brand_id: str
    rollup: bool
    state: ReportJobState
    progress: int
    stage: str
    created_at: datetime
    filename: str | None = None
    content: bytes | None = None
    expires_at: datetime | None = None
    error_code: str | None = None


class ReportJobError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ReportJobManager:
    """Single-worker queue with memory-only results and bounded lifetime."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 600,
        max_jobs: int = 16,
        max_jobs_per_owner: int = 2,
        max_workbook_bytes: int = 25 * 1024 * 1024,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_jobs = max_jobs
        self.max_jobs_per_owner = max_jobs_per_owner
        self.max_workbook_bytes = max_workbook_bytes
        self._jobs: dict[str, _ReportJob] = {}
        self._timers: dict[str, Timer] = {}
        self._lock = RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="xlsx-report")
        self._closed = False

    def enqueue(
        self,
        *,
        owner_session_hash: str,
        brand_id: str,
        rollup: bool,
        task: Callable[[ProgressCallback], ReportArtifact],
    ) -> ReportJobView:
        with self._lock:
            if self._closed:
                raise ReportJobError("report_queue_unavailable")
            retained = tuple(self._jobs.values())
            active = tuple(job for job in retained if job.state in {"queued", "running", "ready"})
            if len(retained) >= self.max_jobs:
                raise ReportJobError("report_queue_full")
            owner_jobs = sum(job.owner_session_hash == owner_session_hash for job in active)
            if owner_jobs >= self.max_jobs_per_owner:
                raise ReportJobError("report_owner_job_limit")
            job_id = secrets.token_urlsafe(24)
            job = _ReportJob(
                job_id=job_id,
                owner_session_hash=owner_session_hash,
                brand_id=brand_id,
                rollup=rollup,
                state="queued",
                progress=0,
                stage="Queued",
                created_at=datetime.now(UTC),
            )
            self._jobs[job_id] = job
            self._executor.submit(self._run, job_id, task)
            return self._view(job)

    def status(self, *, job_id: str, owner_session_hash: str) -> ReportJobView:
        with self._lock:
            job = self._owned_job(job_id, owner_session_hash)
            return self._view(job)

    def scope(self, *, job_id: str, owner_session_hash: str) -> tuple[str, bool]:
        with self._lock:
            job = self._owned_job(job_id, owner_session_hash)
            return job.brand_id, job.rollup

    def consume(self, *, job_id: str, owner_session_hash: str) -> ReportArtifact:
        with self._lock:
            job = self._owned_job(job_id, owner_session_hash)
            if job.state != "ready" or job.content is None or job.filename is None:
                raise ReportJobError("report_job_not_ready")
            artifact = ReportArtifact(filename=job.filename, content=job.content)
            self._remove_locked(job_id)
            return artifact

    def close(self) -> None:
        with self._lock:
            self._closed = True
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
            self._jobs.clear()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(
        self,
        job_id: str,
        task: Callable[[ProgressCallback], ReportArtifact],
    ) -> None:
        self._progress(job_id, 3, "Preparing report data", state="running")
        try:
            artifact = task(lambda value, stage: self._progress(job_id, value, stage))
            if not artifact.content or len(artifact.content) > self.max_workbook_bytes:
                raise ReportJobError("report_workbook_size_limit")
            with self._lock:
                job = self._jobs.get(job_id)
                if job is None:
                    return
                job.state = "ready"
                job.progress = 100
                job.stage = "Ready to download"
                job.filename = artifact.filename
                job.content = artifact.content
                job.expires_at = datetime.now(UTC) + timedelta(seconds=self.ttl_seconds)
                timer = Timer(self.ttl_seconds, self._expire, args=(job_id,))
                timer.daemon = True
                self._timers[job_id] = timer
                timer.start()
        except Exception as exc:  # the public contract deliberately returns a stable error code
            code = exc.code if isinstance(exc, ReportJobError) else "report_generation_failed"
            with self._lock:
                job = self._jobs.get(job_id)
                if job is None:
                    return
                job.state = "failed"
                job.progress = min(job.progress, 99)
                job.stage = "Generation failed"
                job.error_code = code
                job.content = None
                job.expires_at = datetime.now(UTC) + timedelta(seconds=self.ttl_seconds)
                timer = Timer(self.ttl_seconds, self._expire, args=(job_id,))
                timer.daemon = True
                self._timers[job_id] = timer
                timer.start()

    def _progress(
        self,
        job_id: str,
        value: int,
        stage: str,
        *,
        state: ReportJobState | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.progress = max(job.progress, min(99, max(0, value)))
            job.stage = stage[:120]
            if state is not None:
                job.state = state

    def _expire(self, job_id: str) -> None:
        with self._lock:
            self._remove_locked(job_id)

    def _owned_job(self, job_id: str, owner_session_hash: str) -> _ReportJob:
        job = self._jobs.get(job_id)
        if job is None or not secrets.compare_digest(job.owner_session_hash, owner_session_hash):
            raise ReportJobError("report_job_not_found")
        if job.expires_at is not None and job.expires_at <= datetime.now(UTC):
            self._remove_locked(job_id)
            raise ReportJobError("report_job_not_found")
        return job

    def _remove_locked(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)
        timer = self._timers.pop(job_id, None)
        if timer is not None and timer is not current_thread():
            timer.cancel()

    @staticmethod
    def _view(job: _ReportJob) -> ReportJobView:
        return ReportJobView(
            job_id=job.job_id,
            state=job.state,
            progress=job.progress,
            stage=job.stage,
            filename=job.filename,
            created_at=job.created_at,
            expires_at=job.expires_at,
            error_code=job.error_code,
        )


__all__ = [
    "ProgressCallback",
    "ReportArtifact",
    "ReportJobError",
    "ReportJobManager",
    "ReportJobState",
    "ReportJobView",
]
